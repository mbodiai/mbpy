from __future__ import annotations

import argparse
import asyncio
import atexit
import fcntl
import inspect
import io
import json
import logging
import random
import signal
import socket
import struct
import sys
import tempfile
import termios
import traceback
from abc import abstractmethod
from contextlib import _GeneratorContextManager, contextmanager
from contextvars import Context
from functools import partial, wraps
from pathlib import Path
from pprint import pprint
from subprocess import PIPE
from threading import Thread
from time import time
from typing import Annotated, Any, Generic, Iterator, Literal, Optional, TypeVar, Union, get_type_hints

import configargparse
import pexpect
import pexpect.socket_pexpect
import pexpect.spawnbase
from aiostream.pipe import map, merge
from more_itertools import iterate
from pexpect import EOF, TIMEOUT
from pexpect.spawnbase import SpawnBase
from rich import box, print_json
from rich.pretty import Text
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from rich.table import Table
from typer import Typer, echo_via_pager
from typer.core import TyperArgument, TyperOption

app = Typer()
T = TypeVar("T", bound="PexpectCommand")


class NewCommandContext(Generic[T]):
    process_type: T
    def __init__(self, command,args=None, timeout=10, cwd=None, show=False, **callable_kwargs):
        if callable(command):
            self.callable_command_no_log = partial(command, args=args, timeout=timeout, cwd=cwd)
        elif isinstance(command, list):
            command, *args = command
            self.callable_command_no_log = partial(self.process_type,command,args=args, timeout=timeout, cwd=cwd)
        elif isinstance(command, str):
            # if not any(c in command for c in ["bash", "sh", "zsh", "fish", "powershell"]):
            #     command = f"bash"

            self.callable_command_no_log = partial(self.process_type, command, args, timeout=timeout, cwd=cwd)
        cwd = Path(str(cwd)).resolve() if cwd else Path.cwd()
        self.cwd = cwd if cwd.is_dir() else cwd.parent if cwd.exists() else Path.cwd()
        self.timeout = timeout
        self.process = None
        self.output = []
        self.started = 0
        self.thread = None
        self.lines = []
        self.show = show
        print(f"Command: {command} {args=}, {timeout=}, {cwd=}, {callable_kwargs=}")
        print(f"self: {self=}, {self.cwd=}")
    
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
        show = show or self.show
        try:
            self.start()
            self.thread = Thread(target=self.streamlines, daemon=True, kwargs={"show": show})
            yield self
        finally:
            self.thread.join(timeout) if self.thread else None

    @wraps(inbackground)
    def inbg(self, show=False, timeout=10):
        show = show or self.show
        yield from self.inbackground(show=show, timeout=timeout)




    @abstractmethod
    def streamlines(self, show=False) -> Iterator[str]:
        show = show or self.show
        raise NotImplementedError

    def readlines(self, show=False) -> str:
        self.process = self.start()
        self.started = time()
        list(self.streamlines(show))

        return "\n".join(self.lines)

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
        def streamlines(self, show=True):
            stream = self.process or self.start()
            while True:
                
                line = stream.readline()  # Read as bytes, not str yet
                if not line:
                    break
                line = str(Text.from_ansi(line.decode("utf-8")))
                if line:
                    self.lines.append(line)
                    if show:
                        print(line)
                    yield line


console = Console(force_terminal=True)


def cli(func):
    """Decorator to automatically turn a function into a command-line interface (CLI).

    It inspects the function signature, generates arguments, and displays help docs
    using `rich` for enhanced visuals.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Get function signature and docstring
        sig = inspect.signature(func)
        params = sig.parameters
        func_doc = func.__doc__ or "No documentation provided"

        # Initialize argparse and add global arguments
        parser = argparse.ArgumentParser(
            description=Panel(f"[bold blue]{func_doc}[/bold blue]", expand=False),
            formatter_class=argparse.RawTextHelpFormatter,
        )

        # Get type hints from the function
        type_hints = get_type_hints(func)

        # Dynamically create CLI arguments based on function parameters
        for name, param in params.items():
            param_type = type_hints.get(name, str)  # Default to str if no type hint is provided
            default = param.default if param.default != param.empty else None
            if default is None:
                parser.add_argument(name, type=param_type, help=f"{name} (required)")
            else:
                parser.add_argument(f"--{name}", type=param_type, default=default, help=f"{name} (default: {default})")

        # Parse command-line arguments
        parsed_args = vars(parser.parse_args())

        # Call the wrapped function with the parsed arguments
        result = func(**parsed_args)

        # Pretty print result based on type
        if isinstance(result, dict):
            print_json(data=json.dumps(result))
        elif isinstance(result, list):
            table = Table(title="Result List", box="SIMPLE")
            for i, item in enumerate(result, start=1):
                table.add_row(str(i), str(item))
            console.print(table)
        elif result is not None:
            console.print(result)

    return wrapper


# Initialize the Rich console
console = Console()


# Create an argument parser using argparse
def create_parser() -> configargparse.ArgumentParser:
    parser = configargparse.ArgumentParser(
        description="Rich CLI Tool Example", formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "-a",
        "--action",
        help="Choose an action:\n1. Run tests\n2. Display status\n3. Exit",
        type=int,
        choices=[1, 2, 3],
    )
    return parser


# Function to display a header using Rich
def display_header() -> None:
    console.print(Panel("[bold green]Welcome to the Rich CLI Tool Example![/bold green]", expand=False))


# Function to display a status table
def display_status() -> None:
    table = Table(title="System Status", box=box.SIMPLE)

    table.add_column("Component", justify="right", style="cyan", no_wrap=True)
    table.add_column("Status", style="magenta")

    table.add_row("Tests", "All Passed")
    table.add_row("Dependencies", "Up-to-date")
    table.add_row("Configuration", "Valid")

    console.print(table)


# Function to display test results using Rich
def run_tests():
    test_table = Table(title="Test Results", box=box.SIMPLE)
    test_table.add_column("Test", justify="right", style="bold cyan")
    test_table.add_column("Result", style="bold magenta")

    # Mocked test results
    test_table.add_row("test_assistant_consider", "[green]Passed[/green]")
    test_table.add_row("test_assistant_deconstruct", "[green]Passed[/green]")
    test_table.add_row("test_assistant_find_relevant_context", "[green]Passed[/green]")
    test_table.add_row("test_assistant_spawn_children", "[green]Passed[/green]")
    test_table.add_row("test_assistant_answer", "[green]Passed[/green]")

    console.print(test_table)





class TCPConnection(SpawnBase):
    """Works similarly to pexpect but uses a cross-platform Python socket API for TCP sockets."""

    def __init__(
        self,
        host: str,
        port: int,
        args=None,
        timeout=30,
        maxread=2000,
        searchwindowsize=None,
        logfile=None,
        encoding=None,
        codec_errors="strict",
        use_poll=False,
    ):
        """Initializes the TCP connection.

        :param host: The hostname or IP address to connect to.
        :param port: The port number for the TCP connection.
        :param timeout: The timeout for socket operations (in seconds).
        """
        self.args = None
        self.command = None
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(timeout)

        # Establish connection
        self.socket.connect((host, port))

        # Initialize the base class
        SpawnBase.__init__(
            self,
            timeout,
            maxread,
            searchwindowsize,
            encoding=encoding,
            codec_errors=codec_errors,
        )

        self.child_fd = self.socket.fileno()
        self.closed = False
        self.name = f"<TCP socket {host}:{port}>"
        self.use_poll = use_poll

    def close(self):
        """Close the socket connection."""
        if self.child_fd == -1:
            return

        self.flush()
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()
        self.child_fd = -1
        self.closed = True

    def isalive(self):
        """Check if the socket is still alive."""
        return self.socket.fileno() >= 0

    def send(self, s) -> int:
        """Send data through the TCP connection."""
        s = self._coerce_send_string(s)
        self._log(s, "send")

        b = self._encoder.encode(s, final=False)
        self.socket.sendall(b)
        return len(b)

    def sendline(self, s) -> int:
        """Send a line of text through the TCP connection."""
        s = self._coerce_send_string(s)
        return self.send(s + self.linesep)

    def write(self, s):
        """Write data through the TCP connection."""
        self.send(s)

    def writelines(self, sequence):
        """Write a sequence of lines through the TCP connection."""
        for s in sequence:
            self.write(s)

    @contextmanager
    def _timeout(self, timeout):
        """Set a temporary timeout for the socket."""
        saved_timeout = self.socket.gettimeout()
        try:
            self.socket.settimeout(timeout)
            yield
        finally:
            self.socket.settimeout(saved_timeout)

    def read_nonblocking(self, size=1, timeout=-1):
        """Read from the TCP connection without blocking.

        :param int size: Read at most *size* bytes.
        :param int timeout: Wait timeout seconds for file descriptor to be
            ready to read. When -1 (default), use self.timeout. When 0, poll.
        :return: String containing the bytes read.
        """
        if timeout == -1:
            timeout = self.timeout
        try:
            with self._timeout(timeout):
                s = self.socket.recv(size)
                if s == b"":
                    self.flag_eof = True
                    raise pexpect.EOF("Socket closed")
                return s
        except TimeoutError:
            raise TIMEOUT("Timeout exceeded.")



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
    show=False,
):
    exec_, *args = command if isinstance(command, list) else command.split()
    proc = TCPConnection(host, port, exec_, args, timeout=timeout)
    return proc.readlines()

def run_command_stream(
    command: str | list[str],
    cwd: str | None = None,
    timeout: int = 10,

):
    exec_, *args = command if isinstance(command, list) else command.split()
    proc = PtyCommand(exec_, args, cwd=cwd, timeout=timeout, echo=False, show=True)
    yield from proc.streamlines()

def run_command(
     command: str | list[str],
    cwd: str | None = None,
    timeout: int = 10,
    show=False,

):
    exec_, *args = command if isinstance(command, list) else command.split()
    proc = PtyCommand(exec_, args, cwd=cwd, timeout=timeout, echo=False, show=show)
    return proc


def run_command_old(
    command: Union[str, list[str]],
    cwd: str | None = None,
    mode: Literal["block_until_done", "stream", "background"] = "block_until_done",
    logfile=None,
    timeout: int = 10,
    debug=False,
    remote=False,
):
    """Run a command and yield the output line by line asynchronously."""
    if sys.flags.debug or debug:
        logging.basicConfig(level=logging.DEBUG, force=True)
        print("Debug logging enabled.")

    # Create logfile if not provided
    logfile = Path(logfile).open if logfile else tempfile.NamedTemporaryFile
    exec_, *args = command if isinstance(command, list) else command.split()
    print(f"Running command: {exec_} {' '.join([arg.strip() for arg in args])}")
    print(f"command: {exec_}".replace("\n", "newline"))

    process = pexpect.spawn(exec_, args, cwd=cwd)

    def read_stream(stream: pexpect.spawnbase.SpawnBase):
        while True:
            line = (
                stream.readline().decode("utf-8").strip().replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")
            )
            if line:
                yield line.decode().strip()
            else:
                break

    if mode == "block_until_done":
        process.expect(EOF, timeout=timeout)
        return process.before.decode()
    if mode == "stream":
        return read_stream(process)

    return process


def sigwinch_passthrough(sig, data, p):
    s = struct.pack("HHHH", 0, 0, 0, 0)
    a = struct.unpack("hhhh", fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, s))
    if not p.closed:
        p.setwinsize(a[0], a[1])


@app.command(no_args_is_help=True)
def run_cmd(
    cmd: Annotated[
        str,
        TyperArgument(
            type=list[str],
            param_decls=["cmd"],
            help="Command to run",
            nargs=-1,
        ),
    ],
    args: Annotated[
        str,
        TyperOption(
            param_decls=["-a", "--args"],
            help="Arguments to pass to the command",
            nargs=-1,
        ),
    ] = None,
    **kwargs,
):
    def _run_cmd(cmd, args, **kwargs):
        if "interact" in kwargs:
            p = pexpect.spawn(cmd, args, **kwargs)
            signal.signal(signal.SIGWINCH, partial(sigwinch_passthrough, p=p))
            p.interact()
        else:
            p = pexpect.spawn(cmd, args, **kwargs)
            p.expect(pexpect.EOF, timeout=10)
            print(p.before.decode())
            p.close()

    out = []
    for i in cmd.split():
        if i.startswith("~"):
            out.append(str(Path(i).expanduser().resolve()))
        elif i.startswith("."):
            out.append(str(Path(i).resolve()))
        else:
            out.append(i)
    if any(
        c in out[0]
        for c in ["cd", "ls", "pwd", "echo", "python", "bash", "sh", "zsh", "fish", "powershell", "cmd", "pwsh"]
    ):
        return _run_cmd(out[0], out[1:], **kwargs)
    return _run_cmd("bash", ["-c", *out], **kwargs)


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    no_args_is_help=True,
)
def interact(
    cmd: Annotated[
        str,
        TyperArgument(
            type=list[str],
            param_decls=["cmd"],
            help="Command to run in interactive mode",
            required=True,
            nargs=-1,
        ),
    ],
):
    run_cmd(cmd, interact=True)


@app.command()
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


if __name__ == "__main__":
    app()
