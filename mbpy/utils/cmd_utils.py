from __future__ import annotations

import asyncio
import fcntl
import logging
import sys
import termios
import traceback
from contextlib import contextmanager, suppress
from functools import partial, wraps
from pathlib import Path
from signal import SIGINT
from threading import Thread
from time import time
from types import NoneType
from typing import AsyncIterator, Callable, Generic, Iterator, Self, TypeAlias, TypeVar, cast

import pexpect._async
from rich.console import Console
from rich.text import Text
from typing_extensions import ParamSpec

from mbpy import SPINNER, isverbose
from mbpy.utils.poexpect import EOF, TIMEOUT, SpawnBase, aspawn, spawn
from mbpy.utils.poexpect import ExceptionPexpect as PexpectException

P = ParamSpec("P")
R = TypeVar("R", bound=str | Iterator[str])

console = Console(force_terminal=True)
if sys.platform == "win32":
    import mbpy.poexpect as pexpect

    pexpect.socket_pexpect = pexpect.Expecter

    

    pexpect.socket_pexpect = pexpect.spawn


else:
    import fcntl
    import termios

    from mbpy.utils import poexpect



    IOCTL = partial(fcntl.ioctl, sys.stdout.fileno(), termios.TIOCGWINSZ)
    class FakeError(Exception):...

pexpect_module = poexpect

PexpectT = TypeVar("PexpectT", bound=spawn)
AExpectT = TypeVar("AExpectT", bound=aspawn)
SpawnT = TypeVar("SpawnT", bound=SpawnBase | spawn | aspawn)
class CommandBase(Generic[SpawnT]):
    process_type: type[SpawnBase]
    process: SpawnT
    _signalstatus: int
    def __init__(
        self,
        cmd: str,
        args: list[str] | None = None,
        show=False,
        cwd=None,
        timeout=30,
        **kwargs,
    ):
        
        self.show = show
        self.cmd: str = cmd
        self.callable_cmd: Callable[[SpawnT,], SpawnBase] = partial(self.process_type,cmd,args,timeout=timeout,**kwargs)
        self.args = args or []

     

        cwd = Path(str(cwd)).resolve() if cwd else Path.cwd()
        self.cwd = cwd if cwd.is_dir() else cwd.parent if cwd.exists() else Path.cwd()
        self.output = []
        self.started = 0
        self.thread = None
        self.lines = []
        self._threads: list[Thread] = []
        self.process = None
        self._started = time()
        self._signalstatus = 0
        logging.debug(f"{cmd=} {args=}, {cwd=}, {kwargs=}")
        logging.debug(f"self: {self=}, {self.cwd=}")

    def _create_thread(self, target, *args, **kwargs):
        thread = Thread(target=target, daemon=True)
        self._threads.append(thread)
        return thread

    @property
    def signaled(self) -> bool:
        return self._signalstatus != 0

    @signaled.setter
    def signaled(self, value: bool):
        self._signalstatus = int(value)

    def expect(self,*args,**kwargs) -> int:
        raise NotImplementedError

    def sigint(self) -> None:
        self._signalstatus = SIGINT

    @classmethod
    def __class_getitem__(cls, item: SpawnT) -> type[Self]:
        cls.process_type = item
        # new = new_class(f"CommandCtx[{item}]", (cls,), {})
        # new.process_type = item
        return cls

    def getorstart(self) ->SpawnT:
        self._started = time()
        if self.process:
            return self.process
        self.process = self.start()
        return self.process

    def start(self) ->SpawnT:
        if time() - self._started > 0.25:
            raise TimeoutError
        try:
            self.process = self.callable_cmd()
        except Exception as e:
            self.process = spawn("bash -c " + self.cmd or "")
            logging.debug(f"Error: {e}")
        self.started = time()
        return self.process

    def __contains__(self, item):
        return item in " ".join(self.lines)
    
class CommandCtx(CommandBase[PexpectT]):
    @contextmanager
    def inbackground(self, *, show=True, timeout=10):
        show = show if show is not None else self.show
        try:
            self.process = self.start()
            self.thread = self._create_thread(
                target=self.streamlines, show=show, timeout=timeout,
            )
            self.thread.start()
            yield self
        finally:
            self.thread.join(timeout) if self.thread else None

    @wraps(inbackground)
    def inbg(self, *, show=False, timeout=10):
        show = show if show is not None else self.show
        with self.inbackground(show=show, timeout=timeout) as lines:
            yield from lines

    def expect(self, show=None) -> str | None:
        show = show if show is not None else self.show
        stream = self.getorstart()
        if not stream:
            raise ValueError("No process to read from")
        status = -1
        try:
            status = stream.expect(
                [EOF, TIMEOUT], timeout=10,
            )
        except Exception:
            # traceback.print_exc() if not e else None
            logging.error(f"status: {status}, line:{self.process.before}")
        if  status not in (0, 1):
            logging.error(f"status: {status}, line:{self.process.before}")


        if not self.process.before:
            return None
        line = self.process.before.decode("utf-8")
        if show:
            SPINNER.stop()
            console.print(Text.from_ansi(line.rstrip("\n")))
        return line

    def streamlines(self, *, show=None) -> Iterator[str]:
        while True:
            try:
                line = self.expect(show=show)
                if line is not None:
                    break
                yield line
            except (EOF,TIMEOUT,KeyboardInterrupt):
                break
 

    def readlines(self, *, show=None) -> list[str]:
        show = show if show is not None else self.show
        self.process = self.start()
        self.started = time()
        return list(self.streamlines(show=show))


    def readtext(self, *, show=None) -> str:
        lines = self.readlines(show=show)
        return "\n".join([str(Text.from_ansi(line.rstrip("\n"))) for line in lines])

    def __iter__(self):
        yield from self.streamlines()

 
    def __str__(self):
        return self.readtext()

    def __enter__(self):
        return self.readtext()

    def __exit__(self, exc_type, exc_val, exc_tb):
        for thread in self._threads:
            with suppress(Exception):
                thread.join(timeout=1)
        if self.process:
            self.process.close()


console = Console(force_terminal=True)

class AsyncCommandCtx(
    CommandBase[AExpectT],
):
    """A context manager for asynchronous command execution using pexpect-like interfaces.

    Attributes:
        process_type (Type[AExpectT]): The type of the process to manage.
        aprocess (Optional[AExpectT]): The asynchronous process instance.
        _signalstatus (bool): Internal flag to manage signaling.
    """
    process_type: type[aspawn] # type: ignore

    async def __aiter__(self) -> AsyncIterator[str]:
        """Asynchronous iterator to yield lines from the process.

        Yields:
            AsyncIterator[str]: Lines from the asynchronous process.
        """
        async for line in self.astreamlines():
            yield line

    async def areadtext(self, show: bool|None=None) -> str:
        """Reads all lines from the asynchronous process and concatenates them into a single string.

        Args:
            show (Optional[bool]): Whether to display the lines as they are read.

        Returns:
            str: The concatenated text from the process.
        """
        lines = []
        async for line in self.astreamlines(show=show):
            SPINNER.stop()
            lines.append(line.rstrip("\n"))
        return "\n".join(lines)
            

    async def astreamlines(self,show:bool|None=None) -> AsyncIterator[str]:
        """Asynchronously streams lines from the process.

        Args:
            show (Optional[bool]): Whether to display the lines as they are read.

        Yields:
            AsyncIterator[str]: Lines from the asynchronous process.
        """
        show = show if show is not None else getattr(self, "show", False)
        while not self.signaled:
            try:
                line = await self.aexpect(show=show)
                if not line:
                    break
                logging.debug(f"astream line: {line}")
                yield line
            except (EOF, TIMEOUT, KeyboardInterrupt):
                logging.debug("EOF reached in astreamlines")
                break

    async def aexpect(self, show: bool  | None = None)  -> str | NoneType:
        """Awaits an expectation from the process.

        Args:
            show (Optional[bool]): Whether to display the line as it's read.

        Returns:
            Optional[str]: The line read from the process, or None.
        """
        show = show if show is not None else getattr(self, "show", False)
        stream: AExpectT = self.getorstart()
        if not stream:
            raise ValueError("No process to read from")
        try:
            async for status in stream.aexpect([ EOF, TIMEOUT], timeout=10):

                if status not in (0, 1,2):
                    SPINNER.stop()
                    logging.error(f"Unexpected status: {status}, line: {stream.before}")

                try:
                    line = cast(bytes,stream.before).decode("utf-8")
                except AttributeError:
                    line = str(stream.before)
                if show:
                    SPINNER.stop()
                    console.print(Text.from_ansi(line.rstrip("\n")))
                return line
        except PexpectException as e:
            # Log the exception
            traceback.print_exc()
            logging.error(f"Exception during aexpect: {e}")
            SPINNER.stop()
            return None


    async def areadlines(self,show: bool | None = None) -> list[str]:
        """Asynchronously reads all lines from the process.

        Args:
            show (Optional[bool]): Whether to display the lines as they are read.

        Returns:
            List[str]: A list of lines read from the process.
        """
        show = show if show is not None else getattr(self, "show", False)
        self.started = time()
        self.process = self.getorstart()
        lines: list[str] = []
        async for line in self.astreamlines(show=show):
            lines.append(line)
        logging.debug("Finished areadlines")
        return lines

    async def readtext(self,show: bool  | None = None) -> str:
        """Asynchronously reads all lines from the process and concatenates them into a single string.

        Args:
            show (Optional[bool]): Whether to display the lines as they are read.

        Returns:
            str: The concatenated text from the process.
        """
        try:
            return "\n".join([str(Text.from_ansi(line.rstrip("\n"))) for line in await self.areadlines(show)])
        except RuntimeError as e:
            raise e

PtyCommand = CommandCtx[spawn]
AsyncPtyCommand = AsyncCommandCtx[aspawn]


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, force=True)
    async def main() -> None:
        async for _line in AsyncPtyCommand("ls").astreamlines(True):
            pass
    
    asyncio.run(main())
        