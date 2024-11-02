from __future__ import annotations

import importlib
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
from contextlib import contextmanager
from functools import partial, wraps
from pathlib import Path
from threading import Thread
from time import time
from typing import Callable, Generic, Iterator, TypeVar

import rich_click as click

from mbpy.utils import IOCTL, NewCommandContext, PtyCommand, console, pexpect_module


@click.command()
@click.argument("command", nargs=-1, required=True, type=click.UNPROCESSED)
@click.option("--cwd", default=None, help="Current working directory")
@click.option("--timeout", default=10, help="Timeout for command")
@click.option("--no-show", default=False, is_flag=True, help="Show output")
@click.option("-i", "--interactive", default=False, help="Interact with command.  Not supported on windows", is_flag=True)
@click.option("-d", "--debug", default=False, help="Debug mode", is_flag=True)
def cli(command, cwd, timeout, no_show, *,interactive: bool = False, debug: bool = False):
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
        run(command, cwd=cwd, timeout=timeout, show=not no_show)


def run_command_background(
    command: str | list[str],
    cwd: str | None = None,
    timeout: int = 10,
    debug=False,
):
    from mbpy.utils import PtyCommand
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
    return NewCommandContext[pexpect_module.socket_pexpect.SocketSpawn](
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
):
    exec_, *args = command if isinstance(command, list) else command.split()
    proc = PtyCommand(exec_, args, cwd=cwd, timeout=timeout, echo=False, show=True)
    yield from proc.streamlines()


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
    return PtyCommand(exec_, args, cwd=cwd, timeout=timeout, echo=False, show=show)


def run(
    command: str | list[str],
    cwd: str | None = None,
    timeout: int = 10,
    *,
    show=True,
) -> str:
    """Run command and return output as a string."""
    return PtyCommand(*as_exec_args(command), cwd=cwd, timeout=timeout, echo=False, show=show).readlines()



def sigwinch_passthrough(sig, data, p: pexpect_module.spawn):
    s = struct.pack("HHHH", 0, 0, 0, 0)
    a = struct.unpack("hhhh", IOCTL(s))
    if not p.closed:
        p.setwinsize(a[0], a[1])


def run_local(
    cmd,
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
        p = pexpect_module.spawn(cmd, args, timeout=timeout, cwd=cwd, **kwargs)
        signal.signal(signal.SIGWINCH, partial(sigwinch_passthrough, p=p))
        p.interact()
        if response := p.before:
            response = response.decode()
        else:
            return
        from rich.text import Text
        console.print(Text.from_ansi(response)) if show else None
        yield response
    else:
        p: pexpect_module.spawn = pexpect_module.spawn(cmd, args, **kwargs)
        p.expect(pexpect_module.EOF, timeout=10)
        if response := p.before:
            response = response.decode()
            console.print(Text.from_ansi(response)) if show else None
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
    # if not contains_exec(c):
    #     return os.getenv("SHELL", "bash"), ["-c",*c]
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
    >>> terminal = commands.interact("Choose an option", choices=[str(i) for i in range(1, len(results) + 1)] + ["q"])
    >>> choice = next(terminal)
    >>> choice.terminal.send("exit")

    """
    cmd = run_local(
        *as_exec_args(cmd),
        interact=True,
        cwd=cwd,
        timeout=timeout,
        show=show,
        **kwargs,
    )
    for response in cmd:
        cmd = yield response





def main() -> None:
    cli()


if __name__ == "__main__":
    main()
