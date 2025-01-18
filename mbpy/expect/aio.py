import asyncio
from asyncio.subprocess import Process, SubprocessStreamProtocol
import os
import re
import shlex
import signal
import sys
import weakref
from typing import Any, List, Optional, Pattern, Tuple, Union

from mbpy.expect import Expecter
import uvloop.handles


class AsyncPExpectError(Exception):...
_DEFAULT_LIMIT = 2**16  # 64 KiB
EXTRA_LIMIT = 2**20  # 1 MiB


class AsyncPExpector(Expecter):
    """Async implementation of pexpect-like functionality using asyncio streams."""

    def __init__(
        self,
        command: str | List[str],
        timeout: float = 30.0,
        encoding: str = "utf-8",
        codec_errors: str = "strict",
        env: dict | None = None,
        maxread: int = 2000,
    ):
        """Initialize AsyncPExpect instance.

        Args:
            command: Command to execute (string or list of arguments)
            timeout: Default timeout for expect operations
            encoding: Character encoding to use for string operations
            codec_errors: How to handle encoding errors
            env: Optional environment variables dictionary
            maxread: Maximum number of bytes to read at once
        """
        self.command = command if isinstance(command, list) else command.split()
        self._timeout = timeout
        self.encoding = encoding
        self.codec_errors = codec_errors
        self.env = env
        self.maxread = maxread

        # Stream handling
        self._reader: asyncio.StreamReader| None = asyncio.StreamReader()
        self._transport: asyncio.SubprocessTransport| None = asyncio.SubprocessTransport()
        self._protocol: asyncio.SubprocessProtocol| None = asyncio.SubprocessProtocol()
        self._writer: asyncio.StreamWriter | None = None


        # Pattern matching state
        self.before = b""  # Everything before last match
        self.after = b""  # Everything after last match
        self.match = None  # Last match object
        self._buffer = b""  # Current buffer of unmatched data

        # Process state
        self.pid: Optional[int] = None
        self.closed = False
        self.terminated = False
        self._status: Optional[int] = None

        # Ensure proper cleanup
        self._spawn_task: Optional[asyncio.Task] = None
        self._cleanup_weakref = weakref.ref(self, self._cleanup)

    @property
    def exitstatus(self) -> Optional[int]:
        """The exit status of the process. Only available after process terminates."""
        return self._status

    async def spawn(self, *, timeout: float | None = None) -> None:  # noqa: ASYNC109
        """Spawn the child process and set up communication streams.

        Args:
            timeout: Optional timeout for process startup
        """
        if self._reader is not None:
            return

        connect_timeout = timeout if timeout is not None else self.timeout
        cmd, *args = shlex.split(self.command) if isinstance(self.command, str) else self.command

        try:    
                loop = asyncio.events.get_running_loop()
                protocol_factory = lambda: SubprocessStreamProtocol(limit=EXTRA_LIMIT, loop=loop)
                self._transport, self._protocol = await loop.subprocess_exec(
                    protocol_factory,
                    cmd, *args,
                    stdin=sys.stdin, stdout=sys.stdout,
                    stderr=sys.stderr, encoding=self.encoding,errors=self.codec_errors
                )
                self._process = Process(self._transport, self._protocol, loop)
                
                # self._writer = asyncio.StreamWriter(self._transport, self._protocol, self._reader, loop)
                self._writer = self._process.stdin
                if self._process.stdin is None or self._process.stdout is None:
                    raise AsyncPExpectError("Failed to create subprocess pipes")

                self._reader = self._process.stdout
                self.pid = self._process.pid

        except TimeoutError:
            if self._transport is not None:
                self._transport.kill()
            raise TimeoutError(f"Timeout ({connect_timeout}s) while spawning process") from None

    def _cleanup(self, weakref: weakref.ReferenceType) -> None:
        """Clean up resources when object is garbage collected."""
        if not self.closed and self._transport is not None:
            self._transport.kill()
            self.closed = True
            del weakref
            

    async def expect(
        self,
        pattern: str | bytes | Pattern | List[Union[str, bytes, Pattern]],
        timeout: float | None = None,  # noqa: ASYNC109
        *,
        async_: bool = False,
    ) -> int:
        """Wait for the expected pattern(s) in the output stream.

        Args:
            pattern: String, bytes, regex pattern or list of patterns
            timeout: Optional timeout override
            async_: If True, don't consume input between matches

        Returns:
            Index of the pattern that matched (0 if single pattern)

        Raises:
            TimeoutError: Pattern not found within timeout
            EOFError: EOF reached before pattern match
            AsyncPExpectError: Other errors
        """
        if self._reader is None:
            raise AsyncPExpectError("Process not spawned")



        # Normalize patterns to list of compiled regex patterns
        patterns = [pattern] if not isinstance(pattern, list) else pattern

        compiled_patterns: list[Pattern] = []
        for p in patterns:
            if isinstance(p, str | bytes):
                if isinstance(p, str):
                    pat = p.encode(self.encoding, self.codec_errors)
                compiled_patterns.append(re.compile(re.escape(pat)))
            else:
                # Already a pattern object
                compiled_patterns.append(p)

        try:
            async with asyncio.timeout(timeout):
                while True:
                    # Check existing buffer first
                    for i, cp in enumerate(compiled_patterns):
                        match = cp.search(self._buffer)
                        if match:
                            self.before = self._buffer[: match.start()]
                            self.after = self._buffer[match.start() : match.end()]
                            self.match = match
                            if not async_:
                                self._buffer = self._buffer[match.end() :]
                            return i

                    # Read more data
                    try:
                        chunk = await self._reader.read(self.maxread)
                    except ConnectionError as e:
                        raise AsyncPExpectError(f"Connection error: {e}") from e

                    if not chunk:
                        if self._transport and self._transport.get_returncode() is not None:
                            self._status = self._transport.get_returncode()
                        raise EOFError("EOF reached before match")

                    self._buffer += chunk

        except TimeoutError:
            raise TimeoutError(f"Pattern not found within {timeout} seconds") from None

    async def expect_exact(
        self, pattern: str | bytes | List[str | bytes], timeout: float | None = None  # noqa: ASYNC109
    ) -> int:
        """Wait for an exact string pattern. More efficient than regex matching.

        Args:
            pattern: String, bytes or list of strings/bytes to match
            timeout: Optional timeout override

        Returns:
            Index of the pattern that matched
        """
        patterns = [pattern] if isinstance(pattern, str | bytes) else pattern

        # Convert strings to bytes
        byte_patterns = [p.encode(self.encoding, self.codec_errors) if isinstance(p, str) else p for p in patterns]


        try:
            async with asyncio.timeout(timeout):
                while True:
                    for i, bp in enumerate(byte_patterns):
                        pos = self._buffer.find(bp)
                        if pos >= 0:
                            self.before = self._buffer[:pos]
                            self.after = bp
                            self.match = None  # No regex match object for exact matches
                            self._buffer = self._buffer[pos + len(bp) :]
                            return i

                    chunk = await self._reader.read(self.maxread)
                    if not chunk:
                        if self._transport and self._transport.get_returncode() is not None:
                            self._status = self._transport.get_returncode()
                        raise EOFError("EOF reached before match")
                    self._buffer += chunk

        except TimeoutError:
            raise TimeoutError(f"Pattern not found within {timeout} seconds") from None

    async def expect_eof(self, timeout: Optional[float] = None) -> None:
        """Wait for EOF from the process.

        Args:
            timeout: Optional timeout override
        """
        if self._reader is None:
            return

        timeout_val = timeout if timeout is not None else self.timeout

        try:
            async with asyncio.timeout(timeout):
                while True:
                    chunk = await self._reader.read(self.maxread)
                    if not chunk:
                        break
                    self._buffer += chunk

                if self._transport:
                    self._status = self._transport.get_returncode()

        except TimeoutError:
            raise TimeoutError(f"EOF not received within {timeout} seconds") from None

    async def send(self, data: str | bytes) -> None:
        """Send data to the process.

        Args:
            data: Data to send (string or bytes)
        """
        if self._writer is None:
            raise AsyncPExpectError("Process not spawned")

        if isinstance(data, str):
            data = data.encode(self.encoding, self.codec_errors)

        self._writer.write(data)
        await self._writer.drain()

    async def sendline(self, line: str | bytes = "") -> None:
        """Send a line of text to the process.

        Args:
            line: Line to send (appends newline)
        """
        await self.send(line)
        await self.send(os.linesep.encode(self.encoding, self.codec_errors))

    def terminate(self, force: bool = False) -> None:
        """Terminate the child process.

        Args:
            force: If True, use SIGKILL instead of SIGTERM
        """
        if self._transport is None or self.terminated:
            return

        if force:
            self._transport.kill()
        else:
            self._transport.terminate()

        self.terminated = True

    async def close(self) -> None:
        """Close the process and clean up resources."""
        if self.closed:
            return

        if self._writer is not None:
            self._writer.close()
            await self._writer.wait_closed()

        if not self.terminated and self._transport is not None:
            self.terminate()

        self.closed = True
        self._reader = None
        self._writer = None
        self._transport = None
        self._buffer = b""

    async def __aenter__(self):
        """Async context manager entry."""
        await self.spawn()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
