"""Copied and modified to work with asyncio and windows from pexpect."""
import asyncio
import codecs
import errno
import logging
import os
import re
import select
import shlex
import shutil
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
import traceback
from asyncio import (
    BaseTransport,
    ReadTransport,
)
from collections.abc import Awaitable, Callable, Iterable
from contextlib import contextmanager
from functools import wraps
from io import BytesIO, StringIO
from pathlib import Path
from queue import Empty, Queue
from re import Match, Pattern
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Literal,
    LiteralString,
    Protocol,
    Self,
    TextIO,
    TypeVar,
    Union,
    cast,
    overload,
)

from typing_extensions import TypeAlias

string_types = (str, bytes)
AnyStrT = TypeVar("AnyStrT", str, bytes)
AnyStrT_co = TypeVar("AnyStrT_co", str, bytes, covariant=True)
PY3: bool
text_type: type
AnyStr  = str  | bytes




def get_shell_aliases(home_dir="~"):
    try:
        # Determine the shell and the appropriate initialization file
        shell = os.environ.get("SHELL", "")
        mbdir = Path(os.getenv("MB_WS", Path.home()))
        home_dirs = {Path.home(), Path(home_dir).expanduser(), mbdir}
        results = []

        for home_dir in home_dirs:
            if "bash" in shell:
                init_file = home_dir / ".bashrc"
            elif "zsh" in shell:
                init_file = home_dir / ".zshrc"
            else:
                raise ValueError(f"Unsupported shell: {shell}")

            # Check if the initialization file exists
            if not init_file.exists():
                continue  # Skip if the file doesn't exist

            # Source the shell configuration file and list aliases
            command = f"source {init_file}; alias"
            result = subprocess.run(command, shell=True, capture_output=True, text=True, executable=shell, check=False)

            if result.returncode == 0:
                results.append(result.stdout.strip())
            else:
                raise ValueError(f"{result.stderr.strip()}")


        # Resolve aliases and dependencies
        return resolve_aliases_and_dependencies("\n".join(results).splitlines())
    except Exception as e:
        traceback.print_exc()
        return f"Error: {e}"


def resolve_aliases_and_dependencies(aliases, shell="bash"):
    """Resolves shell aliases, expands environment variables, and checks dependencies."""
    try:
        out = {}
        missing_dependencies = []
        for line in aliases:
            match = re.match(r"(\w+)=['\"]?(.+?)['\"]?$", line)
            if match:
                alias_name, alias_command = match.groups()
                resolved_command = os.path.expandvars(alias_command)  # Expand env variables

                # Check for missing dependencies
                command_parts = re.split(r"[;|& ]+", resolved_command)  # Robust splitting
                md = [
                    part
                    for part in command_parts
                    if not shutil.which(part) and not part.startswith("$") and not part.startswith("(")
                ]
                missing_dependencies.extend(md)
                out[alias_name] = resolved_command

        return out, missing_dependencies
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

aliases,md = get_shell_aliases()

class ExceptionPexpect(Exception):
    """Base class for all exceptions raised by this module."""

    def __init__(self, value):
        super().__init__(value)
        self.value = value

    def __str__(self):
        return str(self.value)

    def get_trace(self):
        """This returns an abbreviated stack trace with lines that only concern
        the caller. In other words, the stack trace inside the Pexpect module
        is not included.
        """
        tblist = traceback.extract_tb(sys.exc_info()[2])
        tblist = [item for item in tblist if ("pexpect/__init__" not in item[0]) and ("pexpect/expect" not in item[0])]
        tblist = traceback.format_list(tblist)
        return "".join(tblist)


class EOF(ExceptionPexpect):
    """Raised when EOF is read from a child.
    This usually means the child has exited.
    """


class TIMEOUT(ExceptionPexpect):
    """Raised when a read time exceeds the timeout."""



class _NullCoder:
    """Pass bytes through unchanged."""

    @staticmethod
    def encode(b, final=False):
        return b

    @staticmethod
    def decode(b, final=False):
        return b

class _Logfile(Protocol):
    def write(self, s, /) -> object: ...
    def flush(self) -> object: ...


_T = TypeVar("T")
_T_co = TypeVar("_T_co", str, bytes, covariant=True)
_T_contra = TypeVar("_T_contra", contravariant=True)

class SearcherStringT(Protocol[_T_co]):  # type: ignore # noqa: N801
    """This is a plain string search helper for the spawn.expect_any() method.
    This helper class is for speed. For more powerful regex patterns
    see the helper class, searcher_re.

    Attributes:
        eof_index     - index of EOF, or -1
        timeout_index - index of TIMEOUT, or -1

    After a successful match by the search() method the following attributes
    are available:

        start - index into the buffer, first byte of match
        end   - index into the buffer, first byte after match
        match - the matching string itself

    """  # noqa: D205

    longest_string: int
    eof_index: int
    timeout_index: int
    _strings: list[_T_co | tuple[int, _T_co]]
    match: _T_co
    start: int
    end: int
    
    def __init__(self, strings: list[_T_co | tuple[int, _T_co]]) -> None: ...
    def __str__(self) -> str: ...
    def search(self, buffer: str, freshlen: int, searchwindowsize: int | None = None) -> int: ...
    

class searcher_string: # noqa
    """This is a plain string search helper for the spawn.expect_any() method.
    This helper class is for speed. For more powerful regex patterns
    see the helper class, searcher_re.

    Attributes:
        eof_index     - index of EOF, or -1
        timeout_index - index of TIMEOUT, or -1

    After a successful match by the search() method the following attributes
    are available:

        start - index into the buffer, first byte of match
        end   - index into the buffer, first byte after match
        match - the matching string itself

    """

    def __init__(self, strings):
        """This creates an instance of searcher_string. This argument 'strings'
        may be a list; a sequence of strings; or the EOF or TIMEOUT types.
        """
        self.eof_index = -1
        self.timeout_index = -1
        self._strings = []
        self.longest_string = 0
        for n, s in enumerate(strings):
            if s is EOF:
                self.eof_index = n
                continue
            if s is TIMEOUT:
                self.timeout_index = n
                continue
            self._strings.append((n, s))
            if len(s) > self.longest_string:
                self.longest_string = len(s)

    def __str__(self):
        """This returns a human-readable string that represents the state of
        the object.
        """
        ss = [(ns[0], "    %d: %r" % ns) for ns in self._strings]
        ss.append((-1, "searcher_string:"))
        if self.eof_index >= 0:
            ss.append((self.eof_index, "    %d: EOF" % self.eof_index))
        if self.timeout_index >= 0:
            ss.append((self.timeout_index, "    %d: TIMEOUT" % self.timeout_index))
        ss.sort()
        ss = list(zip(*ss, strict=False))[1]
        return "\n".join(ss)

    def search(self, buffer, freshlen, searchwindowsize=None):
        """This searches 'buffer' for the first occurrence of one of the search
        strings.  'freshlen' must indicate the number of bytes at the end of
        'buffer' which have not been searched before. It helps to avoid
        searching the same, possibly big, buffer over and over again.

        See class spawn for the 'searchwindowsize' argument.

        If there is a match this returns the index of that string, and sets
        'start', 'end' and 'match'. Otherwise, this returns -1.
        """
        first_match = None

        # 'freshlen' helps a lot here. Further optimizations could
        # possibly include:
        #
        # using something like the Boyer-Moore Fast String Searching
        # Algorithm; pre-compiling the search through a list of
        # strings into something that can scan the input once to
        # search for all N strings; realize that if we search for
        # ['bar', 'baz'] and the input is '...foo' we need not bother
        # rescanning until we've read three more bytes.
        #
        # Sadly, I don't know enough about this interesting topic. /grahn

        for index, s in self._strings:
            if searchwindowsize is None:
                # the match, if any, can only be in the fresh data,
                # or at the very end of the old data
                offset = -(freshlen + len(s))
            else:
                # better obey searchwindowsize
                offset = -searchwindowsize
            n = buffer.find(s, offset)
            if n >= 0 and (first_match is None or n < first_match):
                first_match = n
                best_index, best_match = index, s
        if first_match is None:
            return -1
        self.match = best_match
        self.start = first_match
        self.end = self.start + len(self.match)
        return best_index


class searcher_re: # noqa
    """Regular expression string search helper for the spawn.expect_any() method.
    
    This helper class is for powerful pattern matching. For speed, see the helper class, searcher_string.

    Attributes:
        eof_index     - index of EOF, or -1
        timeout_index - index of TIMEOUT, or -1

    After a successful match by the search() method the following attributes
    are available:

        start - index into the buffer, first byte of match
        end   - index into the buffer, first byte after match
        match - the re.match object returned by a successful re.search

    """

    def __init__(self, patterns):
        """Ceates an instance that searches for 'patterns'.
        
        Where 'patterns' may be a list or other sequence of compiled regular
        expressions, or the EOF or TIMEOUT types.
        """
        self.eof_index = -1
        self.timeout_index = -1
        self._searches = []
        for n, s in enumerate(patterns):
            if s is EOF:
                self.eof_index = n
                continue
            if s is TIMEOUT:
                self.timeout_index = n
                continue
            self._searches.append((n, s))

    def __str__(self):
        """Returns a human-readable string that represents the state of the object."""
        # ss = [(n, '    %d: re.compile("%s")' %
        #    (n, repr(s.pattern))) for n, s in self._searches]
        ss = []
        for n, s in self._searches:
            ss.append((n, "    %d: re.compile(%r)" % (n, s.pattern)))
        ss.append((-1, "searcher_re:"))
        if self.eof_index >= 0:
            ss.append((self.eof_index, "    %d: EOF" % self.eof_index))
        if self.timeout_index >= 0:
            ss.append((self.timeout_index, "    %d: TIMEOUT" % self.timeout_index))
        ss.sort()
        ss = list(zip(*ss, strict=False))[1]
        return "\n".join(ss)

    def search(self, buffer, freshlen, searchwindowsize=None):
        """Searches 'buffer' for the first occurrence of one of the regular expression.
        
        'freshlen' must indicate the number of bytes at the end of
        'buffer' which have not been searched before.

        See class spawn for the 'searchwindowsize' argument.

        If there is a match this returns the index of that string, and sets
        'start', 'end' and 'match'. Otherwise, returns -1.
        """
        first_match = None
        # 'freshlen' doesn't help here -- we cannot predict the
        # length of a match, and the re module provides no help.
        searchstart = 0 if searchwindowsize is None else max(0, len(buffer) - searchwindowsize)
        for index, s in self._searches:
            match = s.search(buffer, searchstart)
            if match is None:
                continue
            n = match.start()
            if first_match is None or n < first_match:
                first_match = n
                the_match = match
                best_index = index
        if first_match is None:
            return -1
        self.start = first_match
        self.match = the_match
        self.end = self.match.end()
        return best_index


_ErrorPattern: TypeAlias = type[EOF | TIMEOUT]
_InputStringPattern: TypeAlias = str | bytes | _ErrorPattern
_InputRePattern: TypeAlias = Pattern[str] | Pattern[bytes] | _InputStringPattern
_CompiledStringPattern: TypeAlias = AnyStr | _ErrorPattern
_CompiledRePattern: TypeAlias = Pattern | _ErrorPattern
_Searcher: TypeAlias = searcher_string | searcher_re


class PatternWaiter(Protocol):
    transport: ReadTransport
    fut: asyncio.Future
    expecter: "Expecter"
    
    def set_expecter(self, expecter: "Expecter") -> Self:
        self.expecter = expecter
        self.fut = asyncio.Future()
        return self
    def found(self, result) -> Self:
        if not self.fut.done():
            self.fut.set_result(result)
            self.transport.pause_reading()
        return self
    def error(self, exc) -> None:
        if not self.fut.done():
            # Assign the collected output to `before` before raising
            if not self.expecter.spawn.before:
                self.expecter.spawn.before = self.expecter.spawn._before.getvalue()
        self.fut.set_exception(exc)
        self.transport.pause_reading()
    def connection_made(self, transport) -> Self:
        self.transport = transport
        return self
    def data_received(self, data) -> Self:
        spawn = self.expecter.spawn
        s = spawn._decoder.decode(data)
        spawn._log(s, "read")

        if self.fut.done():
            spawn._before.write(s)
            spawn._buffer.write(s)
            return self

        try:
            index = self.expecter.new_data(s)
            if index is not None:
                # Found a match
                self.found(index)
        except Exception as e:
            self.expecter.errored()
            self.error(e)
        return self

    def eof_received(self) -> Self:
        # N.B. If this gets called, async will close the pipe (the spawn object)
        # for us
        try:
            self.expecter.spawn.flag_eof = True
            index = self.expecter.eof()
        except EOF as e:
            self.error(e)
        else:
            self.found(index)
        return self
    def connection_lost(self, exc) -> Self:
        if isinstance(exc, OSError) and exc.errno == errno.EIO:
            # We may get here without eof_received being called, e.g on Linux
            self.eof_received()
        elif exc is not None:
            self.error(exc)
        return self



async def repl_run_command_async(repl: "REPLWrapper", cmdlines, timeout=-1) -> LiteralString:
    res = []
    repl.child.sendline(cmdlines[0])
    for line in cmdlines[1:]:
        await repl._expect_prompt(timeout=timeout, async_=True)
        res.append(repl.child.before)
        repl.child.sendline(line)

    # Command was fully submitted, now wait for the next prompt
    prompt_idx = await repl._expect_prompt(timeout=timeout, async_=True)
    if prompt_idx == 1:
        # We got the continuation prompt - command was incomplete
        repl.child.kill(signal.SIGINT)
        await repl._expect_prompt(timeout=1, async_=True)
        raise ValueError("Continuation prompt found - input was incomplete:")
    return "".join(res + [repl.child.before])






basestring = str

PEXPECT_PROMPT = "[PEXPECT_PROMPT>"
PEXPECT_CONTINUATION_PROMPT = "[PEXPECT_PROMPT+"


class REPLWrapper:
    """Wrapper for a REPL.
    
    :param cmd_or_spawn: This can either be an instance of :class:`pexpect.spawn`
      in which a REPL has already been started, or a str command to start a new
      REPL process.
    :param str orig_prompt: The prompt to expect at first.
    :param str prompt_change: A command to change the prompt to something more
      unique. If this is ``None``, the prompt will not be changed. This will
      be formatted with the new and continuation prompts as positional
      parameters, so you can use ``{}`` style formatting to insert them into
      the command.
    :param str new_prompt: The more unique prompt to expect after the change.
    :param str extra_init_cmd: Commands to do extra initialisation, such as
      disabling pagers.
    """
    process_type: "type[SpawnBase]"
    def __init__(
        self,
        cmd_or_spawn: Union[str, "SpawnBase"],
        orig_prompt,
        prompt_change,
        new_prompt=PEXPECT_PROMPT,
        continuation_prompt=PEXPECT_CONTINUATION_PROMPT,
        extra_init_cmd=None,
    ):
        if isinstance(cmd_or_spawn, basestring):
            self.child = self.process_type(cmd_or_spawn, echo=False, encoding="utf-8")
        else:
            self.child = cmd_or_spawn
        if self.child.echo:
            # Existing spawn instance has echo enabled, disable it
            # to prevent our input from being repeated to output.
            self.child.setecho(False)
            self.child.waitnoecho()

        if prompt_change is None:
            self.prompt = orig_prompt
        else:
            self.set_prompt(orig_prompt, prompt_change.format(new_prompt, continuation_prompt))
            self.prompt = new_prompt
        self.continuation_prompt = continuation_prompt

        self._expect_prompt()

        if extra_init_cmd is not None:
            self.run_command(extra_init_cmd)

    def set_prompt(self, orig_prompt, prompt_change) -> None:
        self.child.expect(orig_prompt)
        self.child.sendline(prompt_change)

    def _expect_prompt(self, timeout=-1, async_=False):
        return self.child.expect_exact([self.prompt, self.continuation_prompt], timeout=timeout, async_=async_)

    def run_command(self, command, timeout=-1, async_=False):
        """Send a command to the REPL, wait for and return output.

        :param str command: The command to send. Trailing newlines are not needed.
          This should be a complete block of input that will trigger execution;
          if a continuation prompt is found after sending input, :exc:`ValueError`
          will be raised.
        :param int timeout: How long to wait for the next prompt. -1 means the
          default from the :class:`pexpect.spawn` object (default 30 seconds).
          None means to wait indefinitely.
        :param bool async_: On Python 3.4, or Python 3.3 with asyncio
          installed, passing ``async_=True`` will make this return an
          :mod:`asyncio` Future, which you can yield from to get the same
          result that this method would normally give directly.
        """
        # Split up multiline commands and feed them in bit-by-bit
        cmdlines = command.splitlines()
        # splitlines ignores trailing newlines - add it back in manually
        if command.endswith("\n"):
            cmdlines.append("")
        if not cmdlines:
            raise ValueError("No command was given")

        if async_:
            from ._async import repl_run_command_async

            return repl_run_command_async(self, cmdlines, timeout)

        res = []
        self.child.sendline(cmdlines[0])
        for line in cmdlines[1:]:
            self._expect_prompt(timeout=timeout)
            res.append(self.child.before)
            self.child.sendline(line)

        # Command was fully submitted, now wait for the next prompt
        if self._expect_prompt(timeout=timeout) == 1:
            # We got the continuation prompt - command was incomplete
            self.child.kill(signal.SIGINT)
            self._expect_prompt(timeout=1)
            raise ValueError("Continuation prompt found - input was incomplete:\n" + command)
        return "".join(res + [self.child.before])


def python(command=sys.executable):
    """Start a Python shell and return a :class:`REPLWrapper` object."""
    return REPLWrapper(command, ">>> ", "import sys; sys.ps1={0!r}; sys.ps2={1!r}")


def _repl_sh(command, args, non_printable_insert):
    child = spawn(command, args, echo=False, encoding="utf-8")

    # If the user runs 'env', the value of PS1 will be in the output. To avoid
    # replwrap seeing that as the next prompt, we'll embed the marker characters
    # for invisible characters in the prompt; these show up when inspecting the
    # environment variable, but not when bash displays the prompt.
    ps1 = PEXPECT_PROMPT[:5] + non_printable_insert + PEXPECT_PROMPT[5:]
    ps2 = PEXPECT_CONTINUATION_PROMPT[:5] + non_printable_insert + PEXPECT_CONTINUATION_PROMPT[5:]
    prompt_change = f"PS1='{ps1}' PS2='{ps2}' PROMPT_COMMAND=''"

    return REPLWrapper(child, "\\$", prompt_change, extra_init_cmd="export PAGER=cat")


def bash(command="bash"):
    """Start a bash shell and return a :class:`REPLWrapper` object."""
    bashrc = os.path.join(os.path.dirname(__file__), "bashrc.sh")
    return _repl_sh(command, ["--rcfile", bashrc], non_printable_insert="\\[\\]")


def zsh(command="zsh", args=("--no-rcs", "-V", "+Z")):
    """Start a zsh shell and return a :class:`REPLWrapper` object."""
    return _repl_sh(command, list(args), non_printable_insert="%(!..)")


class SpawnBaseT(Protocol[AnyStrT_co]):
    encoding: str | None
    pid: int | None
    flag_eof: bool
    stdin: TextIO
    stdout: TextIO
    stderr: TextIO
    searcher: None
    ignorecase: bool
    before: AnyStr | None
    after: _CompiledStringPattern | None
    match: AnyStr | Match[str] | Match[bytes]| _ErrorPattern | None
    match_index: int | None
    terminated: bool
    exitstatus: int | None
    signalstatus: int | None
    status: int | None
    child_fd: int
    timeout: float | None
    delimiter: type[EOF]
    logfile: _Logfile | None
    logfile_read: _Logfile | None
    logfile_send: _Logfile | None
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
    string_type: type[AnyStrT_co]
    buffer_type: type[IO[AnyStrT_co]] 
    crlf: AnyStr
    allowed_string_types: tuple[type, ...]
    linesep: AnyStr
    write_to_stdout: Callable[[AnyStr], int]


    @property
    def buffer(self) -> AnyStr: ...
    @buffer.setter
    def buffer(self, value: AnyStr) -> None: ...
    def read_nonblocking(self, size: int = 1, timeout: float | None = None) -> AnyStr: ...
    def compile_pattern_list(
        self, patterns: _InputRePattern | list[_InputRePattern],
    ) -> list[_CompiledRePattern]: ...
    @overload
    def expect(
        self,
        pattern: _InputRePattern | list[_InputRePattern],
        timeout: float | None = -1,
        searchwindowsize: int | None = -1,
        async_: Literal[False] = False,
    ) -> int: ...
    @overload
    def expect(
        self,
        pattern: _InputRePattern | list[_InputRePattern],
        timeout: float | None = -1,
        searchwindowsize: int | None = -1,
        *,
        async_: Literal[True],
    ) -> Awaitable[int]: ...
    @overload
    def expect_list(
        self,
        pattern_list: list[_CompiledRePattern],
        timeout: float | None = -1,
        searchwindowsize: int | None = -1,
        async_: Literal[False] = False,
    ) -> int: ...
    @overload
    def expect_list(
        self,
        pattern_list: list[_CompiledRePattern],
        timeout: float | None = -1,
        searchwindowsize: int | None = -1,
        *,
        async_: Literal[True],
    ) -> Awaitable[int]: ...
    @overload
    def expect_exact(
        self,
        pattern_list: _InputStringPattern | Iterable[_InputStringPattern],
        timeout: float | None = -1,
        searchwindowsize: int | None = -1,
        async_: Literal[False] = False,
    ) -> int: ...
    @overload
    def expect_exact(
        self,
        pattern_list: _InputStringPattern | Iterable[_InputStringPattern],
        timeout: float | None = -1,
        searchwindowsize: int | None = -1,
        *,
        async_: Literal[True],
    ) -> Awaitable[int]: ...
    def expect_loop(
        self, searcher: _Searcher, timeout: float | None = -1, searchwindowsize: int | None = -1,
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
        logfile: _Logfile | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        ignore_sighup: bool = False,
        echo: bool = True,
        preexec_fn: Callable[[], None] | None = None,
        encoding: str | None = None,
        codec_errors: str = "strict",
        dimensions: tuple[int, int] | None = None,
        use_poll: bool = False,
    ):...
    def __call__(self, command: str, args: list[str] | None = None,**kwargs) -> None: ...
class PexpectError(Exception):
    """Base class for all exceptions raised by this module."""

    def __init__(self, value):
        super().__init__(value)
        self.value = value

    def __str__(self):
        return str(self.value)

    def get_trace(self) -> str:
        """This returns an abbreviated stack trace with lines that only concern the caller.
        
        In other words, the stack trace inside the Pexpect module
        is not included.
        """
        tblist = traceback.extract_tb(sys.exc_info()[2])
        tblist = [item for item in tblist if ('pexpect/__init__' not in item[0])
                                           and ('pexpect/expect' not in item[0])]
        tblist = traceback.format_list(tblist)
        return ''.join(tblist)



    





class Expecter:
    def __init__(self, spawn: "SpawnBase", searcher: _Searcher, searchwindowsize=-1):
        self.spawn = spawn
        self.searcher: _Searcher = searcher
        # A value of -1 means to use the figure from spawn, which should
        # be None or a positive number.
        if searchwindowsize == -1:
            searchwindowsize = spawn.searchwindowsize
        self.searchwindowsize = searchwindowsize
        self.lookback = None
        if hasattr(searcher, "longest_string"):
            self.lookback = searcher.longest_string

    def do_search(self, window, freshlen):
        spawn = self.spawn
        searcher = self.searcher
        if freshlen > len(window):
            freshlen = len(window)
        index = searcher.search(window, freshlen, self.searchwindowsize)
        if index >= 0:
            spawn._buffer = spawn.buffer_type()
            spawn._buffer.write(window[searcher.end :])
            spawn.before = spawn._before.getvalue()[0 : -(len(window) - searcher.start)]
            spawn._before = spawn.buffer_type()
            spawn._before.write(window[searcher.end :])
            spawn.after = window[searcher.start : searcher.end]
            spawn.match = searcher.match
            spawn.match_index = index
            # Found a match
            return index
        if self.searchwindowsize or self.lookback:
            maintain = self.searchwindowsize or self.lookback
            if spawn._buffer.tell() > maintain:
                spawn._buffer = spawn.buffer_type()
                spawn._buffer.write(window[-maintain:])
        return None

    def existing_data(self):
        # First call from a new call to expect_loop or expect_async.
        # self.searchwindowsize may have changed.
        # Treat all data as fresh.
        spawn = self.spawn
        before_len = spawn._before.tell()
        buf_len = spawn._buffer.tell()
        freshlen = before_len
        if before_len > buf_len:
            logging.debug(f"before len > buffer len")
            if not self.searchwindowsize:
                logging.debug("searchwindow not set")
                spawn._buffer = spawn.buffer_type()
                window = spawn._before.getvalue()
                spawn._buffer.write(window)
            elif buf_len < self.searchwindowsize:
                spawn._buffer = spawn.buffer_type()
                spawn._before.seek(max(0, before_len - self.searchwindowsize))
                window = spawn._before.read()
                spawn._buffer.write(window)
            else:
                spawn._buffer.seek(max(0, buf_len - self.searchwindowsize))
                window = spawn._buffer.read()
        else:
            if self.searchwindowsize:
                spawn._buffer.seek(max(0, buf_len - self.searchwindowsize))
                window = spawn._buffer.read()
            else:
                window = spawn._buffer.getvalue()
        return self.do_search(window, freshlen)

    def new_data(self, data):
        # A subsequent call, after a call to existing_data.
        spawn = self.spawn
        freshlen = len(data)
        spawn._before.write(data)
        logging.debug(f"{self.lookback=}, {self.searchwindowsize=}")
        if not self.searchwindowsize:
            if self.lookback:
                # search lookback + new data.
                old_len = spawn._buffer.tell()
                spawn._buffer.write(data)
                spawn._buffer.seek(max(0, old_len - self.lookback))
                window = spawn._buffer.read()
            else:
                # copy the whole buffer (really slow for large datasets).
                spawn._buffer.write(data)
                window = spawn.buffer
        else:
            if len(data) >= self.searchwindowsize or not spawn._buffer.tell():
                window = data[-self.searchwindowsize :]
                spawn._buffer = spawn.buffer_type()
                spawn._buffer.write(window[-self.searchwindowsize :])
            else:
                spawn._buffer.write(data)
                new_len = spawn._buffer.tell()
                spawn._buffer.seek(max(0, new_len - self.searchwindowsize))
                window = spawn._buffer.read()
        return self.do_search(window, freshlen)

    def eof(self, err=None):
        spawn = self.spawn

        spawn.before = spawn._before.getvalue()
        spawn._buffer = spawn.buffer_type()
        spawn._before = spawn.buffer_type()
        spawn.after = EOF
        index = self.searcher.eof_index
        if index >= 0:
            spawn.match = EOF
            spawn.match_index = index
            return index
        spawn.match = None
        spawn.match_index = None
        msg = str(spawn)
        msg += f"\nsearcher: {self.searcher}"
        if err is not None:
            msg = str(err) + "\n" + msg

        exc = EOF(msg)
        exc.__cause__ = None  # in Python 3.x we can use "raise exc from None"
        raise exc

    def timeout(self, err=None):
        spawn = self.spawn

        spawn.before = spawn._before.getvalue()
        spawn.after = str(TIMEOUT)
        index = self.searcher.timeout_index
        if index >= 0:
            spawn.match = TIMEOUT
            spawn.match_index = index
            return index
        spawn.match = None
        spawn.match_index = None
        msg = str(spawn)
        msg += f"\nsearcher: {self.searcher}"
        if err is not None:
            msg = str(err) + "\n" + msg
        raise TIMEOUT(err)

    def errored(self) -> None:
        spawn = self.spawn
        spawn.before = spawn._before.getvalue()
        spawn.after = None
        spawn.match = None
        spawn.match_index = None

    def expect_loop(self, timeout=-1):
        """Blocking expect."""
        spawn = self.spawn

        if timeout is not None:
            end_time = time.time() + timeout

        try:
            idx = self.existing_data()
            if idx is not None:
                return idx
            while True:
                # No match at this point
                if (timeout is not None) and (timeout < 0):
                    return self.timeout()
                # Still have time left, so read more data
                incoming = spawn.read_nonblocking(spawn.maxread, timeout)
                if self.spawn.delayafterread is not None:
                    time.sleep(self.spawn.delayafterread)
                idx = self.new_data(incoming)
                # Keep reading until exception or return.
                if idx is not None:
                    return idx
                if timeout is not None:
                    timeout = end_time - time.time()
        except EOF as e:
            return self.eof(e)
        except TIMEOUT as e:
            return self.timeout(e)
        except:
            self.errored()
            raise




PY3 = sys.version_info[0] >= 3
text_type = str


class SpawnBase:
    encoding: str | None = None
    pid: int | None = None
    flag_eof: bool = False

    def __init__(self, timeout: float | None = 30, maxread: int = 2000, searchwindowsize: int | None = None,
                 logfile: _Logfile | None = None, encoding: str | None = None, codec_errors: str = 'strict'):
        self.stdin: TextIO = sys.stdin
        self.stdout: TextIO = sys.stdout
        self.stderr: TextIO = sys.stderr

        self.searcher: _Searcher | None = None
        self.ignorecase: bool = False
        self.before: bytes | str | None = None
        self.after: AnyStr | None = None
        self.match: AnyStr | Match[str] | Match[bytes] | _ErrorPattern | None = None
        self.match_index: int | None = None
        self.terminated: bool = True
        self.exitstatus: int | None = None
        self.signalstatus: int | None = None
        # status returned by os.waitpid
        self.status: int | None = None
        # the child file descriptor is initially closed
        self.child_fd: int | None = -1
        self.timeout: float | None = timeout
        self.delimiter: type[EOF] = EOF
        self.logfile: _Logfile | None = logfile
        # input from child (read_nonblocking)
        self.logfile_read: _Logfile | None = None
        # output to send (send, sendline)
        self.logfile_send: _Logfile | None = None
        # max bytes to read at one time into buffer
        self.maxread: int = maxread
        # Data before searchwindowsize point is preserved, but not searched.
        self.searchwindowsize: int | None = searchwindowsize
        # Delay used before sending data to child. Time in seconds.
        # Set this to None to skip the time.sleep() call completely.
        self.delaybeforesend: float | None = 0.05
        # Used by close() to give kernel time to update process status.
        # Time in seconds.
        self.delayafterclose: float = 0.1
        # Used by terminate() to give kernel time to update process status.
        # Time in seconds.
        self.delayafterterminate: float = 0.1
        # Delay in seconds to sleep after each call to read_nonblocking().
        # Set this to None to skip the time.sleep() call completely: that
        # would restore the behavior from pexpect-2.0 (for performance
        # reasons or because you don't want to release Python's global
        # interpreter lock).
        self.delayafterread: float | None = 0.0001
        self.softspace: bool = False
        self.name: str = '<' + repr(self) + '>'
        self.closed: bool = True

        # Unicode interface
        self.encoding: str | None = encoding
        self.codec_errors: str = codec_errors
        if encoding is None:
            # bytes mode (accepts some unicode for backwards compatibility)
            self._encoder = self._decoder = _NullCoder()
            self.string_type = bytes
            self.buffer_type = BytesIO
            self.crlf = b'\r\n'
            if PY3:
                self.allowed_string_types = (bytes, str)
                self.linesep = os.linesep.encode('ascii')
                def write_to_stdout(b):
                    try:
                        return sys.stdout.buffer.write(b)
                    except AttributeError:
                        # If stdout has been replaced, it may not have .buffer
                        return sys.stdout.write(b.decode('ascii', 'replace'))
                self.write_to_stdout = write_to_stdout
            else:
                self.allowed_string_types = (basestring,)  # analysis:ignore
                self.linesep = os.linesep
                self.write_to_stdout = sys.stdout.write
        else:
            # unicode mode
            self._encoder = codecs.getincrementalencoder(encoding)(codec_errors)
            self._decoder = codecs.getincrementaldecoder(encoding)(codec_errors)
            self.string_type = text_type
            self.buffer_type = StringIO
            self.crlf = '\r\n'
            self.allowed_string_types = (text_type, )
            if PY3:
                self.linesep = os.linesep
            else:
                self.linesep = os.linesep.decode('ascii')
            # This can handle unicode in both Python 2 and 3
            self.write_to_stdout = sys.stdout.write
        # storage for async transport
        self.async_pw_transport: tuple[PatternWaiter, asyncio.Transport] | None = None
        # This is the read buffer. See maxread.
        self._buffer = self.buffer_type()
        # The buffer may be trimmed for efficiency reasons.  This is the
        # untrimmed buffer, used to create the before attribute.
        self._before = self.buffer_type()

    def _log(self, s, direction):
        if self.logfile is not None:
            self.logfile.write(s)
            self.logfile.flush()
        second_log = self.logfile_send if (direction=='send') else self.logfile_read
        if second_log is not None:
            second_log.write(s)
            second_log.flush()

    # For backwards compatibility, in bytes mode (when encoding is None)
    # unicode is accepted for send and expect. Unicode mode is strictly unicode
    # only.
    def _coerce_expect_string(self, s):
        if self.encoding is None and not isinstance(s, bytes):
            return s.encode('ascii')
        return s

    # In bytes mode, regex patterns should also be of bytes type
    def _coerce_expect_re(self, r):
        p = r.pattern
        if self.encoding is None and not isinstance(p, bytes):
            return re.compile(p.encode('utf-8'))
        # And vice-versa
        if self.encoding is not None and isinstance(p, bytes):
            return re.compile(p.decode('utf-8'))
        return r

    def _coerce_send_string(self, s):
        if self.encoding is None and not isinstance(s, bytes):
            return s.encode('utf-8')
        return s

    def _get_buffer(self):
        return self._buffer.getvalue()

    def _set_buffer(self, value):
        self._buffer = self.buffer_type()
        self._buffer.write(value)

    # This property is provided for backwards compatibility (self.buffer used
    # to be a string/bytes object)
    buffer = property(_get_buffer, _set_buffer)

    def read_nonblocking(self, size=1, timeout=None):
        """This reads data from the file descriptor.

        This is a simple implementation suitable for a regular file. Subclasses using ptys or pipes should override it.

        The timeout parameter is ignored.
        """
        try:
            s = os.read(self.child_fd, size)
        except OSError as err:
            if err.args[0] == errno.EIO:
                # Linux-style EOF
                self.flag_eof = True
                raise EOF('End Of File (EOF). Exception style platform.')
            raise
        if s == b'':
            # BSD-style EOF
            self.flag_eof = True
            raise EOF('End Of File (EOF). Empty string style platform.')

        s = self._decoder.decode(s, final=False)
        self._log(s, 'read')
        return s

    def _pattern_type_err(self, pattern):
        raise TypeError('got {badtype} ({badobj!r}) as pattern, must be one'
                        ' of: {goodtypes}, pexpect.EOF, pexpect.TIMEOUT'\
                        .format(badtype=type(pattern),
                                badobj=pattern,
                                goodtypes=', '.join([str(ast)\
                                    for ast in self.allowed_string_types]),
                                ),
                        )

    def compile_pattern_list(self, patterns):
        """This compiles a pattern-string or a list of pattern-strings.
        Patterns must be a StringType, EOF, TIMEOUT, SRE_Pattern, or a list of
        those. Patterns may also be None which results in an empty list (you
        might do this if waiting for an EOF or TIMEOUT condition without
        expecting any pattern).

        This is used by expect() when calling expect_list(). Thus expect() is
        nothing more than::

             cpl = self.compile_pattern_list(pl)
             return self.expect_list(cpl, timeout)

        If you are using expect() within a loop it may be more
        efficient to compile the patterns first and then call expect_list().
        This avoid calls in a loop to compile_pattern_list()::

             cpl = self.compile_pattern_list(my_pattern)
             while some_condition:
                ...
                i = self.expect_list(cpl, timeout)
                ...
        """
        if patterns is None:
            return []
        if not isinstance(patterns, list):
            patterns = [patterns]

        # Allow dot to match \n
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
            elif isinstance(p, type(re.compile(''))):
                p = self._coerce_expect_re(p)
                compiled_pattern_list.append(p)
            else:
                self._pattern_type_err(p)
        return compiled_pattern_list

    def expect(self, pattern, timeout=-1, searchwindowsize=-1, async_=False, **kw):
        """This seeks through the stream until a pattern is matched. The
        pattern is overloaded and may take several types. The pattern can be a
        StringType, EOF, a compiled re, or a list of any of those types.
        Strings will be compiled to re types. This returns the index into the
        pattern list. If the pattern was not a list this returns index 0 on a
        successful match. This may raise exceptions for EOF or TIMEOUT. To
        avoid the EOF or TIMEOUT exceptions add EOF or TIMEOUT to the pattern
        list. That will cause expect to match an EOF or TIMEOUT condition
        instead of raising an exception.

        If you pass a list of patterns and more than one matches, the first
        match in the stream is chosen. If more than one pattern matches at that
        point, the leftmost in the pattern list is chosen. For example::

            # the input is 'foobar'
            index = p.expect(['bar', 'foo', 'foobar'])
            # returns 1('foo') even though 'foobar' is a "better" match

        Please note, however, that buffering can affect this behavior, since
        input arrives in unpredictable chunks. For example::

            # the input is 'foobar'
            index = p.expect(['foobar', 'foo'])
            # returns 0('foobar') if all input is available at once,
            # but returns 1('foo') if parts of the final 'bar' arrive late

        When a match is found for the given pattern, the class instance
        attribute *match* becomes an re.MatchObject result.  Should an EOF
        or TIMEOUT pattern match, then the match attribute will be an instance
        of that exception class.  The pairing before and after class
        instance attributes are views of the data preceding and following
        the matching pattern.  On general exception, class attribute
        *before* is all data received up to the exception, while *match* and
        *after* attributes are value None.

        When the keyword argument timeout is -1 (default), then TIMEOUT will
        raise after the default value specified by the class timeout
        attribute. When None, TIMEOUT will not be raised and may block
        indefinitely until match.

        When the keyword argument searchwindowsize is -1 (default), then the
        value specified by the class maxread attribute is used.

        A list entry may be EOF or TIMEOUT instead of a string. This will
        catch these exceptions and return the index of the list entry instead
        of raising the exception. The attribute 'after' will be set to the
        exception type. The attribute 'match' will be None. This allows you to
        write code like this::

                index = p.expect(['good', 'bad', pexpect.EOF, pexpect.TIMEOUT])
                if index == 0:
                    do_something()
                elif index == 1:
                    do_something_else()
                elif index == 2:
                    do_some_other_thing()
                elif index == 3:
                    do_something_completely_different()

        instead of code like this::

                try:
                    index = p.expect(['good', 'bad'])
                    if index == 0:
                        do_something()
                    elif index == 1:
                        do_something_else()
                except EOF:
                    do_some_other_thing()
                except TIMEOUT:
                    do_something_completely_different()

        These two forms are equivalent. It all depends on what you want. You
        can also just expect the EOF if you are waiting for all output of a
        child to finish. For example::

                p = pexpect.spawn('/bin/ls')
                p.expect(pexpect.EOF)
                print p.before

        If you are trying to optimize for speed then see expect_list().

        On Python 3.4, or Python 3.3 with asyncio installed, passing
        ``async_=True``  will make this return an :mod:`asyncio` coroutine,
        which you can yield from to get the same result that this method would
        normally give directly. So, inside a coroutine, you can replace this code::

            index = p.expect(patterns)

        With this non-blocking form::

            index = yield from p.expect(patterns, async_=True)
        """  # noqa: D205
        if 'async' in kw:
            async_ = kw.pop('async')
        if kw:
            raise TypeError(f"Unknown keyword arguments: {kw}")

        compiled_pattern_list = self.compile_pattern_list(pattern)
        return self.expect_list(compiled_pattern_list,
                timeout, searchwindowsize, async_)

    def expect_list(self, pattern_list, timeout=-1, searchwindowsize=-1,
                    async_=False, **kw):
        """This takes a list of compiled regular expressions and returns the
        index into the pattern_list that matched the child output. The list may
        also contain EOF or TIMEOUT(which are not compiled regular
        expressions). This method is similar to the expect() method except that
        expect_list() does not recompile the pattern list on every call. This
        may help if you are trying to optimize for speed, otherwise just use
        the expect() method.  This is called by expect().


        Like :meth:`expect`, passing ``async_=True`` will make this return an
        asyncio coroutine.
        """
        if timeout == -1:
            timeout = self.timeout
        if 'async' in kw:
            async_ = kw.pop('async')
        if kw:
            raise TypeError(f"Unknown keyword arguments: {kw}")

        exp = Expecter(self, searcher_re(pattern_list), searchwindowsize)
        if async_:
            from ._async import expect_async
            return expect_async(exp, timeout)
        return exp.expect_loop(timeout)

    def expect_exact(self, pattern_list, timeout=-1, searchwindowsize=-1,
                     async_=False, **kw):
        """This is similar to expect(), but uses plain string matching instead
        of compiled regular expressions in 'pattern_list'. The 'pattern_list'
        may be a string; a list or other sequence of strings; or TIMEOUT and
        EOF.

        This call might be faster than expect() for two reasons: string
        searching is faster than RE matching and it is possible to limit the
        search to just the end of the input buffer.

        This method is also useful when you don't want to have to worry about
        escaping regular expression characters that you want to match.

        Like :meth:`expect`, passing ``async_=True`` will make this return an
        asyncio coroutine.
        """
        if timeout == -1:
            timeout = self.timeout
        if 'async' in kw:
            kw.pop('async')
        if kw:
            raise TypeError(f"Unknown keyword arguments: {kw}")

        if (isinstance(pattern_list, self.allowed_string_types) or
                pattern_list in (TIMEOUT, EOF)):
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
        """This is the common loop used inside expect. The 'searcher' should be
        an instance of searcher_re or searcher_string, which describes how and
        what to search for in the input.

        See expect() for other arguments, return value and exceptions.
        """
        exp = Expecter(self, searcher, searchwindowsize)
        return exp.expect_loop(timeout)

    def read(self, size=-1):
        """This reads at most "size" bytes from the file (less if the read hits
        EOF before obtaining size bytes). If the size argument is negative or
        omitted, read all data until EOF is reached. The bytes are returned as
        a string object. An empty string is returned when EOF is encountered
        immediately.
        """
        if size == 0:
            return self.string_type()
        if size < 0:
            # delimiter default is EOF
            self.expect(self.delimiter)
            return self.before

        # I could have done this more directly by not using expect(), but
        # I deliberately decided to couple read() to expect() so that
        # I would catch any bugs early and ensure consistent behavior.
        # It's a little less efficient, but there is less for me to
        # worry about if I have to later modify read() or expect().
        # Note, it's OK if size==-1 in the regex. That just means it
        # will never match anything in which case we stop only on EOF.
        cre = re.compile(self._coerce_expect_string('.{%d}' % size), re.DOTALL)
        # delimiter default is EOF
        index = self.expect([cre, self.delimiter])
        if index == 0:
            ### FIXME self.before should be ''. Should I assert this?
            return self.after
        return self.before

    def readline(self, size=-1):
        r"""This reads and returns one entire line.
        
        The newline at the end of line is returned as part of the string, unless the file ends without a
        newline. An empty string is returned if EOF is encountered immediately.
        This looks for a newline as a CR/LF pair (\\r\\n) even on UNIX because
        this is what the pseudotty device returns. So contrary to what you may
        expect you will receive newlines as \\r\\n.

        If the size argument is 0 then an empty string is returned. In all
        other cases the size argument is ignored, which is not standard
        behavior for a file-like object.
        """
        if size == 0:
            return self.string_type()
        # delimiter default is EOF
        index = self.expect([self.crlf, self.delimiter])
        if index == 0:
            return cast(str,self.before) + cast(str,self.crlf)

        return self.before

    def __iter__(self):
        """This is to support iterators over a file-like object."""
        return iter(self.readline, self.string_type())

    def readlines(self, sizehint=-1):
        """This reads until EOF using readline() and returns a list containing
        the lines thus read. The optional 'sizehint' argument is ignored.
        Remember, because this reads until EOF that means the child
        process should have closed its stdout. If you run this method on
        a child that is still running with its stdout open then this
        method will block until it timesout.
        """
        lines = []
        while True:
            line = self.readline()
            if not line:
                break
            lines.append(line)
        return lines

    def fileno(self):
        """Expose file descriptor for a file-like interface."""
        return self.child_fd

    def flush(self) -> None:
        """This does nothing. It is here to support the interface for a
        File-like object.
        """
        pass

    def isatty(self) -> bool:
        """Overridden in subclass using tty."""
        return False

    # For 'with spawn(...) as child:'
    def __enter__(self):
        return self

    def __exit__(self, etype, evalue, tb):
        # We rely on subclasses to implement close(). If they don't, it's not
        # clear what a context manager should do.
        self.close()




class PopenSpawn(SpawnBase):
    def __init__(self, cmd, timeout=30, maxread=2000, searchwindowsize=None,
                 logfile=None, cwd=None, env=None, encoding=None,
                 codec_errors='strict', preexec_fn=None):
        super().__init__(timeout=timeout, maxread=maxread,
                searchwindowsize=searchwindowsize, logfile=logfile,
                encoding=encoding, codec_errors=codec_errors)

        # Note that `SpawnBase` initializes `self.crlf` to `\r\n`
        # because the default behaviour for a PTY is to convert
        # incoming LF to `\r\n` (see the `onlcr` flag and
        # https://stackoverflow.com/a/35887657/5397009). Here we set
        # it to `os.linesep` because that is what the spawned
        # application outputs by default and `popen` doesn't translate
        # anything.
        if encoding is None:
            self.crlf = os.linesep.encode ("ascii")
        else:
            self.crlf = self.string_type (os.linesep)

        kwargs = {"bufsize": 0, "stdin": subprocess.PIPE,
                      "stderr": subprocess.STDOUT, "stdout": subprocess.PIPE,
                      "cwd": cwd, "preexec_fn": preexec_fn, "env": env}

        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs['startupinfo'] = startupinfo
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP

        if isinstance(cmd, string_types) and sys.platform != 'win32':
            cmd = shlex.split(cmd, posix=os.name == 'posix')

        self.proc = subprocess.Popen(cmd, **kwargs)
        self.pid = self.proc.pid
        self.closed = False
        self._buf = self.string_type()

        self._read_queue = Queue()
        self._read_thread = threading.Thread(target=self._read_incoming)
        self._read_thread.daemon = True
        self._read_thread.start()

    _read_reached_eof = False

    def read_nonblocking(self, size, timeout):
        buf = self._buf
        if self._read_reached_eof:
            # We have already finished reading. Use up any buffered data,
            # then raise EOF
            if buf:
                self._buf = buf[size:]
                return buf[:size]
            self.flag_eof = True
            raise EOF('End Of File (EOF).')

        if timeout == -1:
            timeout = self.timeout
        elif timeout is None:
            timeout = 1e6

        t0 = time.time()
        while (time.time() - t0) < timeout and size and len(buf) < size:
            try:
                incoming = self._read_queue.get_nowait()
            except Empty:
                break
            else:
                if incoming is None:
                    self._read_reached_eof = True
                    break

                buf += self._decoder.decode(incoming, final=False)

        r, self._buf = buf[:size], buf[size:]

        self._log(r, 'read')
        return r

    def _read_incoming(self):
        """Run in a thread to move output from a pipe to a queue."""
        fileno = self.proc.stdout.fileno()
        while 1:
            buf = b''
            try:
                buf = os.read(fileno, 1024)
            except OSError as e:
                self._log(e, 'read')

            if not buf:
                # This indicates we have reached EOF
                self._read_queue.put(None)
                return

            self._read_queue.put(buf)

    def write(self, s) -> None:
        """This is similar to send() except that there is no return value."""
        self.send(s)

    def writelines(self, sequence) -> None:
        """This calls write() for each element in the sequence.

        The sequence can be any iterable object producing strings, typically a
        list of strings. This does not add line separators. There is no return
        value.
        """
        for s in sequence:
            self.send(s)

    def send(self, s):
        """Send data to the subprocess' stdin.

        Returns the number of bytes written.
        """
        s = self._coerce_send_string(s)
        self._log(s, 'send')

        b = self._encoder.encode(s, final=False)
        if PY3:
            return self.proc.stdin.write(b)
        # On Python 2, .write() returns None, so we return the length of
        # bytes written ourselves. This assumes they all got written.
        self.proc.stdin.write(b)
        return len(b)

    def sendline(self, s=''):
        """Wraps send(), sending string ``s`` to child process, with os.linesep
        automatically appended. Returns number of bytes written.
        """
        n = self.send(s)
        return n + self.send(self.linesep)

    def wait(self):
        """Wait for the subprocess to finish.

        Returns the exit code.
        """
        status = self.proc.wait()
        if status >= 0:
            self.exitstatus = status
            self.signalstatus = None
        else:
            self.exitstatus = None
            self.signalstatus = -status
        self.terminated = True
        return status

    def kill(self, sig) -> None:
        """Sends a Unix signal to the subprocess.

        Use constants from the :mod:`signal` module to specify which signal.
        """
        if sys.platform == 'win32':
            if sig in [signal.SIGINT, signal.CTRL_C_EVENT]:
                sig = signal.CTRL_C_EVENT
            elif sig in [signal.SIGBREAK, signal.CTRL_BREAK_EVENT]:
                sig = signal.CTRL_BREAK_EVENT
            else:
                sig = signal.SIGTERM

        os.kill(self.proc.pid, sig)

    def close(self) -> None:
        self.proc.send_signal(signal.SIGINT)
        
    def sendeof(self) -> None:
        """Closes the stdin pipe from the writing end."""
        self.proc.stdin.close()


class APatternWaiterT(Protocol):
    transport: ReadTransport | None
    expecter: "Expecter"
    fut: asyncio.Future[int]

    def set_expecter(self, expecter: "Expecter") -> Self: ...
    def found(self, result: int) -> Self: ...
    def error(self, exc: BaseException | type[BaseException]) -> Self: ...
    def connection_made(self, transport: ReadTransport) -> Self: ...
    def data_received(self, data: bytes) -> Self: ...
    def eof_received(self) -> Self: ...
    def connection_lost(self, exc: BaseException | type[BaseException] | None) -> Self: ...



async def expect_async(expecter: Expecter, timeout: int | None=None) -> AsyncIterator[int]:
    # First process data that was previously read - if it maches, we don't need
    # async stuff.
    idx = expecter.existing_data()
    if idx is not None:
        logging.debug(f"idx {idx}")
        yield idx
        return
    if not expecter.spawn.async_pw_transport:
        pw = APatternWaiter()
        pw.set_expecter(expecter)
        transport, pw = await asyncio.get_event_loop().connect_read_pipe(lambda: pw, expecter.spawn)
        expecter.spawn.async_pw_transport = pw, transport
        logging.debug("set transport and pw")
    else:
        pw, transport = expecter.spawn.async_pw_transport
        pw.set_expecter(expecter)
        transport.resume_reading()
        logging.debug("resumed reading")
    try:
        yield await asyncio.wait_for(pw.fut, timeout)
        return 
    except TimeoutError as e:
        transport.pause_reading()
        yield expecter.timeout(e)
        return 



async def repl_run_command_async(repl, cmdlines, timeout=-1):
    res = []
    repl.child.sendline(cmdlines[0])
    for line in cmdlines[1:]:
        yield repl._expect_prompt(timeout=timeout, async_=True)
        res.append(repl.child.before)
        repl.child.sendline(line)

    # Command was fully submitted, now wait for the next prompt
    prompt_idx = yield repl._expect_prompt(timeout=timeout, async_=True)
    if prompt_idx == 1:
        # We got the continuation prompt - command was incomplete
        repl.child.kill(signal.SIGINT)
        yield repl._expect_prompt(timeout=1, async_=True)
        raise ValueError("Continuation prompt found - input was incomplete:")
    yield "".join(res + [repl.child.before])
    return

class APatternWaiter(asyncio.Protocol):
    transport: BaseTransport

    def set_expecter(self, expecter: Expecter):
        self.expecter = expecter
        self.fut = asyncio.Future()
        return self

    def found(self, result)  -> Self:
        if not self.fut.done():
            self.fut.set_result(result)
            self.transport.pause_reading()
        return self

    def error(self, exc) -> Self:
        if not self.fut.done():
            self.fut.set_exception(exc)
            self.transport.pause_reading()
        return self
    def connection_made(self, transport: BaseTransport)  -> None:
        self.transport = transport


    def data_received(self, data) -> None:
        logging.debug("received data")
        spawn = self.expecter.spawn
        s = spawn._decoder.decode(data)
        # spawn._log(s, "read")

        if self.fut.done():
            logging.debug("fut done")
            # spawn._before.write(s)
            # spawn._buffer.write(s)
            return

        try:
            index = self.expecter.new_data(s)
            if index is not None:
                logging.debug("found match")
                # Found a match
                self.found(index)
        except Exception as e:
            logging.debug("errored")
            self.expecter.errored()
            self.error(e)

    def eof_received(self) -> None:
        # N.B. If this gets called, async will close the pipe (the spawn object)
        # for us
        try:
            self.expecter.spawn.flag_eof = True
            index = self.expecter.eof()
        except EOF as e:
            self.error(e)
        else:
            self.found(index)

    def connection_lost(self, exc) -> None:
        logging.debug("connection lost")
        if isinstance(exc, OSError) and exc.errno == errno.EIO:
            # We may get here without eof_received being called, e.g on Linux
            self.eof_received()
        elif exc is not None:
            self.error(exc)

if sys.platform != "win32":

    import pty

    import ptyprocess
    from ptyprocess.ptyprocess import use_native_pty_fork


    @contextmanager
    def _wrap_ptyprocess_err():
        """Turn ptyprocess errors into our own ExceptionPexpect errors."""
        try:
            yield
        except ptyprocess.PtyProcessError as e:
            raise ExceptionPexpect(*e.args)


    PY3 = sys.version_info[0] >= 3


    class PtySpawn(SpawnBase): # noqa
        """This is the main class interface for Pexpect."""

        # This is purely informational now - changing it has no effect
        use_native_pty_fork = use_native_pty_fork

        def __init__(
            self,
            command: str | None,
            args: list[str] | None = None,
            timeout: int | float | None = 30,
            maxread: int = 2000,
            searchwindowsize: int | None = None,
            logfile: _Logfile | None = None,
            cwd: str | None = None,
            env: dict[str, str] | None = None,
            ignore_sighup: bool = False,
            echo: bool = True,
            preexec_fn: Callable[[], None] | None = None,
            encoding: str | None = None,
            codec_errors: str = "strict",
            dimensions: tuple[int, int] | None = None,
            use_poll: bool = False,
        ):
            """The command parameter may be a string that includes a command and any arguments to the command.
            
            Example::

            child = pexpect.spawn("/usr/bin/ftp")
            child = pexpect.spawn("/usr/bin/ssh user@example.com")
            child = pexpect.spawn("ls -latr /tmp")

            You may also construct it with a list of arguments like so::

            child = pexpect.spawn("/usr/bin/ftp", [])
            child = pexpect.spawn("/usr/bin/ssh", ["user@example.com"])
            child = pexpect.spawn("ls", ["-latr", "/tmp"])

            After this the child application will be created and will be ready to
            talk to. For normal use, see expect() and send() and sendline().

            Remember that Pexpect does NOT interpret shell meta characters such as
            redirect, pipe, or wild cards (``>``, ``|``, or ``*``). This is a
            common mistake.  If you want to run a command and pipe it through
            another command then you must also start a shell. For example::

            child = pexpect.spawn('/bin/bash -c "ls -l | grep LOG > logs.txt"')
            child.expect(pexpect.EOF)

            The second form of spawn (where you pass a list of arguments) is useful
            in situations where you wish to spawn a command and pass it its own
            argument list. This can make syntax more clear. For example, the
            following is equivalent to the previous example::

            shell_cmd = "ls -l | grep LOG > logs.txt"
            child = pexpect.spawn("/bin/bash", ["-c", shell_cmd])
            child.expect(pexpect.EOF)

            The maxread attribute sets the read buffer size. This is maximum number
            of bytes that Pexpect will try to read from a TTY at one time. Setting
            the maxread size to 1 will turn off buffering. Setting the maxread
            value higher may help performance in cases where large amounts of
            output are read back from the child. This feature is useful in
            conjunction with searchwindowsize.

            When the keyword argument *searchwindowsize* is None (default), the
            full buffer is searched at each iteration of receiving incoming data.
            The default number of bytes scanned at each iteration is very large
            and may be reduced to collaterally reduce search cost.  After
            :meth:`~.expect` returns, the full buffer attribute remains up to
            size *maxread* irrespective of *searchwindowsize* value.

            When the keyword argument ``timeout`` is specified as a number,
            (default: *30*), then :class:`TIMEOUT` will be raised after the value
            specified has elapsed, in seconds, for any of the :meth:`~.expect`
            family of method calls.  When None, TIMEOUT will not be raised, and
            :meth:`~.expect` may block indefinitely until match.


            The logfile member turns on or off logging. All input and output will
            be copied to the given file object. Set logfile to None to stop
            logging. This is the default. Set logfile to sys.stdout to echo
            everything to standard output. The logfile is flushed after each write.

            Example log input and output to a file::

            child = pexpect.spawn("some_command")
            fout = open("mylog.txt", "wb")
            child.logfile = fout

            Example log to stdout::

            # In Python 2:
            child = pexpect.spawn("some_command")
            child.logfile = sys.stdout

            # In Python 3, we'll use the ``encoding`` argument to decode data
            # from the subprocess and handle it as unicode:
            child = pexpect.spawn("some_command", encoding="utf-8")
            child.logfile = sys.stdout

            The logfile_read and logfile_send members can be used to separately log
            the input from the child and output sent to the child. Sometimes you
            don't want to see everything you write to the child. You only want to
            log what the child sends back. For example::

            child = pexpect.spawn("some_command")
            child.logfile_read = sys.stdout

            You will need to pass an encoding to spawn in the above code if you are
            using Python 3.

            To separately log output sent to the child use logfile_send::

            child.logfile_send = fout

            If ``ignore_sighup`` is True, the child process will ignore SIGHUP
            signals. The default is False from Pexpect 4.0, meaning that SIGHUP
            will be handled normally by the child.

            The delaybeforesend helps overcome a weird behavior that many users
            were experiencing. The typical problem was that a user would expect() a
            "Password:" prompt and then immediately call sendline() to send the
            password. The user would then see that their password was echoed back
            to them. Passwords don't normally echo. The problem is caused by the
            fact that most applications print out the "Password" prompt and then
            turn off stdin echo, but if you send your password before the
            application turned off echo, then you get your password echoed.
            Normally this wouldn't be a problem when interacting with a human at a
            real keyboard. If you introduce a slight delay just before writing then
            this seems to clear up the problem. This was such a common problem for
            many users that I decided that the default pexpect behavior should be
            to sleep just before writing to the child application. 1/20th of a
            second (50 ms) seems to be enough to clear up the problem. You can set
            delaybeforesend to None to return to the old behavior.

            Note that spawn is clever about finding commands on your path.
            It uses the same logic that "which" uses to find executables.

            If you wish to get the exit status of the child you must call the
            close() method. The exit or signal status of the child will be stored
            in self.exitstatus or self.signalstatus. If the child exited normally
            then exitstatus will store the exit return code and signalstatus will
            be None. If the child was terminated abnormally with a signal then
            signalstatus will store the signal value and exitstatus will be None::

            child = pexpect.spawn("some_command")
            child.close()
            print(child.exitstatus, child.signalstatus)

            If you need more detail you can also read the self.status member which
            stores the status returned by os.waitpid. You can interpret this using
            os.WIFEXITED/os.WEXITSTATUS or os.WIFSIGNALED/os.TERMSIG.

            The echo attribute may be set to False to disable echoing of input.
            As a pseudo-terminal, all input echoed by the "keyboard" (send()
            or sendline()) will be repeated to output.  For many cases, it is
            not desirable to have echo enabled, and it may be later disabled
            using setecho(False) followed by waitnoecho().  However, for some
            platforms such as Solaris, this is not possible, and should be
            disabled immediately on spawn.

            If preexec_fn is given, it will be called in the child process before
            launching the given command. This is useful to e.g. reset inherited
            signal handlers.

            The dimensions attribute specifies the size of the pseudo-terminal as
            seen by the subprocess, and is specified as a two-entry tuple (rows,
            columns). If this is unspecified, the defaults in ptyprocess will apply.

            The use_poll attribute enables using select.poll() over select.select()
            for socket handling. This is handy if your system could have > 1024 fds
            """
            super().__init__(
            timeout=timeout,
            maxread=maxread,
            searchwindowsize=searchwindowsize,
            logfile=logfile,
            encoding=encoding,
            codec_errors=codec_errors,
            )
            self.STDIN_FILENO = pty.STDIN_FILENO
            self.STDOUT_FILENO = pty.STDOUT_FILENO
            self.STDERR_FILENO = pty.STDERR_FILENO
            self.str_last_chars = 100
            self.cwd = cwd
            self.env = env
            self.echo = echo
            self.ignore_sighup = ignore_sighup
            self.__irix_hack = sys.platform.lower().startswith("irix")
            if command is None:
                self.command = None
                self.args = None
                self.name = "<pexpect factory incomplete>"
            else:
                self._spawn(command, args, preexec_fn, dimensions)
            self.use_poll = use_poll

        def __str__(self):
            """A human-readable string that represents the state of the object."""
            s = []
            s.append(repr(self))
            s.append("command: " + str(self.command))
            s.append(f"args: {self.args!r}")
            s.append(f"buffer (last {self.str_last_chars} chars): {self.buffer[-self.str_last_chars :]!r}")
            s.append(
                "before (last {} chars): {!r}".format(self.str_last_chars, self.before[-self.str_last_chars :] if self.before else ""),
            )
            s.append(f"after: {self.after!r}")
            s.append(f"match: {self.match!r}")
            s.append("match_index: " + str(self.match_index))
            s.append("exitstatus: " + str(self.exitstatus))
            if hasattr(self, "ptyproc"):
                s.append("flag_eof: " + str(self.flag_eof))
            s.append("pid: " + str(self.pid))
            s.append("child_fd: " + str(self.child_fd))
            s.append("closed: " + str(self.closed))
            s.append("timeout: " + str(self.timeout))
            s.append("delimiter: " + str(self.delimiter))
            s.append("logfile: " + str(self.logfile))
            s.append("logfile_read: " + str(self.logfile_read))
            s.append("logfile_send: " + str(self.logfile_send))
            s.append("maxread: " + str(self.maxread))
            s.append("ignorecase: " + str(self.ignorecase))
            s.append("searchwindowsize: " + str(self.searchwindowsize))
            s.append("delaybeforesend: " + str(self.delaybeforesend))
            s.append("delayafterclose: " + str(self.delayafterclose))
            s.append("delayafterterminate: " + str(self.delayafterterminate))
            return "\n".join(s)

        def _spawn(self, command, args=None, preexec_fn=None, dimensions=None):
            """This starts the given command in a child process.
            
            This does all the fork/exec type of stuff for a pty. This is called by __init__. If args
            is empty then command will be parsed (split on spaces) and args will be
            set to parsed arguments.
            """
            # The pid and child_fd of this object get set by this method.
            # Note that it is difficult for this method to fail.
            # You cannot detect if the child process cannot start.
            # So the only way you can tell if the child process started
            # or not is to try to read from the file descriptor. If you get
            # EOF immediately then it means that the child is already dead.
            # That may not necessarily be bad because you may have spawned a child
            # that performs some task; creates no stdout output; and then dies.

            # If command is an int type then it may represent a file descriptor.
            if args is None:
                args = []
            if isinstance(command, int):
                raise ExceptionPexpect(
                    "Command is an int type. "
                    + "If this is a file descriptor then maybe you want to "
                    + "use fdpexpect.fdspawn which takes an existing "
                    + "file descriptor instead of a command string.",
                )

            args = list(args) if args else []
            if args == []:
                self.args = split_command_line(command)
                self.command = self.args[0]
            else:
                # Make a shallow copy of the args list.
                self.args = args[:]
                self.args.insert(0, command)
                self.command = command

            command_with_path = which(self.command, env=self.env)
            if command_with_path is None:
                raise ExceptionPexpect("The command was not found or was not " + f"executable: {self.command}.")
            self.command = command_with_path
            self.args[0] = self.command

            self.name = "<" + " ".join(self.args) + ">"

            assert self.pid is None, "The pid member must be None."
            assert self.command is not None, "The command member must not be None."

            kwargs = {"echo": self.echo, "preexec_fn": preexec_fn}
            if self.ignore_sighup:

                def preexec_wrapper():
                    """Set SIGHUP to be ignored, then call the real preexec_fn."""
                    signal.signal(signal.SIGHUP, signal.SIG_IGN)
                    if preexec_fn is not None:
                        preexec_fn()

                kwargs["preexec_fn"] = preexec_wrapper

            if dimensions is not None:
                kwargs["dimensions"] = dimensions

            if self.encoding is not None:
                # Encode command line using the specified encoding
                self.args = [a if isinstance(a, bytes) else a.encode(self.encoding) for a in self.args]

            self.ptyproc = self._spawnpty(self.args, env=self.env, cwd=self.cwd, **kwargs)

            self.pid = self.ptyproc.pid
            self.child_fd = self.ptyproc.fd

            self.terminated = False
            self.closed = False

        def _spawnpty(self, args, **kwargs):
            """Spawn a pty and return an instance of PtyProcess."""
            return ptyprocess.PtyProcess.spawn(args, **kwargs)

        def close(self, force=True) -> None:
            """This closes the connection with the child application.
            
            Calling close() more than once is valid. This emulates standard Python
            behavior with files. Set force to True if you want to make sure that
            the child is terminated (SIGKILL is sent if the child ignores SIGHUP
            and SIGINT).
            """
            self.flush()
            with _wrap_ptyprocess_err():
                # PtyProcessError may be raised if it is not possible to terminate
                # the child.
                self.ptyproc.close(force=force)
            self.isalive()  # Update exit status from ptyproc
            self.child_fd = -1
            self.closed = True

        def isatty(self):
            """Is the file descriptor is open and connected to a tty(-like) device?

            On SVR4-style platforms implementing streams, such as SunOS and HP-UX,
            the child pty may not appear as a terminal device.  This means
            methods such as setecho(), setwinsize(), getwinsize() may raise an
            IOError.
            """ 
            return os.isatty(self.child_fd)

        def waitnoecho(self, timeout=-1) -> bool | None:
            """Waits until the terminal ECHO flag is set False.

            Returns True if the echo mode is off. This returns False if the ECHO flag was
            not set False before the timeout. This can be used to detect when the
            child is waiting for a password. Usually a child application will turn
            off echo mode when it is waiting for the user to enter a password. For
            example, instead of expecting the "password:" prompt you can wait for
            the child to set ECHO off::

                p = pexpect.spawn("ssh user@example.com")
                p.waitnoecho()
                p.sendline(mypassword)

            If timeout==-1 then this method will use the value in self.timeout.
            If timeout==None then this method to block until ECHO flag is False.
            """
            if timeout == -1:
                timeout = self.timeout
            if timeout is not None:
                end_time = time.time() + timeout
            while True:
                if not self.getecho():
                    return True
                if timeout < 0 and timeout is not None:
                    return False
                if timeout is not None:
                    timeout = end_time - time.time()
                time.sleep(0.1)

        def getecho(self):
            """This returns the terminal echo mode.
            
            This returns True if echo is on or False if echo is off.
            Child applications that are expecting you
            to enter a password often set ECHO False. See waitnoecho().

            Not supported on platforms where ``isatty()`` returns False.
            """
            return self.ptyproc.getecho()

        def setecho(self, state):
            """This sets the terminal echo mode on or off.
            
            Note that anything the child sent before the echo will be lost, so you should be sure that
            your input buffer is empty before you call setecho(). For example, the
            following will work as expected::

                p = pexpect.spawn("cat")  # Echo is on by default.
                p.sendline("1234")  # We expect see this twice from the child...
                p.expect(["1234"])  # ... once from the tty echo...
                p.expect(["1234"])  # ... and again from cat itself.
                p.setecho(False)  # Turn off tty echo
                p.sendline("abcd")  # We will set this only once (echoed by cat).
                p.sendline("wxyz")  # We will set this only once (echoed by cat)
                p.expect(["abcd"])
                p.expect(["wxyz"])

            The following WILL NOT WORK because the lines sent before the setecho
            will be lost::

                p = pexpect.spawn("cat")
                p.sendline("1234")
                p.setecho(False)  # Turn off tty echo
                p.sendline("abcd")  # We will set this only once (echoed by cat).
                p.sendline("wxyz")  # We will set this only once (echoed by cat)
                p.expect(["1234"])
                p.expect(["1234"])
                p.expect(["abcd"])
                p.expect(["wxyz"])


            Not supported on platforms where ``isatty()`` returns False.
            """
            return self.ptyproc.setecho(state)

        def read_nonblocking(self, size=1, timeout=-1):
            """Read at most size characters from the child application.

            iIncludes a timeout. If the read does not complete within the timeout
            period then a TIMEOUT exception is raised. If the end of file is read
            then an EOF exception will be raised.  If a logfile is specified, a
            copy is written to that log.

            If timeout is None then the read may block indefinitely.
            If timeout is -1 then the self.timeout value is used. If timeout is 0
            then the child is polled and if there is no data immediately ready
            then this will raise a TIMEOUT exception.

            The timeout refers only to the amount of time to read at least one
            character. This is not affected by the 'size' parameter, so if you call
            read_nonblocking(size=100, timeout=30) and only one character is
            available right away then one character will be returned immediately.
            It will not wait for 30 seconds for another 99 characters to come in.

            On the other hand, if there are bytes available to read immediately,
            all those bytes will be read (up to the buffer size). So, if the
            buffer size is 1 megabyte and there is 1 megabyte of data available
            to read, the buffer will be filled, regardless of timeout.

            This is a wrapper around os.read(). It uses select.select() or
            select.poll() to implement the timeout.
            """
            if self.closed:
                raise ValueError("I/O operation on closed file.")

            if self.use_poll:

                def select(timeout):
                    return poll_ignore_interrupts([self.child_fd], timeout)
            else:

                def select(timeout):
                    return select_ignore_interrupts([self.child_fd], [], [], timeout)[0]

            # If there is data available to read right now, read as much as
            # we can. We do this to increase performance if there are a lot
            # of bytes to be read. This also avoids calling isalive() too
            # often. See also:
            # * https://github.com/pexpect/pexpect/pull/304
            # * http://trac.sagemath.org/ticket/10295
            if select(0):
                try:
                    incoming = super().read_nonblocking(size)
                except EOF:
                    # Maybe the child is dead: update some attributes in that case
                    self.isalive()
                    raise
                while len(incoming) < size and select(0):
                    try:
                        incoming += super().read_nonblocking(size - len(incoming))
                    except EOF:
                        # Maybe the child is dead: update some attributes in that case
                        self.isalive()
                        # Don't raise EOF, just return what we read so far.
                        return incoming
                return incoming

            if timeout == -1:
                timeout = self.timeout

            if not self.isalive():
                # The process is dead, but there may or may not be data
                # available to read. Note that some systems such as Solaris
                # do not give an EOF when the child dies. In fact, you can
                # still try to read from the child_fd -- it will block
                # forever or until TIMEOUT. For that reason, it's important
                # to do this check before calling select() with timeout.
                if select(0):
                    return super().read_nonblocking(size)
                self.flag_eof = True
                raise EOF("End Of File (EOF). Braindead platform.")
            if self.__irix_hack:
                # Irix takes a long time before it realizes a child was terminated.
                # Make sure that the timeout is at least 2 seconds.
                # FIXME So does this mean Irix systems are forced to always have
                # FIXME a 2 second delay when calling read_nonblocking? That sucks.
                if timeout is not None and timeout < 2:
                    timeout = 2

            # Because of the select(0) check above, we know that no data
            # is available right now. But if a non-zero timeout is given
            # (possibly timeout=None), we call select() with a timeout.
            if (timeout != 0) and select(timeout):
                return super().read_nonblocking(size)

            if not self.isalive():
                # Some platforms, such as Irix, will claim that their
                # processes are alive; timeout on the select; and
                # then finally admit that they are not alive.
                self.flag_eof = True
                raise EOF("End of File (EOF). Very slow platform.")
            raise TIMEOUT("Timeout exceeded.")

        def write(self, s) -> None:
            """This is similar to send() except that there is no return value."""
            self.send(s)

        def writelines(self, sequence) -> None:
            """Call write() for each element in the sequence.
            
            The sequence can be any iterable object producing strings, typically a list of
            strings. This does not add line separators. There is no return value.
            """
            for s in sequence:
                self.write(s)

        def send(self, s):
            r"""Sends string ``s`` to the child process, returning the number of  bytes written.
            
            If a logfile is specified, a copy is written to that
            log.

            The default terminal input mode is canonical processing unless set
            otherwise by the child process. This allows backspace and other line
            processing to be performed prior to transmitting to the receiving
            program. As this is buffered, there is a limited size of such buffer.

            On Linux systems, this is 4096 (defined by N_TTY_BUF_SIZE). All
            other systems honor the POSIX.1 definition PC_MAX_CANON -- 1024
            on OSX, 256 on OpenSolaris, and 1920 on FreeBSD.

            This value may be discovered using fpathconf(3)::

                >>> from os import fpathconf
                >>> print(fpathconf(0, 'PC_MAX_CANON'))
                256

            On such a system, only 256 bytes may be received per line. Any
            subsequent bytes received will be discarded. BEL (``'\a'``) is then
            sent to output if IMAXBEL (termios.h) is set by the tty driver.
            This is usually enabled by default.  Linux does not honor this as
            an option -- it behaves as though it is always set on.

            Canonical input processing may be disabled altogether by executing
            a shell, then stty(1), before executing the final program::

                >>> bash = pexpect.spawn('/bin/bash', echo=False)
                >>> bash.sendline('stty -icanon')
                >>> bash.sendline('base64')
                >>> bash.sendline('x' * 5000)
            """
            if self.delaybeforesend is not None:
                time.sleep(self.delaybeforesend)

            s = self._coerce_send_string(s)
            self._log(s, "send")

            b = self._encoder.encode(s, final=False)
            return os.write(self.child_fd, b)

        def sendline(self, s=""):
            """Wraps send(), sending string ``s`` to child process, with ``os.linesep`` automatically appended.
            
            Returns number of bytes
            written.  Only a limited number of bytes may be sent for each
            line in the default terminal mode, see docstring of :meth:`send`.
            """
            s = self._coerce_send_string(s)
            return self.send(s + self.linesep)

        def _log_control(self, s):
            """Write control characters to the appropriate log files."""
            if self.encoding is not None:
                s = s.decode(self.encoding, "replace")
            self._log(s, "send")

        def sendcontrol(self, char):
            r"""Helper method that wraps send() with mnemonic access for sending control.
            
            (e.g. Ctrl-C or Ctrl-D).  For example, to send Ctrl-G (ASCII 7, bell, '\a')::

            child.sendcontrol("g")

            See also, sendintr() and sendeof().
            """
            n, byte = self.ptyproc.sendcontrol(char)
            self._log_control(byte)
            return n

        def sendeof(self) -> None:
            """This sends an EOF to the child.
            
            This sends a character which causes
            the pending parent output buffer to be sent to the waiting child
            program without waiting for end-of-line. If it is the first character
            of the line, the read() in the user program returns 0, which signifies
            end-of-file. This means to work as expected a sendeof() has to be
            called at the beginning of a line. This method does not send a newline.
            It is the responsibility of the caller to ensure the eof is sent at the
            beginning of a line.
            """
            n, byte = self.ptyproc.sendeof()
            self._log_control(byte)

        def sendintr(self) -> None:
            """This sends a SIGINT to the child.
            
            It does not require the SIGINT to be the first character on a line.
            """
            n, byte = self.ptyproc.sendintr()
            self._log_control(byte)

        @property
        def flag_eof(self):
            return self.ptyproc.flag_eof

        @flag_eof.setter
        def flag_eof(self, value):
            self.ptyproc.flag_eof = value

        def eof(self):
            """This returns True if the EOF exception was ever raised."""
            return self.flag_eof

        def terminate(self, force=False):
            """This forces a child process to terminate.
            
            It starts nicely with SIGHUP and SIGINT. If "force" is True then moves onto SIGKILL. This
            returns True if the child was terminated. This returns False if the
            child could not be terminated.
            """
            if not self.isalive():
                return True
            try:
                self.kill(signal.SIGHUP)
                time.sleep(self.delayafterterminate)
                if not self.isalive():
                    return True
                self.kill(signal.SIGCONT)
                time.sleep(self.delayafterterminate)
                if not self.isalive():
                    return True
                self.kill(signal.SIGINT)
                time.sleep(self.delayafterterminate)
                if not self.isalive():
                    return True
                if force:
                    self.kill(signal.SIGKILL)
                    time.sleep(self.delayafterterminate)
                    return bool(not self.isalive())
                return False
            except OSError:
                # I think there are kernel timing issues that sometimes cause
                # this to happen. I think isalive() reports True, but the
                # process is dead to the kernel.
                # Make one last attempt to see if the kernel is up to date.
                time.sleep(self.delayafterterminate)
                return bool(not self.isalive())

        def wait(self):
            """Waits until the child exits.
            
            This is a blocking call. This will
            not read any data from the child, so this will block forever if the
            child has unread output and has terminated. In other words, the child
            may have printed output then called exit(), but, the child is
            technically still alive until its output is read by the parent.

            This method is non-blocking if :meth:`wait` has already been called
            previously or :meth:`isalive` method returns False.  It simply returns
            the previously determined exit status.
            """
            ptyproc = self.ptyproc
            with _wrap_ptyprocess_err():
                # exception may occur if "Is some other process attempting
                # "job control with our child pid?"
                exitstatus = ptyproc.wait()
            self.status = ptyproc.status
            self.exitstatus = ptyproc.exitstatus
            self.signalstatus = ptyproc.signalstatus
            self.terminated = True

            return exitstatus

        def isalive(self):
            """This tests if the child process is running or not.
            
            This is non-blocking. If the child was terminated then this will read the
            exitstatus or signalstatus of the child. This returns True if the child
            process appears to be running or False if not. It can take literally
            SECONDS for Solaris to return the right status.
            """
            ptyproc = self.ptyproc
            with _wrap_ptyprocess_err():
                alive = ptyproc.isalive()

            if not alive:
                self.status = ptyproc.status
                self.exitstatus = ptyproc.exitstatus
                self.signalstatus = ptyproc.signalstatus
                self.terminated = True

            return alive

        def kill(self, sig) -> None:
            """This sends the given signal to the child application.
            
            In keeping with UNIX tradition it has a misleading name. It does not necessarily
            kill the child unless you send the right signal.
            """
            # Same as os.kill, but the pid is given for you.
            if self.isalive():
                os.kill(self.pid, sig)

        def getwinsize(self):
            """This returns the terminal window size of the child tty.
            
            The return alue is a tuple of (rows, cols).
            """
            return self.ptyproc.getwinsize()

        def setwinsize(self, rows, cols):
            """This sets the terminal window size of the child tty.
            
            This will cause a SIGWINCH signal to be sent to the child. This does not change the
            physical window size. It changes the size reported to TTY-aware
            applications like vi or curses -- applications that respond to the
            SIGWINCH signal.
            """
            return self.ptyproc.setwinsize(rows, cols)

        def interact(self, escape_character=chr(29), input_filter=None, output_filter=None) -> None:
            """Gives control of the child process to the interactive user (the human at the keyboard).
            
            Keystrokes are sent to the child process, and
            the stdout and stderr output of the child process is printed. This
            simply echos the child stdout and child stderr to the real stdout and
            it echos the real stdin to the child stdin. When the user types the
            escape_character this method will return None. The escape_character
            will not be transmitted.  The default for escape_character is
            entered as ``Ctrl - ]``, the very same as BSD telnet. To prevent
            escaping, escape_character may be set to None.

            If a logfile is specified, then the data sent and received from the
            child process in interact mode is duplicated to the given log.

            You may pass in optional input and output filter functions. These
            functions should take bytes array and return bytes array too. Even
            with ``encoding='utf-8'`` support, meth:`interact` will always pass
            input_filter and output_filter bytes. You may need to wrap your
            function to decode and encode back to UTF-8.

            The output_filter will be passed all the output from the child process.
            The input_filter will be passed all the keyboard input from the user.
            The input_filter is run BEFORE the check for the escape_character.

            Note that if you change the window size of the parent the SIGWINCH
            signal will not be passed through to the child. If you want the child
            window size to change when the parent's window size changes then do
            something like the following example::

                import pexpect, struct, fcntl, termios, signal, sys


                def sigwinch_passthrough(sig, data):
                    s = struct.pack("HHHH", 0, 0, 0, 0)
                    a = struct.unpack("hhhh", fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, s))
                    if not p.closed:
                        p.setwinsize(a[0], a[1])


                # Note this 'p' is global and used in sigwinch_passthrough.
                p = pexpect.spawn("/bin/bash")
                signal.signal(signal.SIGWINCH, sigwinch_passthrough)
                p.interact()
            """
            # Flush the buffer.
            self.write_to_stdout(self.buffer)
            self.stdout.flush()
            self._buffer = self.buffer_type()
            mode = tty.tcgetattr(self.STDIN_FILENO)
            tty.setraw(self.STDIN_FILENO)
            if escape_character is not None and PY3:
                escape_character = escape_character.encode("latin-1")
            try:
                self.__interact_copy(escape_character, input_filter, output_filter)
            finally:
                tty.tcsetattr(self.STDIN_FILENO, tty.TCSAFLUSH, mode)

        def __interact_writen(self, fd, data):
            """This is used by the interact() method."""
            while data != b"" and self.isalive():
                n = os.write(fd, data)
                data = data[n:]

        def __interact_read(self, fd):
            """This is used by the interact() method."""
            return os.read(fd, 1000)

        def __interact_copy(self, escape_character=None, input_filter=None, output_filter=None):
            """This is used by the interact() method."""
            while self.isalive():
                if self.use_poll:
                    r = poll_ignore_interrupts([self.child_fd, self.STDIN_FILENO])
                else:
                    r, w, e = select_ignore_interrupts([self.child_fd, self.STDIN_FILENO], [], [])
                if self.child_fd in r:
                    try:
                        data = self.__interact_read(self.child_fd)
                    except OSError as err:
                        if err.args[0] == errno.EIO:
                            # Linux-style EOF
                            break
                        raise
                    if data == b"":
                        # BSD-style EOF
                        break
                    if output_filter:
                        data = output_filter(data)
                    self._log(data, "read")
                    os.write(self.STDOUT_FILENO, data)
                if self.STDIN_FILENO in r:
                    data = self.__interact_read(self.STDIN_FILENO)
                    if input_filter:
                        data = input_filter(data)
                    i = -1
                    if escape_character is not None:
                        i = data.rfind(escape_character)
                    if i != -1:
                        data = data[:i]
                        if data:
                            self._log(data, "send")
                        self.__interact_writen(self.child_fd, data)
                        break
                    self._log(data, "send")
                    self.__interact_writen(self.child_fd, data)

else:
    PtySpawn = PopenSpawn
class AOpenSpawn(PtySpawn):
    """Async version of spawn."""
    async def aexpect(self, pattern, timeout=1, searchwindowsize=200) -> AsyncIterator[int]:
        compiled_pattern_list = self.compile_pattern_list(pattern)
        async for item in self.aexpect_list(compiled_pattern_list, timeout, searchwindowsize):
            yield item
        return

    async def aexpect_list(self, pattern_list, timeout=1, searchwindowsize=200) -> AsyncIterator[int]:
        exp = Expecter(self, searcher_re(pattern_list), searchwindowsize)

        try:
            async for item in expect_async(exp, timeout=timeout):
                self.before = self.before or exp.spawn.before
                yield item
            logging.debug("DONE EXPECTING ASYNC")
        except (EOF, TIMEOUT,KeyboardInterrupt) as e:
            # Assign the collected output to `before` before raising
            logging.debug("EOF OR TIMEOUT REC AEPCEPT")
            self.before = self.before or exp.spawn.before
            # traceback.print_exc()
            raise e
        return
def is_executable_file(path):
    """Checks that path is an executable regular file, or a symlink towards one.

    This is roughly ``os.path isfile(path) and os.access(path, os.X_OK)``.
    """
    # follow symlinks,
    fpath = os.path.realpath(path)

    if not Path(fpath).exists():
        # non-files (directories, fifo, etc.)
        return False

    mode = Path.stat(fpath).st_mode

    if sys.platform.startswith("sunos") and os.getuid() == 0:
        # When root on Solaris, os.X_OK is True for *all* files, irregardless
        # of their executability -- instead, any permission bit of any user,
        # group, or other is fine enough.
        #
        # (This may be true for other "Unix98" OS's such as HP-UX and AIX)
        return bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))

    return os.access(fpath, os.X_OK)


def which(filename, env=None):
    """Find a file in PATH.

    This takes a given filename; tries to find it in the environment path;
    then checks if it is executable. This returns the full path to the filename
    if found and executable. Otherwise this returns None.
    """
    # Special case where filename contains an explicit path.
    cmd = Path(filename)
    if cmd.exists() and is_executable_file(cmd):
        return filename
    if filename in aliases:
        return filename
    if env is None:
        env = os.environ
    p = env.get("PATH")
    if p is not None:
        p = os.defpath
    pathlist = p.split(os.pathsep)
    for path in pathlist:
        ff = path / cmd
        if is_executable_file(ff):
            return str(ff)
    if filename in os.environ:
        return filename
    return aliases.get(filename)


def split_command_line(command_line) -> list[Any]:
    """Split command line into a list of arguments.
    
    This splits a command line into a list of arguments. It splits arguments
    on spaces, but handles embedded quotes, doublequotes, and escaped
    characters. It's impossible to do this with a regular expression, so I
    wrote a little state machine to parse the command line.
    """
    arg_list = []
    arg = ""

    # Constants to name the states we can be in.
    state_basic = 0
    state_esc = 1
    state_singlequote = 2
    state_doublequote = 3
    # The state when consuming whitespace between commands.
    state_whitespace = 4
    state = state_basic

    for c in command_line:
        if state in (state_basic, state_whitespace):
            if c == "\\":
                # Escape the next character
                state = state_esc
            elif c == r"'":
                # Handle single quote
                state = state_singlequote
            elif c == r'"':
                # Handle double quote
                state = state_doublequote
            elif c.isspace():
                # Add arg to arg_list if we aren't in the middle of whitespace.
                if state == state_whitespace:
                    # Do nothing.
                    None
                else:
                    arg_list.append(arg)
                    arg = ""
                    state = state_whitespace
            else:
                arg = arg + c
                state = state_basic
        elif state == state_esc:
            arg = arg + c
            state = state_basic
        elif state == state_singlequote:
            if c == r"'":
                state = state_basic
            else:
                arg = arg + c
        elif state == state_doublequote:
            if c == r'"':
                state = state_basic
            else:
                arg = arg + c

    if arg != "":
        arg_list.append(arg)
    return arg_list


def select_ignore_interrupts(iwtd, owtd, ewtd, timeout=None):
    """This is a wrapper around select.select() that ignores signals. If
    select.select raises a select.error exception and errno is an EINTR
    error then it is ignored. Mainly this is used to ignore sigwinch
    (terminal resize).
    """
    # if select() is interrupted by a signal (errno==EINTR) then
    # we loop back and enter the select() again.
    if timeout is not None:
        end_time = time.time() + timeout
    while True:
        try:
            return select.select(iwtd, owtd, ewtd, timeout)
        except InterruptedError:
            err = sys.exc_info()[1]
            if err.args[0] == errno.EINTR:
                # if we loop back we have to subtract the
                # amount of time we already waited.
                if timeout is not None:
                    timeout = end_time - time.time()
                    if timeout < 0:
                        return ([], [], [])
            else:
                # something else caused the select.error, so
                # this actually is an exception.
                raise


def poll_ignore_interrupts(fds, timeout=None):
    """Simple wrapper around poll to register file descriptors and
    ignore signals.
    """
    if timeout is not None:
        end_time = time.time() + timeout

    poller = select.poll()
    for fd in fds:
        poller.register(fd, select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLERR)

    while True:
        try:
            timeout_ms = None if timeout is None else timeout * 1000
            results = poller.poll(timeout_ms)
            return [afd for afd, _ in results]
        except InterruptedError:
            err = sys.exc_info()[1]
            if err.args[0] == errno.EINTR:
                # if we loop back we have to subtract the
                # amount of time we already waited.
                if timeout is not None:
                    timeout = end_time - time.time()
                    if timeout < 0:
                        return []
            else:
                # something else caused the select.error, so
                # this actually is an exception.
                raise


class SocketSpawn(SpawnBase):
    """This is like :mod:`pexpect.fdpexpect` but uses the cross-platform python socket api,
    rather than the unix-specific file descriptor api. Thus, it works with
    remote connections on both unix and windows.
    """

    def __init__(
        self,
        socket: socket.socket,
        args=None,
        timeout=30,
        maxread=2000,
        searchwindowsize=None,
        logfile=None,
        encoding=None,
        codec_errors="strict",
        use_poll=False,
    ):
        """This takes an open socket."""
        self.args = None
        self.command = None
        SpawnBase.__init__(
            self,
            timeout,
            maxread,
            searchwindowsize,
            logfile,
            encoding=encoding,
            codec_errors=codec_errors,
        )
        self.socket = socket
        self.child_fd = socket.fileno()
        self.closed = False
        self.name = f"<socket {socket}>"
        self.use_poll = use_poll

    def close(self) -> None:
        """Close the socket.

        Calling this method a second time does nothing, but if the file
        descriptor was closed elsewhere, :class:`OSError` will be raised.
        """
        if self.child_fd == -1:
            return

        self.flush()
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()
        self.child_fd = -1
        self.closed = True

    def isalive(self):
        """Alive if the fileno is valid."""
        return self.socket.fileno() >= 0

    def send(self, s) -> int:
        """Write to socket, return number of bytes written."""
        s = self._coerce_send_string(s)
        self._log(s, "send")

        b = self._encoder.encode(s, final=False)
        self.socket.sendall(b)
        return len(b)

    def sendline(self, s) -> int:
        """Write to socket with trailing newline, return number of bytes written."""
        s = self._coerce_send_string(s)
        return self.send(s + self.linesep)

    def write(self, s) -> None:
        """Write to socket, return None."""
        self.send(s)

    def writelines(self, sequence) -> None:
        """Call self.write() for each item in sequence."""
        for s in sequence:
            self.write(s)

    @contextmanager
    def _timeout(self, timeout):
        saved_timeout = self.socket.gettimeout()
        try:
            self.socket.settimeout(timeout)
            yield
        finally:
            self.socket.settimeout(saved_timeout)

    def read_nonblocking(self, size=1, timeout=-1):
        """Read from the file descriptor and return the result as a string.

        The read_nonblocking method of :class:`SpawnBase` assumes that a call
        to os.read will not block (timeout parameter is ignored). This is not
        the case for POSIX file-like objects such as sockets and serial ports.

        Use :func:`select.select`, timeout is implemented conditionally for
        POSIX systems.

        :param int size: Read at most *size* bytes.
        :param int timeout: Wait timeout seconds for file descriptor to be
            ready to read. When -1 (default), use self.timeout. When 0, poll.
        :return: String containing the bytes read
        """
        if timeout == -1:
            timeout = self.timeout
        try:
            with self._timeout(timeout):
                s = self.socket.recv(size)
                if s == b"":
                    self.flag_eof = True
                    raise EOF("Socket closed")
                return s
        except TimeoutError:
            raise TIMEOUT("Timeout exceeded.")


spawn: TypeAlias = PtySpawn
aspawn: TypeAlias = AOpenSpawn
socket_spawn: TypeAlias = SocketSpawn






if __name__ == "__main__":
    # p = spawn("ls -l")
    # p.expect(EOF)
    # print(p.before)
    from rich.console import Console
    from rich.text import Text
    console = Console()
    from mbpy import SPINNER
    
    async def main() -> None:
        await SPINNER.astart()
        ap = aspawn("python3 -m pip list")
        async for _ in  ap.aexpect(EOF):
            SPINNER.stop()
            console.print(Text.from_ansi(ap.before.decode("utf-8") or ""))

    asyncio.run(main())

