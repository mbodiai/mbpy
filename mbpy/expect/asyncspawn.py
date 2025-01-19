"""Async-native process spawner and expecter."""
import asyncio
import re
from typing import AsyncIterator, Optional, Pattern, Union

from mbpy.import_utils import smart_import

class AsyncSpawn:
    """Async-native process spawner with expect-like functionality."""
    
    def __init__(self, command: str | list[str], show: bool = False, cwd=None, shell=False, **kwargs):
        self.command = command if isinstance(command, str) else " ".join(command)
        self.kwargs = kwargs
        self.show = show
        self.process: Optional[asyncio.subprocess.Process] = None
        self._buffer = bytearray()
        self.before = ""
        self.after = ""
        self.match = None
        self.cwd = cwd
        self.shell = shell
        self.spinner = smart_import("mbpy.helpers._display.SPINNER")()
        
    async def __aenter__(self):
        """Start process when entering context."""
        shlex = smart_import("shlex")
        if self.shell:
            self.process = await asyncio.create_subprocess_shell(
                self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.PIPE,
                cwd=self.cwd,
                **self.kwargs
            )
        else:
            # Split command into program and arguments
            args = shlex.split(self.command)
            if not args:
                raise ValueError("Empty command")
                
            self.process = await asyncio.create_subprocess_exec(
                args[0],
                *args[1:],
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.PIPE,
                cwd=self.cwd,
                **self.kwargs
            )
        return self
        
    async def __aexit__(self, exc_type, exc, tb):
        """Ensure cleanup happens even with errors."""
        try:
            await self.terminate()
        except Exception as e:
            # Log but don't raise - ensure cleanup completes
            import logging
            logging.error(f"Error during process cleanup: {e}")
            
    async def terminate(self):
        """Safely terminate the process."""
        if self.process:
            try:
                # Check if process is still running before attempting to terminate
                if self.process.returncode is None:
                    try:
                        self.process.terminate()
                        # Give process time to terminate gracefully
                        try:
                            await asyncio.wait_for(self.process.wait(), timeout=1.0)
                        except asyncio.TimeoutError:
                            # Force kill if graceful termination fails
                            self.process.kill()
                            await self.process.wait()
                    except ProcessLookupError:
                        # Process already terminated
                        pass
            finally:
                self.process = None

    async def readline(self) -> str:
        if not self.process or not self.process.stdout:
            raise RuntimeError("Process not started")
        line = await self.process.stdout.readline()
        sterr = await self.process.stderr.readline()
        line = line.decode().strip()
        sterr = sterr.decode().strip()
        self.spinner.stop()
        if line and not sterr:
            return line
        if sterr and not line:
            return sterr
        if line and sterr:
            return line + "\n" + sterr
    
    async def readtext(self) -> str:
        """Read the entire output from the process."""
        return "\n".join(await self.readlines())
    async def readlines(self,show=False) -> list[str]:
        """Async generator that yields lines from the process output."""
        out = []
        async for line in self.streamlines(show=show):
            out.append(line)
        return out

    async def streamlines(self, show=False) -> AsyncIterator[str]:
        """Async generator that yields lines from the process output."""
        show = show or self.show
        console = smart_import("mbpy.helpers._display.getconsole")()
        Text = smart_import("rich.text.Text")
        while True:
            line = await self.readline()
            if not line:
                break
            if show:
                self.spinner.stop()
                console.print(line)
            yield line

    async def expect(self, 
                    pattern: Union[str, bytes, Pattern, list[Union[str, bytes, Pattern]]], 
                    timeout: float = 30) -> AsyncIterator[int]:
        """Async generator that yields matches against the pattern."""
        patterns = [re.compile(pattern)] if isinstance(pattern, (str, bytes)) else [
            re.compile(p) if isinstance(p, (str, bytes)) else p 
            for p in pattern
        ]

        async with asyncio.timeout(timeout):
            while True:
                if not self.process or self.process.stdout.at_eof():
                    break
                    
                data = await self.process.stdout.read(1024)
                if not data:
                    break
                    
                self._buffer.extend(data)
                current = self._buffer.decode()
                
                for i, p in enumerate(patterns):
                    if match := p.search(current):
                        self.before = current[:match.start()]
                        self.after = current[match.end():]
                        self.match = match
                        self._buffer = self.after.encode()
                        yield i
                        break

    async def send(self, data: str) -> None:
        if not self.process or not self.process.stdin:
            raise RuntimeError("Process not started")
        self.process.stdin.write(data.encode())
        await self.process.stdin.drain()

    async def sendline(self, data: str = '') -> None:
        await self.send(data + '\n')

    def __aiter__(self):
        return self.streamlines()

# Example usage:
async def check_repo(repo: str) -> bool:
    async with AsyncSpawn(f"gh repo view {repo} --json name") as proc:
        async for _ in proc.expect("not found|name"):
            if "not found" in proc.match.group():
                return False
            return True
    return False
