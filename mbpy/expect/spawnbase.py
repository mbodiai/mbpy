"""Copied and modified to work with asyncio and windows from pexpect."""

import asyncio
import codecs
import errno
import logging
import os
from pathlib import Path
import re
import signal
import socket
import sys
from collections.abc import Awaitable, Callable, Iterable
from contextlib import contextmanager
from io import BytesIO, StringIO
from logging import Formatter, Handler
from re import Match
from typing import (
    IO,
    Any,
    AsyncIterator,
    Literal,
    Protocol,
    TextIO,
    TypeVar,
    cast,
    overload,
)

from rich.console import Console

from mbpy.expect.exceptions import EOF, TIMEOUT
from mbpy.expect.expect import Expecter, PatternWaiter
from mbpy.expect.searcher import SearcherStringT, searcher_re, searcher_string

# Define type aliases
string_types = (str, bytes)
AnyStrT = TypeVar("AnyStrT", str, bytes)
AnyStrT_co = TypeVar("AnyStrT_co", str, bytes, covariant=True)
AnyStr = str | bytes
LogFile = Any | None


class _NullCoder:
    """Pass bytes through unchanged."""

    @staticmethod
    def encode(b, final=False):
        return b

    @staticmethod
    def decode(b, final=False):
        return b

class SpawnBaseT(Protocol[AnyStrT]):
    encoding: str | None
    pid: int | None
    flag_eof: bool
    stdin: TextIO
    stdout: TextIO
    stderr: TextIO
    searcher: None | SearcherStringT
    ignorecase: bool
    before: AnyStrT | None
    after: Any | None
    match: AnyStrT | Match[str] | Match[bytes] | EOF | TIMEOUT | None
    match_index: int | None
    terminated: bool
    exitstatus: int | None
    signalstatus: int | None
    status: int | None
    child_fd: int
    timeout: float | None
    delimiter: type[EOF]
    logfile: LogFile
    logfile_read: LogFile
    logfile_send: LogFile
    maxread: int
    searchwindowsize: int | None
    delaybeforesend: float | None
    delayafterclose: float
    delayafterterminate: float
    delayafterread: float
    softspace: bool
    name: str
    closed: bool
    codec_errors: str
    string_type: type[AnyStrT]
    buffer_type: type[IO[AnyStrT]]
    crlf: AnyStr
    allowed_string_types: tuple[type, ...]
    linesep: AnyStr
    write_to_stdout: Callable[[AnyStr], int ] | Any

    @property
    def buffer(self) -> AnyStr: ...
    @buffer.setter
    def buffer(self, value: AnyStr) -> None: ...
    def read_nonblocking(self, size: int = 1, timeout: float | None = None) -> AnyStr: ...
    def compile_pattern_list(
        self,
        patterns: Any | list[Any],
    ) -> list[Any]: ...
    @overload
    def expect(
        self,
        pattern: Any | list[Any],
        timeout: float | None = -1,
        searchwindowsize: int | None = -1,
        async_: Literal[False] = False,
    ) -> int: ...
    @overload
    def expect(
        self,
        pattern: Any | list[Any],
        timeout: float | None = -1,
        searchwindowsize: int | None = -1,
        *,
        async_: Literal[True],
    ) -> Awaitable[int]: ...
    @overload
    def expect_list(
        self,
        pattern_list: list[Any],
        timeout: float | None = -1,
        searchwindowsize: int | None = -1,
        async_: Literal[False] = False,
    ) -> int: ...
    @overload
    def expect_list(
        self,
        pattern_list: list[Any],
        timeout: float | None = -1,
        searchwindowsize: int | None = -1,
        *,
        async_: Literal[True],
    ) -> Awaitable[int]: ...
    @overload
    def expect_exact(
        self,
        pattern_list: Any | Iterable[Any],
        timeout: float | None = -1,
        searchwindowsize: int | None = -1,
        async_: Literal[False] = False,
    ) -> int: ...
    @overload
    def expect_exact(
        self,
        pattern_list: Any | Iterable[Any],
        timeout: float | None = -1,
        searchwindowsize: int | None = -1,
        *,
        async_: Literal[True],
    ) -> Awaitable[int]: ...
    def expect_loop(
        self,
        searcher: SearcherStringT,
        timeout: float | None = -1,
        searchwindowsize: int | None = -1,
    ) -> int: ...
    def read(self, size: int = -1) -> AnyStr: ...
    def readline(self, size: int = -1) -> AnyStr: ...
    def __iter__(self): ...
    def readlines(self, sizehint: int = -1) -> list[AnyStr]: ...
    def fileno(self) -> int: ...
    def flush(self) -> None: ...
    def isatty(self) -> bool: ...
    def __enter__(self): ...
    def __exit__(self, etype, evalue, tb) -> None: ...
    def close(self) -> None: ...
    def __init__(
        self,
        command: str | None,
        args: list[str] | None = None,
        timeout: int | float | None = 30,
        maxread: int = 2000,
        searchwindowsize: int | None = None,
        logfile: Any | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        ignore_sighup: bool = False,
        echo: bool = True,
        preexec_fn: Callable[[], None] | None = None,
        encoding: str | None = None,
        codec_errors: str = "strict",
        dimensions: tuple[int, int] | None = None,
        use_poll: bool = False,
    ): ...
    def __call__(self, command: str, args: list[str] | None = None, **kwargs) -> None: ...


text_type = str


class SpawnBase(SpawnBaseT[str]):
    encoding: str | None = None
    pid: int | None = None
    flag_eof: bool = False

    def __init__(
        self,
        timeout: float | None = 30,
        maxread: int = 2000,
        searchwindowsize: int | None = None,
        logfile: Any | None = None,
        encoding: str | None = None,
        codec_errors: str = "strict",
    ):
        self.stdin: TextIO = sys.stdin
        self.stdout: TextIO = sys.stdout
        self.stderr: TextIO = sys.stderr

        self.searcher: SearcherStringT | None = None
        self.ignorecase: bool = False
        self.before: bytes | str | None = None
        self.after: AnyStr | None = None
        self.match: AnyStr | Match[str] | Match[bytes] | Exception | None = None
        self.match_index: int | None = None
        self.terminated: bool = True
        self.exitstatus: int | None = None
        self.signalstatus: int | None = None
        self.status: int | None = None
        self.child_fd: int | None = -1
        self.timeout: float | None = timeout
        self.delimiter: type[EOF] = EOF
        self.logfile: Any | None = Path(logfile) if isinstance(logfile, str) else logfile if isinstance(logfile, Path) else Path(".pexpect.log")
        self.logfile_read: Any | None = None
        self.logfile_send: Any | None = None
        self.maxread: int = maxread
        self.searchwindowsize: int | None = searchwindowsize
        self.delaybeforesend: float | None = 0.05
        self.delayafterclose: float = 0.1
        self.delayafterterminate: float = 0.1
        self.delayafterread: float | None = 0.0001
        self.softspace: bool = False
        self.name: str = "<" + repr(self) + ">"
        self.closed: bool = True

        self.encoding: str | None = encoding
        self.codec_errors: str = codec_errors
        if encoding is None:
            self._encoder = self._decoder = _NullCoder()
            self.string_type = bytes
            self.buffer_type = BytesIO
            self.crlf = b"\r\n"

            self.allowed_string_types = (bytes, str)
            self.linesep = os.linesep.encode("ascii")

            def write_to_stdout(b):
                try:
                    return sys.stdout.buffer.write(b)
                except AttributeError:
                    return sys.stdout.write(b.decode("ascii", "replace"))

            self.write_to_stdout = write_to_stdout
        else:
            self._encoder = codecs.getincrementalencoder(encoding)(codec_errors)
            self._decoder = codecs.getincrementaldecoder(encoding)(codec_errors)
            self.string_type = text_type
            self.buffer_type = StringIO
            self.crlf = "\r\n"
            self.allowed_string_types = (text_type,)
            self.linesep = os.linesep

            self.write_to_stdout = sys.stdout.write
        self.async_pw_transport: tuple[PatternWaiter, asyncio.Transport] | None = None
        self._buffer = self.buffer_type()
        self._before = self.buffer_type()
        self.logfile = self.logfile or ".pexpect.log"

    def _log(self, s, direction):
        if self.logfile is not None:

            self.logfile.write_text(s.decode("utf-8"))

        second_log = self.logfile_send if (direction == "send") else self.logfile_read
        if second_log is not None:
            second_log.write(s)
            second_log.flush()

    def _coerce_expect_string(self, s):
        if self.encoding is None and not isinstance(s, bytes):
            return s.encode("ascii")
        return s

    def _coerce_expect_re(self, r):
        p = r.pattern
        if self.encoding is None and not isinstance(p, bytes):
            return re.compile(p.encode("utf-8"))
        if self.encoding is not None and isinstance(p, bytes):
            return re.compile(p.decode("utf-8"))
        return r

    def _coerce_send_string(self, s):
        if self.encoding is None and not isinstance(s, bytes):
            return s.encode("utf-8")
        return s

    def _get_buffer(self):
        return self._buffer.getvalue()

    def _set_buffer(self, value):
        self._buffer = self.buffer_type()
        self._buffer.write(value)

    buffer = property(_get_buffer, _set_buffer)

    def read_nonblocking(self, size=1, timeout=None):
        try:
            s = os.read(self.child_fd, size)
        except OSError as err:
            if err.args[0] == errno.EIO:
                self.flag_eof = True
                raise EOF("End Of File (EOF). Exception style platform.")
            raise
        if s == b"":
            self.flag_eof = True
            raise EOF("End Of File (EOF). Empty string style platform.")

        s = self._decoder.decode(s, final=False)
        self._log(s, "read")
        return s

    def _pattern_type_err(self, pattern):
        raise TypeError(
            "got {badtype} ({badobj!r}) as pattern, must be one"
            " of: {goodtypes}, pexpect.EOF, pexpect.TIMEOUT".format(
                badtype=type(pattern),
                badobj=pattern,
                goodtypes=", ".join([str(ast) for ast in self.allowed_string_types]),
            ),
        )

    def compile_pattern_list(self, patterns):
        if patterns is None:
            return []
        if not isinstance(patterns, list):
            patterns = [patterns]

        compile_flags = re.DOTALL
        if self.ignorecase:
            compile_flags = compile_flags | re.IGNORECASE
        compiled_pattern_list = []
        for _idx, p in enumerate(patterns):
            if isinstance(p, self.allowed_string_types):
                p = self._coerce_expect_string(p)
                compiled_pattern_list.append(re.compile(p, compile_flags))
            elif p is EOF:
                compiled_pattern_list.append(EOF)
            elif p is TIMEOUT:
                compiled_pattern_list.append(TIMEOUT)
            elif isinstance(p, type(re.compile(""))):
                p = self._coerce_expect_re(p)
                compiled_pattern_list.append(p)
            else:
                self._pattern_type_err(p)
        return compiled_pattern_list

    def expect(self, pattern, timeout=-1, searchwindowsize=-1, async_=False, **kw):
        if "async" in kw:
            async_ = kw.pop("async")
        if kw:
            raise TypeError(f"Unknown keyword arguments: {kw}")

        compiled_pattern_list = self.compile_pattern_list(pattern)
        return self.expect_list(compiled_pattern_list, timeout, searchwindowsize, async_)

    def expect_list(self, pattern_list, timeout=-1, searchwindowsize=-1, async_=False, **kw):
        if timeout == -1:
            timeout = self.timeout
        if "async" in kw:
            async_ = kw.pop("async")
        if kw:
            raise TypeError(f"Unknown keyword arguments: {kw}")

        exp = Expecter(self, searcher_re(pattern_list), searchwindowsize)
        if async_:
            from ._async import expect_async

            return expect_async(exp, timeout)
        return exp.expect_loop(timeout)

    def expect_exact(self, pattern_list, timeout=-1, searchwindowsize=-1, async_=False, **kw):
        if timeout == -1:
            timeout = self.timeout
        if "async" in kw:
            kw.pop("async")
        if kw:
            raise TypeError(f"Unknown keyword arguments: {kw}")

        if isinstance(pattern_list, self.allowed_string_types) or pattern_list in (TIMEOUT, EOF):
            pattern_list = [pattern_list]

        def prepare_pattern(pattern):
            if pattern in (TIMEOUT, EOF):
                return pattern
            if isinstance(pattern, self.allowed_string_types):
                return self._coerce_expect_string(pattern)
            self._pattern_type_err(pattern)
            return None

        try:
            pattern_list = iter(pattern_list)
        except TypeError:
            self._pattern_type_err(pattern_list)
        pattern_list = [prepare_pattern(p) for p in pattern_list]

        exp = Expecter(self, searcher_string(pattern_list), searchwindowsize)

        return exp.expect_loop(timeout)

    def expect_loop(self, searcher, timeout=-1, searchwindowsize=-1):
        exp = Expecter(self, searcher, searchwindowsize)
        return exp.expect_loop(timeout)

    def read(self, size=-1):
        if size == 0:
            return self.string_type()
        if size < 0:
            self.expect(self.delimiter)
            return self.before

        cre = re.compile(self._coerce_expect_string(".{%d}" % size), re.DOTALL)
        index = self.expect([cre, self.delimiter])
        if index == 0:
            return self.after
        return self.before

    def readline(self, size=-1):
        if size == 0:
            return self.string_type()
        index = self.expect([self.crlf, self.delimiter])
        if index == 0:
            return cast(str, self.before) + cast(str, self.crlf)

        return self.before

    def __iter__(self):
        return iter(self.readline, self.string_type())

    def readlines(self, sizehint=-1):
        lines = []
        while True:
            line = self.readline()
            if not line:
                break
            lines.append(line)
        return lines

    def fileno(self):
        return self.child_fd

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False

    def __enter__(self):
        return self

    def __exit__(self, etype, evalue, tb):
        self.close()
