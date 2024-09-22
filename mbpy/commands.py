from __future__ import annotations

import argparse
import asyncio
import atexit
import inspect
import io
import json
import logging
import socket
from subprocess import PIPE
import sys
import tempfile
import traceback
from contextlib import contextmanager
from contextvars import Context
from functools import partial, wraps
from pathlib import Path
from pprint import pprint
from threading import Thread
from time import time
from typing import Any, Generic, Iterator, Literal, Optional, TypeVar, Union, get_type_hints
import configargparse
import pexpect
import pexpect.socket_pexpect
from aiostream.pipe import map, merge
from pexpect import EOF, TIMEOUT
from pexpect.spawnbase import SpawnBase
from rich import print_json
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import fcntl
import signal
import struct
import termios

import pexpect
from typer import Typer, echo_via_pager
from typer.core import TyperArgument, TyperOption
from typing import Annotated
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
import random
from rich.console import Console

app = Typer()
T = TypeVar("T")


class NewCommandContext(Generic[T]):
    def __init__(self, callable_command, timeout=0.1, cwd=None, logfile=None, **callable_kwargs):
        # self.logfle = callable_kwargs.pop("logfile", logfile)
        self.callable_command_no_log = partial(callable_command, timeout=timeout, cwd=cwd, **callable_kwargs)
        self.cwd = cwd or Path.cwd()
        self.timeout = timeout
        self.stdout = []
        self.stderr = []
        self.process: T | None = None
        self.started = 0
        self.thread = None

    @contextmanager
    def to_thread(self, printlines=False, timeout=10) -> Iterator[str]:
        try:
            self.thread = Thread(target=self.readlines, daemon=True, kwargs={"printlines": printlines})
            self.thread.start()
            yield self
        finally:
            # self.logfile.close() if self.logfile is not None and hasattr(self.logfile, "close") else None
            self.thread.join(timeout) if self.thread else None

    def start(self) -> T:
        self.process: T = self.callable_command_no_log(logfile=self.logfle)
        self.started = time()
        return self.process

    def streamlines(self, printlines=False) -> Iterator[str]:
        pass


class PexpectCommand(NewCommandContext[SpawnBase]):
    def __init__(self, callable_command, timeout=0.1, cwd=None, logfile=None, **callable_kwargs):
        self.logfle: io.TextIO = callable_kwargs.pop("logfile", logfile)
        self.callable_command_no_log = partial(callable_command, timeout=timeout, cwd=cwd, **callable_kwargs)
        self.cwd = cwd or Path.cwd()
        self.timeout = timeout
        self.stdout = []
        self.stderr = []
        self.process: pexpect.spawnbase.SpawnBase | None = None
        self.started = 0
        self.thread = None

    @contextmanager
    def to_thread(self, printlines=False, timeout=10) -> Iterator[str]:
        try:
            self.thread = Thread(target=self.streamlines, daemon=True, kwargs={"printlines": printlines})
            self.thread.start()
            yield self
        finally:
            self.logfile.close() if self.logfile is not None and hasattr(self.logfile, "close") else None
            self.thread.join(timeout) if self.thread else None

    # def streamlines(self, printlines=False) -> Iterator[str]:
    #     process = self.process or self.start()
    #     try:
    #         while not process.eof() and time() - self.started < self.timeout:
    #             print(f"Time elapsed: {time() - self.started}")
    #             self.started = time()
    #             line = (
    #                 process.readline()
    #                 .decode("utf-8")
    #                 .strip()
    #                 .replace("\\n", "\n")
    #                 .replace("\\t", "\t")
    #                 .replace("\\r", "\r")
    #             )
    #             self.stdout.append(line)
    #             yield line
    #         return
    #     except pexpect.exceptions.TIMEOUT as e:
    #         if process.isalive():
    #             process.terminate(force=True)
    #         yield f"Command timed out: {e}"
    #     except Exception as e:
    #         process.terminate(force=True) if process.isalive() else None
    #         process.close()

    #         traceback.print_exc()
    #         raise e
    #     finally:
    #         self.logfle.close()
    #         self.process.kill() if self.process else None


class PtyCommand:
    def __init__(self, callable_command, timeout=10, cwd=None, logfile=None, **callable_kwargs):
        logfile = Path(str(logfile)).resolve() if logfile else tempfile.NamedTemporaryFile(delete=False)

        # self.logfile: Optional[io.TextIOBase] = callable_kwargs.pop("logfile", logfile)
        self.callable_command_no_log = partial(callable_command, timeout=timeout, cwd=cwd, **callable_kwargs)
        cwd = Path(str(cwd)).resolve() if cwd else Path.cwd()
        self.cwd = cwd if cwd.is_dir() else cwd.parent if cwd.exists() else Path.cwd()
        self.timeout = timeout
        self.output = []
        self.process: Optional[pexpect.pty_spawn.spawn] = None
        self.started = 0
        self.thread = None
        self.lines = []

    @contextmanager
    def to_thread(self, printlines=False, timeout=10) -> Iterator[str]:
        try:
            self.thread = Thread(target=self.readlines, daemon=True, kwargs={"printlines": printlines})
            self.thread.start()
            yield self
        finally:
            if self.thread:
                self.thread.join(timeout)

    def readlines(self, show=False):
        self.start()
        return "".join(self.streamlines(show))

    def start(self):
        if not self.process or not self.process.isalive():
            self.process: pexpect.pty_spawn.spawn = self.callable_command_no_log(
                echo=False,
            )
            self.started = time()
        return self.process

    def streamlines(self, show=False) -> Iterator[str]:
        process = self.process or self.start()
        try:
            while not process.eof() and time() - self.started < self.timeout and process.isalive():
                yield self.readline(self.process)
        except pexpect.exceptions.TIMEOUT as e:
            if process.isalive():
                process.terminate(force=True)
            yield f"Command timed out: {e}"
        except Exception as e:
            if process.isalive():
                process.terminate(force=True)
            traceback.print_exc()
            raise e
        finally:
            if process.isalive():
                process.close()

    def readline(self, process=None, show=False):
        self.started = time()
        process = process or self.process
        # line = (
        #     process.read_nonblocking(1000, timeout=30)
        #     .decode("utf-8")
        #     .strip()
        #     .replace("\\n", "\n")
        #     .replace("\\t", "\t")
        #     .replace("\\r", "\r")
        # )
        # lines = line.split("\n")
        # if len(self.lines) < 1:
        #     self.lines = lines
        #     self.lines.append([""]) # Always have a line to concatenate to
        # elif len(lines) >= 1:
        #     self.lines[-1] += line[0]
        #     self.lines.append(line[1])
        # else:
        #     self.lines.append(line)
        line = process.readline().decode("utf-8").strip().replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")
        self.lines.append(line)
        if show:
            print(line)
        return line

    def __iter__(self):
        return self.streamlines()

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
def create_parser():
    parser = configargparse.ArgumentParser(description="Rich CLI Tool Example", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "-a",
        "--action",
        help="Choose an action:\n1. Run tests\n2. Display status\n3. Exit",
        type=int,
        choices=[1, 2, 3],
    )
    return parser


# Function to display a header using Rich
def display_header():
    console.print(Panel("[bold green]Welcome to the Rich CLI Tool Example![/bold green]", expand=False))


# Function to display a status table
def display_status():
    table = Table(title="System Status", box=box.SQUARE)

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


__all__ = ["TCPConnection"]


class TCPConnection(SpawnBase):
    """
    This class establishes a TCP connection and works similarly to pexpect but uses a
    cross-platform Python socket API for TCP sockets.
    """

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
        """
        Initializes the TCP connection.

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
        """
        Read from the TCP connection without blocking.

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


def run_command(
    command: Union[str, list[str]],
    cwd: str | None = None,
    mode: Literal["block_until_done", "stream", "background"] = "block_until_done",
    logfile=None,
    timeout: int = 10,
    buffer_size=2000,  # Reduced buffer size to prevent overflow
    debug=False,
    host=None,
    port=None,
):
    """Run a command and yield the output line by line asynchronously."""
    if sys.flags.debug or debug:
        logging.basicConfig(level=logging.DEBUG, force=True)
        print("Debug logging enabled.")

    # Create logfile if not provided
    # logfile = Path(logfile) if logfile else tempfile.NamedTemporaryFile(delete=False)
    exec_, *args = command if isinstance(command, list) else command.split()
    print(f"Running command: {exec_} {' '.join([arg.strip() for arg in args])}")
    print(f"command: {exec_}".replace("\n", "newline"))
    if host is not None and port is not None:
        return TCPConnection(exec_, host=host, port=port, cwd=cwd, timeout=timeout)
    return run_cmd(exec_ + " " + " ".join(args), cwd=cwd, timeout=timeout, logfile=logfile)
    


async def arun_command(
    command: Union[str, list[str]],
    cwd: str | None = None,
    mode: Literal["block_until_done", "stream", "background"] = "block_until_done",
    logfile=None,
    timeout: int = 10,
    buffer_size=2000,  # Reduced buffer size to prevent overflow
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

    if remote:
        process = pexpect
    else:
        process = await asyncio.create_subprocess_exec(exec_, *args, cwd=cwd, stdout=PIPE, stderr=PIPE)

    async def read_stream(stream):
        while True:
            line = await stream.readline()
            if line:
                yield line.decode().strip()
            else:
                break

    if mode == "block_until_done":
        stdout, stderr = await process.communicate()
        yield merge(
            iterate(stdout.decode().splitlines()),
            iterate(stderr.decode().splitlines()),
        )
    return



def sigwinch_passthrough(sig, data, p):
    s = struct.pack("HHHH", 0, 0, 0, 0)
    a = struct.unpack("hhhh", fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, s))
    if not p.closed:
        p.setwinsize(a[0], a[1])


@app.command(no_args_is_help=True)
def run_cmd(cmd: Annotated[
    str, TyperArgument(
        type=list[str],
        param_decls=["cmd"],
        help="Command to run",
        nargs=-1,
    )
], 
    args: Annotated[
        str, TyperOption(
            param_decls=["-a", "--args"],
            help="Arguments to pass to the command",
            nargs=-1,
        )
    ] = None,
    **kwargs,
):
    def _run_cmd(cmd, args, **kwargs):
        p = pexpect.spawn(cmd, **kwargs)
        signal.signal(signal.SIGWINCH, partial(sigwinch_passthrough, p=p))
        p.interact()
    out = []
    for i in cmd.split():
        if i.startswith("~"):
            out.append(str(Path(i).expanduser().resolve()))
        elif i.startswith("."):
            out.append(str(Path(i).resolve()))
        else:
            out.append(i)
    _run_cmd("bash", ["-c",*out], **kwargs)



@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    no_args_is_help=True,
)
def interact(
    cmd: Annotated[str, TyperArgument(
        type=list[str],
        param_decls=["cmd"],
        help="Command to run in interactive mode",
        required=True,
        nargs=-1,
    )]
):  
   
   run_cmd(cmd)


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

