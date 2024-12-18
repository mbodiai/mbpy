from __future__ import annotations

import asyncio
import logging
import shlex
import signal
import struct
import traceback
from collections.abc import Generator, Iterator
from functools import partial
from pathlib import Path
from typing import (
    AsyncGenerator,
    Literal,
    Never,
    Protocol,
    Sequence,
    TypeVar,
    overload,
    runtime_checkable,
)

import rich_click as click
from more_itertools import collapse
from rich.text import Text

from mbpy.context import suppress
from mbpy.utils.cmd_utils import EOF, IOCTL, AsyncPtyCommand, PtyCommand, console, pexpect_module


@click.command()
@click.argument("command", nargs=-1, required=True, type=click.UNPROCESSED)
@click.option("--cwd", default=None, help="Current working directory")
@click.option("--timeout", default=10, help="Timeout for command")
@click.option("--no-show", default=False, is_flag=True, help="Show output")
@click.option(
    "-i", "--interactive", default=False, help="Interact with command.  Not supported on windows", is_flag=True,
)
@click.option("-d", "--debug", default=False, help="Debug mode", is_flag=True)
def cli(
    command: tuple[str, ...],
    cwd: str | None,
    timeout: int,
    no_show: bool,
    *,
    interactive: bool = False,
    debug: bool = False,
) -> None:
    if debug:
        logging.basicConfig(level=logging.DEBUG, force=True)
    if interactive:
        logging.debug(f"{command=}")
        chunks = ""
        gen = interact(command, cwd=cwd, timeout=timeout, show=not no_show)
        for chunk in gen:
            chunks += chunk
            console.print(chunks)
            gen.send(input())
    else:
        logging.debug(f"{command=}")
        with suppress(Exception) as e:
            for line in run_command(command, cwd=cwd, timeout=timeout, show=not no_show).streamlines():
                console.print(line)
        if e:
            pass


def run_command(
    command: str | list[str] | tuple[str, list[str]],
    cwd: str | None = None,
    timeout: int = 10,
    *,
    show=False,
) -> PtyCommand:
    """Run command and return PtyCommand object."""
    commands = shlex.split(command) if isinstance(command, str) else command
    if isinstance(commands, tuple):
        exec_, args = commands
    else:
        exec_, *args = commands
    return PtyCommand(exec_, args, cwd=cwd, timeout=timeout, show=show)


_T = TypeVar("_T")


@runtime_checkable
class ExecArgs(Protocol):
    def __len__(self) -> Literal[2]: ...

    @overload
    def __getitem__(self, idx: Literal[0]) -> str: ...
    @overload
    def __getitem__(self, idx: Literal[1]) -> list[str]: ...
    @overload
    def __getitem__(self, idx: int) -> Never | list[str] | str: ...
    @classmethod
    def supports(cls, c) -> bool:
        return isinstance(c, tuple) and len(c) == 2 and isinstance(c[0], str) and isinstance(c[1], str)


def arun_command(
    command: str | list[str] | tuple[str, list[str]],
    cwd: str | None = None,
    *,
    show=False,
) -> AsyncPtyCommand:
    """Run command and return PtyCommand object."""
    # exec_, args = as_exec_args(command) if not ExecArgs.supports(command) else command
    return AsyncPtyCommand(" ".join(collapse([command],str)), cwd=cwd, show=show)


def run(
    command: str | list[str],
    cwd: str | None = None,
    timeout: int = 10,
    *,
    show=True,
) -> str:
    """Run command and return output as a string."""
    return PtyCommand(" ".join(collapse([command], str)), cwd=cwd, show=show).readtext()


def as_exec_args(cmd: str | list[str]) -> tuple[str, list[str]]:
    cmd = " ".join(collapse(cmd, str)) if not isinstance(cmd, str) else cmd
    c = resolve(cmd)
    c = shlex.split(cmd) if isinstance(cmd, str) else cmd
    if isinstance(c, str):
        # Single string command, no arguments
        return c, []
    if isinstance(c, list):
        # First item is the executable, the rest are arguments
        return c[0], c[1:]
    if isinstance(c, tuple) and len(c) == 2 and isinstance(c[1], list):
        return c
    raise TypeError("Invalid command format")


async def arun(
    command: str | list[str],
    cwd: str | None = None,
    *,
    show=True,
) -> str:
    """Run command and return output as a string."""
    try:
        return await arun_command(command, cwd=cwd, show=show).areadtext()
    except KeyboardInterrupt:
        console.print("\nOperation aborted by user.", style="bold yellow")
    except Exception as e:
        console.print(f"Error: {e}", style="bold red")
        traceback.print_exc()

        return ""
    finally:
        return ""


def sigwinch_passthrough(sig, data, p) -> None:
    s = struct.pack("HHHH", 0, 0, 0, 0)
    a = struct.unpack("hhhh", IOCTL(s))
    if not p.closed:
        p.setwinsize(a[0], a[1])


def run_local(
    cmd: str | list[str],
    args,
    *,
    interact=False,
    cwd=None,
    timeout=10,
    show=True,
    **kwargs,
) -> Iterator[str]:
    """Run command, yield single response, and close."""
    if interact:
        cmd = " ".join(collapse(cmd, str)) if not isinstance(cmd, str) else cmd
        p = pexpect_module.spawn(cmd, args, timeout=timeout, cwd=cwd, **kwargs)
        signal.signal(signal.SIGWINCH, partial(sigwinch_passthrough, p=p))
        p.interact()
        if response := p.before:
            response = response.decode()
        else:
            return

        console.print(Text.from_ansi(response)) if show else None
        yield response
    else:
        p: pexpect_module.spawn = pexpect_module.spawn(cmd, args, **kwargs)
        p.expect(EOF, timeout=10)
        if response := p.before:
            response = response.decode()
            console.print(Text.from_ansi(response)) if show else None
            yield response
        else:
            return
        p.close()
    p.close() if p else None
    return


async def arun_local(
    cmd: str | list[str],
    args,
    *,
    interact=False,
    cwd=None,
    timeout=10,
    show=True,
    **kwargs,
) -> AsyncGenerator[str, str]:
    for resp in await asyncio.to_thread(
        run_local, cmd, args, interact=interact, cwd=cwd, timeout=timeout, show=show, **kwargs,
    ):
        yield resp


def contains_exec(cmd: list[str] | str) -> bool:
    """Check if command contains an executable."""
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    return any(Path(i).exists() for i in cmd)


def resolve(cmd: list[str] | str) -> list[str]:
    """Resolve commands to their full path."""
    cmd = [cmd] if not isinstance(cmd, list) else cmd
    out = []
    for i in cmd:
        if i.startswith("~"):
            out.append(str(Path(i).expanduser().resolve()))
        elif i.startswith("."):
            out.append(str(Path(i).resolve()))
        else:
            out.append(i)
    return out


def interact(
    cmd: str | Sequence[str] | tuple[str, list[str]],
    *,
    cwd: str | None = None,
    timeout: int = 10,
    show: bool = True,
    **kwargs,
) -> Generator[str, str, None]:
    """Run comand, recieve output and wait for user input.

    Example:
    >>> terminal = commands.interact("Choose an option", choices=[str(i) for i in range(1, len(results) + 1)] + ["q"])
    >>> choice = next(terminal)
    >>> choice.terminal.send("exit")

    """
    usr_input = cmd
    repl = run_local(
        *as_exec_args(cmd),
        interact=True,
        cwd=cwd,
        timeout=timeout,
        show=show,
        **kwargs,
    )
    msg = next(repl)
    while usr_input not in ("exit", "quit", "q"):
        while (msg := next(repl)) != "EOF":
            yield msg
        usr_input = yield "> "
        msg = repl.send(" ".join(list(*collapse(as_exec_args(usr_input)))))


async def ainteract(
    cmd: str | list[str],
    *,
    cwd: str | None = None,
    show: bool = True,
    **kwargs,
) -> AsyncGenerator[str, str]:
    usr_input = cmd
    repl = arun_local(*as_exec_args(cmd), interact=True, cwd=cwd, show=show, **kwargs)
    async for msg in repl:
        if msg.strip() == "EOF":
            break
        yield msg
        usr_input = yield "> "
        async for resp in arun_local(*as_exec_args(usr_input), interact=False, cwd=cwd, show=show, **kwargs):
            yield resp


def main() -> None:
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\nOperation aborted by user.", style="bold yellow")


if __name__ == "__main__":
    main()
