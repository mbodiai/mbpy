from __future__ import annotations

import argparse
import asyncio
import atexit
import fcntl
import inspect
import io
import json
import logging
import os
import random
import shlex
import signal
import socket
import struct
import sys
import termios
from abc import abstractmethod
from contextlib import contextmanager
from functools import partial, wraps
from pathlib import Path
from threading import Thread
from time import time
from typing import Callable, Generic, Iterator, TypeVar

import pexpect
import pexpect.socket_pexpect
import pexpect.spawnbase
from rich.console import Console
from rich.pretty import Text
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from typing_extensions import ParamSpec

P = ParamSpec("P")
R = TypeVar("R", bound=str | Iterator[str])
T = TypeVar("T", bound="pexpect.spawn")

console = Console(force_terminal=True)
class NewCommandContext(Generic[T]):
    process_type: T

    def __init__(self, command: str | Callable[P,R] | T, args : list[str] | None = None, timeout=20, cwd=None, show=False, **kwargs):
        self.show = show
        if callable(command):
            self.callable_command_no_log = partial(command, args=args, timeout=timeout, cwd=cwd, **kwargs)
        else:
            self.callable_command_no_log = partial(self.process_type, command, args=args, timeout=timeout, cwd=cwd, **kwargs)
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

    def start(self) -> T:
        self.process: T = self.callable_command_no_log()
        self.started = time()
        return self.process

    def __contains__(self, item):
        return item in " ".join(self.lines)

    @contextmanager
    def inbackground(self, show=True, timeout=10):
        show = show if show is not None else self.show
        try:
            self.start()
            self.thread = Thread(target=self.streamlines, daemon=True, kwargs={"show": show})
            yield self
        finally:
            self.thread.join(timeout) if self.thread else None

    @wraps(inbackground)
    def inbg(self, show=False, timeout=10):
        show = show if show is not None else self.show
        yield from self.inbackground(show=show, timeout=timeout)


    def streamlines(self, *, show=False) -> Iterator[str]:
        show = show if show is not None else self.show
        stream = self.process or self.start()
        while True:
            line = stream.readline()
            if not line:
                break
            line = str(Text.from_ansi(line.decode("utf-8")))
            if line:
                self.lines.append(line)
                if show:
                    console.print(line)
                yield line


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


class PtyCommand(NewCommandContext[pexpect.spawn]):
    def streamlines(self, *, show=False) -> Iterator[str]:
        show = show if show is not None else self.show
        stream = self.process or self.start()
        while True:
            line = stream.readline()
            if not line:
                break
            line = Text.from_ansi(line.decode("utf-8"))
            if line:
                self.lines.append(str(line))
                if show:
                    console.print(str(line))
                yield str(line)






# def cli(func):
#     """Decorator to automatically turn a function into a command-line interface (CLI).

#     It inspects the function signature, generates arguments, and displays help docs
#     using `rich` for enhanced visuals.
#     """

#     @wraps(func)
#     def wrapper(*args, **kwargs):
#         # Get function signature and docstring
#         sig = inspect.signature(func)
#         params = sig.parameters
#         func_doc = func.__doc__ or "No documentation provided"

#         # Initialize argparse and add global arguments
#         parser = argparse.ArgumentParser(
#             description=Panel(f"[bold blue]{func_doc}[/bold blue]", expand=False),
#             formatter_class=argparse.RawTextHelpFormatter,
#         )

#         # Get type hints from the function
#         type_hints = get_type_hints(func)

#         # Dynamically create CLI arguments based on function parameters
#         for name, param in params.items():
#             param_type = type_hints.get(name, str)  # Default to str if no type hint is provided
#             default = param.default if param.default != param.empty else None
#             if default is None:
#                 parser.add_argument(name, type=param_type, help=f"{name} (required)")
#             else:
#                 parser.add_argument(f"--{name}", type=param_type, default=default, help=f"{name} (default: {default})")

#         # Parse command-line arguments
#         parsed_args = vars(parser.parse_args())

#         # Call the wrapped function with the parsed arguments
#         result = func(**parsed_args)

#         # Pretty print result based on type
#         if isinstance(result, dict):
#             print_json(data=json.dumps(result))
#         elif isinstance(result, list):
#             table = Table(title="Result List", box="SIMPLE")
#             for i, item in enumerate(result, start=1):
#                 table.add_row(str(i), str(item))
#             console.print(table)
#         elif result is not None:
#             console.print(result)

#     return wrapper
import rich_click  as click

@click.command()
@click.argument("command", nargs=-1, required=True)
@click.option("--cwd", default=None, help="Current working directory")
@click.option("--timeout", default=10, help="Timeout for command")
@click.option("--no-show", default=False, is_flag=True, help="Show output")
@click.option("-i", "--interactive", default=False, help="Interact with command", is_flag=True)
@click.option("-d","--debug", default=False, help="Debug mode", is_flag=True)
def cli(command, cwd, timeout, no_show, interactive: bool = False, debug: bool = False):
    if interactive:
        logging.debug(f"{command=}")
        interact(command, cwd=cwd, timeout=timeout, show=not no_show)
    else:
        logging.debug(f"{command=}")
        run(command, cwd=cwd, timeout=timeout, show=not no_show)

def run_command_background(
    command: str | list[str],
    cwd: str | None = None,
    timeout: int = 10,
    debug=False,
):
    exec_, *args = command if isinstance(command, list) else command.split()
    proc = PtyCommand(exec_, args, cwd=cwd, timeout=timeout, echo=False)
    return proc.inbackground()


def run_command_remote(
    command: str | list[str],
    host: str,
    port: int,
    timeout: int = 10,
    recv_port: int = 5331,
    *,
    show=False,
):
    exec_, *args = command if isinstance(command, list) else command.split()
    return NewCommandContext[pexpect.socket_pexpect.SocketSpawn](
        exec_,
        args,
        timeout=timeout,
        socket=socket.create_connection((host, port), timeout=timeout, source_address=("0.0.0.0", recv_port)),
        show=show,
    )


def run_command_stream(
    command: str | list[str],
    cwd: str | None = None,
    timeout: int = 10,
    *,
    show=False,
):
    exec_, *args = command if isinstance(command, list) else command.split()
    proc = PtyCommand(exec_, args, cwd=cwd, timeout=timeout, echo=False, show=True)
    yield from proc.streamlines()


def run_command(
    command: str | list[str] | tuple[str, list[str]],
    cwd: str | None = None,
    timeout: int = 10,
    *,
    show=True,
) -> PtyCommand:
    """Run command and return PtyCommand object."""
    commands = shlex.split(command) if isinstance(command, str) else command
    if isinstance(commands, tuple):
        exec_, args = commands
    else:
        exec_, *args = commands
    return PtyCommand(exec_, args, cwd=cwd, timeout=timeout, show=show)

def run(
    command: str | list[str],
    cwd: str | None = None,
    timeout: int = 10,
    *,
    show=True,
) -> str:
    """Run command and return output as a string."""
    return run_command(as_exec_args(command), cwd=cwd, timeout=timeout, show=show).readlines()


def sigwinch_passthrough(sig, data, p: pexpect.spawn):
    s = struct.pack("HHHH", 0, 0, 0, 0)
    a = struct.unpack("hhhh", fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, s))
    if not p.closed:
        p.setwinsize(a[0], a[1])


def run_local(
    cmd,
    args,
    *,
    interact=False,
    cwd=None,
    show=True,
    timeout=10,
    **kwargs,
) -> Iterator[str]:
    """Run command, yield single response, and close."""
    if interact:
        p = pexpect.spawn(cmd, args, timeout=timeout, cwd=cwd, **kwargs)
        signal.signal(signal.SIGWINCH, partial(sigwinch_passthrough, p=p))
        p.interact()
        if response := p.before:
            response = str(Text.from_ansi(response) + "\n")
        else:
            return
        if show:
            console.print(response)
        yield response
    else:
        p: pexpect.spawn = pexpect.spawn(cmd, args, **kwargs)
        p.expect(pexpect.EOF, timeout=10)
        if response := p.before:
            response = str(Text.from_ansi(response) + "\n")
            if show:
                console.print(response)
            yield response
        else:
            return
        p.close()
    return


def contains_exec(cmd: list[str] | str) -> bool:
    """Check if command contains an executable."""
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    return any(Path(i).exists() for i in cmd)

def resolve(cmd: list[str]) -> list[str]:
    """Resolve commands to their full path."""
    out = []
    for i in cmd:
        if i.startswith("~"):
            out.append(str(Path(i).expanduser().resolve()))
        elif i.startswith("."):
            out.append(str(Path(i).resolve()))
        else:
            out.append(i)
    return out

def as_exec_args(cmd: str | list[str]) -> tuple[str, list[str]]:
    c = shlex.split(cmd) if isinstance(cmd, str) else cmd
    c = resolve(c)
    if not contains_exec(c):
        return os.getenv("SHELL", "bash"), ["-c", " ".join(c)]
    return c[0], c[1:]

def interact(
    cmd: str | list[str],
    *,
    cwd: str | None = None,
    timeout: int = 10,
    show: bool = True,
    **kwargs,
):
    """Run comand, recieve output and wait for user input.

    Example:
    >>> terminal = commands.interact("Choose an option", choices=[str(i) for i in range(1, len(results) + 1)] + ['q'])
    >>> choice = next(terminal)
    >>> choice.terminal.send("exit")

    """
    print(f"{cmd=}")
    while cmd != "exit":
        cmd = run_local(*as_exec_args(cmd), **kwargs, interact=True, cwd=cwd, timeout=timeout, show=show)
        for response in cmd:
            cmd = yield response
    return

def progress(query: str):
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.syntax import Syntax
    from rich.table import Table

    syntax = Syntax(
        '''def loop_last(values: Iterable[T]) -> Iterable[Tuple[bool, T]]:
    """Iterate and generate a tuple with a flag for last value."""
    iter_values = iter(values)
    try:
        previous_value = next(iter_values)
    except StopIteration:
        return
    for value in iter_values:
        yield False, previous_value
        previous_value = value
    yield True, previous_value''',
        "python",
        line_numbers=True,
    )

    table = Table("foo", "bar", "baz")
    table.add_row("1", "2", "3")

    progress_renderables = [
        "Text may be printed while the progress bars are rendering.",
        Panel("In fact, [i]any[/i] renderable will work"),
        "Such as [magenta]tables[/]...",
        table,
        "Pretty printed structures...",
        {"type": "example", "text": "Pretty printed"},
        "Syntax...",
        syntax,
        Rule("Give it a try!"),
    ]

    from itertools import cycle

    examples = cycle(progress_renderables)

    console = Console(record=True)

    with Progress(
        SpinnerColumn(),
        *Progress.get_default_columns(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task1 = progress.add_task("[red]Downloading", total=1000)
        task2 = progress.add_task("[green]Processing", total=1000)
        task3 = progress.add_task("[yellow]Thinking", total=None)

        while not progress.finished:
            progress.update(task1, advance=0.5)
            progress.update(task2, advance=0.3)
            time.sleep(0.01)
            if random.randint(0, 100) < 1:  # noqa
                progress.log(next(examples))


def main():
    cli()


if __name__ == "__main__":
    main()
