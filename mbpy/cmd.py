from __future__ import annotations
from collections.abc import Iterable
import sys
from mbpy.import_utils import smart_import
from typing import TYPE_CHECKING


from mbpy.expect.spawnbase import SpawnBase
from mbpy.expect.expect import Expecter
from mbpy.expect.asyncspawn import AsyncSpawn
if TYPE_CHECKING:
    from mbpy.helpers._cmd import Command, AsyncCommand
    from typing import Any, Generator, Optional, Tuple, Union, AsyncGenerator
    from pathlib import Path
    from more_itertools import collapse


async def run_command(
    command: str,
    cwd: str | None = None,
    timeout: int = 10,
    *,
    show=False,
) -> str:
    spawn = Spawn(command, cwd=cwd)
    await spawn.start()
    expecter = Expecter(spawn, [r".*"])
    output = []
    try:
        while spawn.is_running():
            index, data = await expecter.expect(timeout=timeout)
            output.append(data)
            if show:
                print(data, end='')
        return ''.join(output)
    finally:
        await spawn.terminate()

def as_exec_args(cmd: str | list[str]) -> tuple[str, list[str]]:
    shlex = smart_import("shlex")

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


async def arun_command(
    command: str | list[str] | tuple[str, list[str]],
    cwd: str | None = None,
    *,
    show=False,
) -> AsyncGenerator[str, None]:
    """Run command and yield output lines."""
    collapse = smart_import("more_itertools.collapse")
    AsyncSpawn = smart_import("mbpy.expect.asyncspawn.AsyncSpawn")
    SPINNER = smart_import("mbpy.helpers._display.SPINNER")()
    console = smart_import("mbpy.helpers._display.getconsole")()
    async with AsyncSpawn(" ".join(collapse([command], str)),
                          cwd=cwd,
                          show=show) as p:
        async for line in p.streamlines():
            SPINNER.stop()
            yield line



def run(
    command: str | list[str],
    cwd: str | None = None,
    timeout: int = 10,
    *,
    show=True,
) -> str:
    """Run command and return output as a string."""
    if not TYPE_CHECKING:
        Command = smart_import("mbpy.helpers._cmd.Command")
    collapse = smart_import("more_itertools.collapse")
    return Command(" ".join(collapse([command], str)), cwd=cwd, show=show).readtext()

async def arun(cmd: str | list[str], show=False, shell=True, **kwargs) -> str:
    """Run a command asynchronously and return its output."""
    shlex = smart_import("shlex")
    # Properly quote/escape the command
    if not shell:
        try:
            # Test if command can be split properly
            shlex.split(cmd) if isinstance(cmd, str) else cmd
        except ValueError:
            # If splitting fails, use shell mode
            shell = True
    async with AsyncSpawn(cmd, show=show, shell=shell, **kwargs) as proc:
        return await proc.readtext()

# Usage example:
async def check_repo(repo: str) -> bool:
    try:
        output = await arun(f"gh repo view {repo} --json name")
        return True
    except RuntimeError:
        return False

def sigwinch_passthrough(sig, data, p:"Process") -> None:
    """Signal handler for window size change."""
    import struct

    if sys.platform != "win32":
        from fcntl import ioctl


        s = struct.pack("HHHH", 0, 0, 0, 0)
        a = struct.unpack("hhhh", ioctl(s))
        if not p.closed:
            p.setwinsize(a[0], a[1])





def contains_exec(cmd: list[str] | str) -> bool:
    """Check if command contains an executable."""
    shlex = smart_import("shlex")
    Path = smart_import("pathlib.Path")
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    return any(Path(i).exists() for i in cmd)


def resolve(cmd: list[str] | str) -> list[str]:
    """Resolve commands to their full path."""
    Path = smart_import("pathlib.Path")
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


def run_local(
    cmd: str | list[str],
    args,
    *,
    interact=False,
    cwd=None,
    timeout=10,
    show=True,
    **kwargs,
) -> " Generator[str, str, None]":
    """Run command, yield single response, and close."""
    PtyCommand = smart_import("mbpy.helpers._cmd.Command")
    EOF = smart_import("mbpy.helpers._cmd.EOF")
    signal = smart_import("signal")
    console = smart_import("mbpy.helpers._display.console")()
    collapse = smart_import("more_itertools").collapse
    partial = smart_import("functools").partial
    Text = smart_import("rich.text").Text
    cast = smart_import("typing").cast
    if interact:
        cmd = " ".join(collapse(cmd, str)) if not isinstance(cmd, str) else cmd
        p = PtyCommand(cmd, cwd=cwd, timeout=timeout, **kwargs)
        signal.signal(signal.SIGWINCH, partial(sigwinch_passthrough, p=p))
        p.process.interact()
        if response := p.process.before:
            response = response.decode() if isinstance(response, bytes) else response
        else:
            return
        response = cast(str, response)
        console = smart_import("mbpy.helpers._display.console")()
        console.print(Text.from_ansi(response.decode())) if show else None
        yield response
    else:
        p = PtyCommand(" ".join(collapse([cmd], str)), cwd=cwd, timeout=timeout, **kwargs)
        p.process.expect(EOF, timeout=10)
        if response := p.process.before:
            response = response.decode() if isinstance(response, bytes) else response
            response = cast(str, response)
            console.print(Text.from_ansi(response)) if show else None
            yield response
        else:
            return
        p.process.close()
    p.process.close() if p else None
    return


def interact(
    cmd: "str | Iterable[str] | tuple[str, list[str]]",
    *,
    cwd: str | None = None,
    timeout: int = 10,
    show: bool = True,
    **kwargs,
) -> "Generator[str, str, None]":
    """Run comand, recieve output and wait for user input.

    Example:
    >>> terminal = commands.interact("Choose an option", choices=[str(i) for i in range(1, len(results) + 1)] + ["q"])
    >>> choice = next(terminal)
    >>> choice.terminal.send("exit")

    """
    collapse = smart_import("more_itertools").collapse
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

async def arun_local(
    cmd: str | list[str],
    args,
    *,
    interact=False,
    cwd=None,
    show=True,
    **kwargs,
) -> "AsyncGenerator[str, str]":
    """Run command, yield single response, and close."""
    asyncio = smart_import("asyncio")
    for resp in await asyncio.to_thread(
        run_local,
        cmd,
        args,
        interact=interact,
        cwd=cwd,
        show=show,
        **kwargs,
    ):
        yield resp


async def ainteract(
    cmd: str | list[str],
    *,
    cwd: str | None = None,
    show: bool = True,
    **kwargs,
) ->"AsyncGenerator[str, str]":
    """Run comand, recieve output and wait for user input."""

    usr_input = cmd
    repl = arun_local(*as_exec_args(cmd), interact=True, cwd=cwd, show=show, **kwargs)
    async for msg in repl:
        if msg.strip() == "EOF":
            break
        yield msg
        usr_input = yield "> "
        async for resp in arun_local(*as_exec_args(usr_input), interact=False, cwd=cwd, show=show, **kwargs):
            yield resp




if __name__ == "__main__":
    import doctest

    doctest.testmod()
