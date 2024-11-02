from __future__ import annotations

import fcntl
import logging
import sys
import termios
from contextlib import contextmanager
from functools import partial, wraps
from pathlib import Path
from threading import Thread
from time import time
from typing import Callable, Generic, Iterator, TypeAlias, TypeVar

from rich.console import Console
from rich.pretty import Text
from typing_extensions import ParamSpec

P = ParamSpec("P")
R = TypeVar("R", bound=str | Iterator[str])
T = TypeVar("T", bound="pexpect.spawn")

console = Console(force_terminal=True)
if sys.platform == "win32":
    import mbpy.poexpect as pexpect

    pexpect.socket_pexpect = pexpect.Expecter

    pexpect.spawnbase = pexpect.spawnbase
    PexpectClass = pexpect.spawn


else:
    import fcntl
    import termios

    import pexpect
    import pexpect.popen_spawn
    import pexpect.socket_pexpect
    import pexpect.spawnbase

    PexpectClass = pexpect.spawn
    pexpect_module = pexpect
    IOCTL = partial(fcntl.ioctl, sys.stdout.fileno(), termios.TIOCGWINSZ)


PexpectT = TypeVar("PexpectClass", bound=PexpectClass)


class NewCommandContext(Generic[PexpectT]):
    process_type: PexpectT

    def __init__(
        self,
        command: str | Callable[P, R] | PexpectT,
        args: list[str] | None = None,
        timeout=20,
        cwd=None,
        *,
        show=False,
        **kwargs,
    ):
        self.show = show
        if callable(command):
            self.callable_command_no_log = partial(command, args=args, timeout=timeout, cwd=cwd, **kwargs)
        else:
            self.callable_command_no_log = partial(
                self.process_type, command, args=args, timeout=timeout, cwd=cwd, encoding="utf-8", **kwargs
            )
        cwd = Path(str(cwd)).resolve() if cwd else Path.cwd()
        self.cwd = cwd if cwd.is_dir() else cwd.parent if cwd.exists() else Path.cwd()
        self.timeout = timeout
        self.process = None
        self.output = []
        self.started = 0
        self.thread = None
        self.lines = []
        self.show = show
        logging.debug(f"{command=} {args=}, {timeout=}, {cwd=}, {kwargs=}")
        logging.debug(f"self: {self=}, {self.cwd=}")

    def __class_getitem__(cls, item):
        cls.process_type = item
        return cls

    def start(self) -> PexpectT:
        self.process: PexpectT = self.callable_command_no_log()
        self.started = time()
        return self.process

    def __contains__(self, item):
        return item in " ".join(self.lines)

    @contextmanager
    def inbackground(self,*, show=True, timeout=10):
        show = show if show is not None else self.show
        try:
            self.start()
            self.thread = Thread(target=self.streamlines, daemon=True, kwargs={"show": show})
            yield self
        finally:
            self.thread.join(timeout) if self.thread else None

    @wraps(inbackground)
    def inbg(self, *,show=False, timeout=10):
        show = show if show is not None else self.show
        yield from self.inbackground(show=show, timeout=timeout)

    def streamlines(self, *, show=None) -> Iterator[str]:
        show = show if show is not None else self.show
        stream = self.process or self.start()
        while True:
            try:
                line = stream.readline()
            except type(self).process_type.EOF:
                yield self.process.before
                return
            if not line:
                break
            line = Text.from_ansi(line)
            if line:
                self.lines.append(str(line))
                if show:
                    console.print(line)
                yield str(line)

    def __class_getitem__(cls, item: PexpectT):
        cls.process_type = item
        return cls

    def readlines(self, *, show=None) -> str:
        show = show if show is not None else self.show
        self.process = self.start()
        self.started = time()
        lines = list(self.streamlines(show=show))

        return "\n".join(lines)

    def __iter__(self):
        yield from self.streamlines()

    def __str__(self):
        return self.readlines()

    def __enter__(self):
        return self.readlines()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.process and self.process.isalive():
            self.process.terminate()
        if self.process:
            self.process.close()


console = Console(force_terminal=True)



PtyCommand = NewCommandContext[PexpectClass]


