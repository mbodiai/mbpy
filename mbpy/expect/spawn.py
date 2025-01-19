"""Copied and modified to work with asyncio and windows from pexpect."""
import asyncio
import codecs
import errno
import logging
import os
import re
import signal
import socket
from subprocess import Popen, PIPE, STDOUT, DEVNULL
import sys
from collections.abc import Awaitable, Callable, Iterable
from contextlib import contextmanager
from logging import Formatter, Handler
from typing import (
    Any,
    AsyncIterator,
    TypeVar,
)

from rich.console import Console

from mbpy.expect.exceptions import EOF, TIMEOUT, ExceptionPexpect
from mbpy.expect.expect import Expecter, expect_async
from mbpy.expect.pop import PopenSpawn
from mbpy.expect.searcher import searcher_re
from mbpy.expect.utils import poll_ignore_interrupts, select_ignore_interrupts, split_command_line

# Define type aliases
string_types = (str, bytes)
AnyStrT = TypeVar("AnyStrT", str, bytes)
AnyStrT_co = TypeVar("AnyStrT_co", str, bytes, covariant=True)
AnyStr = str | bytes


LogFile = Any


if sys.platform != "win32":


    # import os
    # import pty
    # import time
    # import tty
    # import traceback
    # from contextlib import contextmanager

    # import ptyprocess
    # from ptyprocess.ptyprocess import use_native_pty_fork

    # from mbpy.expect.exceptions import ExceptionPexpect
    # from mbpy.expect.spawnbase import SpawnBase
    # from termios import tcsetattr,tcgetattr
    # @contextmanager
    # def _wrap_ptyprocess_err():
    #     """Turn ptyprocess errors into our own ExceptionPexpect errors."""
    #     try:
    #         yield
    #     except ptyprocess.PtyProcessError as e:
    #         traceback.print_exc()
    #         raise ExceptionPexpect(*e.args) from e

    # class spawn(SpawnBase): # noqa: N801
    #     """This is the main class interface for Pexpect."""

    #     use_native_pty_fork = use_native_pty_fork

    #     def __init__(
    #         self,
    #         command: str | None,
    #         args: list[str] | None = None,
    #         timeout: int | float | None = 30,
    #         maxread: int = 2000,
    #         searchwindowsize: int | None = None,
    #         logfile: Any | None = None,
    #         cwd: str | None = None,
    #         env: dict[str, str] | None = None,
    #         ignore_sighup: bool = False,
    #         echo: bool = True,
    #         preexec_fn: Callable[[], None] | None = None,
    #         encoding: str | None = None,
    #         codec_errors: str = "strict",
    #         dimensions: tuple[int, int] | None = None,
    #         use_poll: bool = False,
    #     ):
    #         super().__init__(
    #         timeout=timeout,
    #         maxread=maxread,
    #         searchwindowsize=searchwindowsize,
    #         logfile=logfile,
    #         encoding=encoding,
    #         codec_errors=codec_errors,
    #         )
    #         self.STDIN_FILENO = pty.STDIN_FILENO
    #         self.STDOUT_FILENO = pty.STDOUT_FILENO
    #         self.STDERR_FILENO = pty.STDERR_FILENO
    #         self.str_last_chars = 100
    #         self.cwd = cwd
    #         self.env = env
    #         self.echo = echo
    #         self.ignore_sighup = ignore_sighup
    #         self.__irix_hack = sys.platform.lower().startswith("irix")
    #         if command is None:
    #             self.command = None
    #             self.args = None
    #             self.name = "<pexpect factory incomplete>"
    #         else:
    #             self._spawn(command, args, preexec_fn, dimensions)
    #         self.use_poll = use_poll

    #     def __str__(self):
    #         """A human-readable string that represents the state of the object."""
    #         s = []
    #         s.append(repr(self))
    #         s.append("command: " + str(self.command))
    #         s.append(f"args: {self.args!r}")
    #         s.append(f"buffer (last {self.str_last_chars} chars): {self.buffer[-self.str_last_chars :]!r}")
    #         s.append(
    #             "before (last {} chars): {!r}".format(self.str_last_chars, self.before[-self.str_last_chars :] if self.before else ""),
    #         )
    #         s.append(f"after: {self.after!r}")
    #         s.append(f"match: {self.match!r}")
    #         s.append("match_index: " + str(self.match_index))
    #         s.append("exitstatus: " + str(self.exitstatus))
    #         if hasattr(self, "ptyproc"):
    #             s.append("flag_eof: " + str(self.flag_eof))
    #         s.append("pid: " + str(self.pid))
    #         s.append("child_fd: " + str(self.child_fd))
    #         s.append("closed: " + str(self.closed))
    #         s.append("timeout: " + str(self.timeout))
    #         s.append("delimiter: " + str(self.delimiter))
    #         s.append("logfile: " + str(self.logfile))
    #         s.append("logfile_read: " + str(self.logfile_read))
    #         s.append("logfile_send: " + str(self.logfile_send))
    #         s.append("maxread: " + str(self.maxread))
    #         s.append("ignorecase: " + str(self.ignorecase))
    #         s.append("searchwindowsize: " + str(self.searchwindowsize))
    #         s.append("delaybeforesend: " + str(self.delaybeforesend))
    #         s.append("delayafterclose: " + str(self.delayafterclose))
    #         s.append("delayafterterminate: " + str(self.delayafterterminate))
    #         return "\n".join(s)

    #     def _spawn(self, command, args=None, preexec_fn=None, dimensions=None):
    #         """This starts the given command in a child process.
            
    #         This does all the fork/exec type of stuff for a pty. This is called by __init__. If args
    #         is empty then command will be parsed (split on spaces) and args will be
    #         set to parsed arguments.
    #         """
    #         if args is None:
    #             args = []
    #         if isinstance(command, int):
    #             raise ExceptionPexpect(
    #                 "Command is an int type. "
    #                 + "If this is a file descriptor then maybe you want to "
    #                 + "use fdpexpect.fdspawn which takes an existing "
    #                 + "file descriptor instead of a command string.",
    #             )

    #         args = list(args) if args else []
    #         if args == []:
    #             self.args = split_command_line(command)
    #             self.command = self.args[0]
    #         else:
    #             self.args = args[:]
    #             self.args.insert(0, command)
    #             self.command = command

    #         self.command = self.command
    #         self.args[0] = self.command

    #         self.name = "<" + " ".join(self.args) + ">"

    #         assert self.pid is None, "The pid member must be None."
    #         assert self.command is not None, "The command member must not be None."

    #         kwargs = {"echo": self.echo, "preexec_fn": preexec_fn}
    #         if self.ignore_sighup:

    #             def preexec_wrapper():
    #                 """Set SIGHUP to be ignored, then call the real preexec_fn."""
    #                 signal.signal(signal.SIGHUP, signal.SIG_IGN)
    #                 if preexec_fn is not None:
    #                     preexec_fn()

    #             kwargs["preexec_fn"] = preexec_wrapper

    #         if dimensions is not None:
    #             kwargs["dimensions"] = dimensions

    #         if self.encoding is not None:
    #             self.args = [a if isinstance(a, bytes) else a.encode(self.encoding) for a in self.args]

    #         self.ptyproc = self._spawnpty(self.args, env=self.env, cwd=self.cwd, **kwargs)

    #         self.pid = self.ptyproc.pid
    #         self.child_fd = self.ptyproc.fd

    #         self.terminated = False
    #         self.closed = False

    #     def _spawnpty(self, args, **kwargs):
    #         """Spawn a subprocess and return the process handle."""
    #         kwargs.pop("use_native_pty_fork", None)
    #         kwargs.pop("echo", None)
    #         return Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, **kwargs)


    #     def close(self, force=True) -> None:
    #         self.flush()
    #         with _wrap_ptyprocess_err():
    #             self.ptyproc.close(force=force)
    #         self.isalive()
    #         self.child_fd = -1
    #         self.closed = True

    #     def isatty(self):
    #         """Is the file descriptor is open and connected to a tty(-like) device?

    #         On SVR4-style platforms implementing streams, such as SunOS and HP-UX,
    #         the child pty may not appear as a terminal device.  This means
    #         methods such as setecho(), setwinsize(), getwinsize() may raise an
    #         IOError.
    #         """
    #         return os.isatty(self.child_fd)

    #     def waitnoecho(self, timeout=-1) -> bool | None:
    #         """Waits until the terminal ECHO flag is set False.

    #         Returns True if the echo mode is off. This returns False if the ECHO flag was
    #         not set False before the timeout. This can be used to detect when the
    #         child is waiting for a password. Usually a child application will turn
    #         off echo mode when it is waiting for the user to enter a password. For
    #         example, instead of expecting the "password:" prompt you can wait for
    #         the child to set ECHO off::

    #             p = pexpect.spawn("ssh user@example.com")
    #             p.waitnoecho()
    #             p.sendline(mypassword)

    #         If timeout==-1 then this method will use the value in self.timeout.
    #         If timeout==None then this method to block until ECHO flag is False.
    #         """
    #         if timeout == -1:
    #             timeout = self.timeout
    #         if timeout is not None:
    #             end_time = time.time() + timeout
    #         while True:
    #             if not self.getecho():
    #                 return True
    #             if timeout < 0 and timeout is not None:
    #                 return False
    #             if timeout is not None:
    #                 timeout = end_time - time.time()
    #             time.sleep(0.1)

    #     def getecho(self):
    #         """This returns the terminal echo mode.
            
    #         This returns True if echo is on or False if echo is off.
    #         Child applications that are expecting you
    #         to enter a password often set ECHO False. See waitnoecho().

    #         Not supported on platforms where ``isatty()`` returns False.
    #         """
    #         return self.ptyproc.getecho()

    #     def setecho(self, state):
    #         """This sets the terminal echo mode on or off.
            
    #         Note that anything the child sent before the echo will be lost, so you should be sure that
    #         your input buffer is empty before you call setecho(). For example, the
    #         following will work as expected::

    #             p = pexpect.spawn("cat")  # Echo is on by default.
    #             p.sendline("1234")  # We expect see this twice from the child...
    #             p.expect(["1234"])  # ... once from the tty echo...
    #             p.expect(["1234"])  # ... and again from cat itself.
    #             p.setecho(False)  # Turn off tty echo
    #             p.sendline("abcd")  # We will set this only once (echoed by cat).
    #             p.sendline("wxyz")  # We will set this only once (echoed by cat)
    #             p.expect(["abcd"])
    #             p.expect(["wxyz"])

    #         The following WILL NOT WORK because the lines sent before the setecho
    #         will be lost::

    #             p = pexpect.spawn("cat")
    #             p.sendline("1234")
    #             p.setecho(False)  # Turn off tty echo
    #             p.sendline("abcd")  # We will set this only once (echoed by cat).
    #             p.sendline("wxyz")  # We will set this only once (echoed by cat)
    #             p.expect(["1234"])
    #             p.expect(["1234"])
    #             p.expect(["abcd"])
    #             p.expect(["wxyz"])


    #         Not supported on platforms where ``isatty()`` returns False.
    #         """
    #         return self.ptyproc.setecho(state)

    #     def read_nonblocking(self, size=1, timeout=-1):
    #         """Read at most size characters from the child application.

    #         iIncludes a timeout. If the read does not complete within the timeout
    #         period then a TIMEOUT exception is raised. If the end of file is read
    #         then an EOF exception will be raised.  If a logfile is specified, a
    #         copy is written to that log.

    #         If timeout is None then the read may block indefinitely.
    #         If timeout is -1 then the self.timeout value is used. If timeout is 0
    #         then the child is polled and if there is no data immediately ready
    #         then this will raise a TIMEOUT exception.

    #         The timeout refers only to the amount of time to read at least one
    #         character. This is not affected by the 'size' parameter, so if you call
    #         read_nonblocking(size=100, timeout=30) and only one character is
    #         available right away then one character will be returned immediately.
    #         It will not wait for 30 seconds for another 99 characters to come in.

    #         On the other hand, if there are bytes available to read immediately,
    #         all those bytes will be read (up to the buffer size). So, if the
    #         buffer size is 1 megabyte and there is 1 megabyte of data available
    #         to read, the buffer will be filled, regardless of timeout.

    #         This is a wrapper around os.read(). It uses select.select() or
    #         select.poll() to implement the timeout.
    #         """
    #         if self.closed:
    #             raise ValueError("I/O operation on closed file.")

    #         if self.use_poll:

    #             def select(timeout):
    #                 return poll_ignore_interrupts([self.child_fd], timeout)
    #         else:

    #             def select(timeout):
    #                 return select_ignore_interrupts([self.child_fd], [], [], timeout)[0]

    #         if select(0):
    #             try:
    #                 incoming = super().read_nonblocking(size)
    #             except EOF:
    #                 self.isalive()
    #                 raise
    #             while len(incoming) < size and select(0):
    #                 try:
    #                     incoming += super().read_nonblocking(size - len(incoming))
    #                 except EOF:
    #                     self.isalive()
    #                     return incoming
    #             return incoming

    #         if timeout == -1:
    #             timeout = self.timeout

    #         if not self.isalive():
    #             if select(0):
    #                 return super().read_nonblocking(size)
    #             self.flag_eof = True
    #             raise EOF("End Of File (EOF). Braindead platform.")
    #         if self.__irix_hack:
    #             if timeout is not None and timeout < 2:
    #                 timeout = 2

    #         if (timeout != 0) and select(timeout):
    #             return super().read_nonblocking(size)

    #         if not self.isalive():
    #             self.flag_eof = True
    #             raise EOF("End of File (EOF). Very slow platform.")
    #         raise TIMEOUT("Timeout exceeded.")

    #     def write(self, s) -> None:
    #         self.send(s)

    #     def writelines(self, sequence) -> None:
    #         for s in sequence:
    #             self.write(s)

    #     def send(self, s):
    #         r"""Sends string ``s`` to the child process, returning the number of  bytes written.
            
    #         If a logfile is specified, a copy is written to that
    #         log.

    #         The default terminal input mode is canonical processing unless set
    #         otherwise by the child process. This allows backspace and other line
    #         processing to be performed prior to transmitting to the receiving
    #         program. As this is buffered, there is a limited size of such buffer.

    #         On Linux systems, this is 4096 (defined by N_TTY_BUF_SIZE). All
    #         other systems honor the POSIX.1 definition PC_MAX_CANON -- 1024
    #         on OSX, 256 on OpenSolaris, and 1920 on FreeBSD.

    #         This value may be discovered using fpathconf(3)::

    #             >>> from os import fpathconf
    #             >>> print(fpathconf(0, 'PC_MAX_CANON'))
    #             256

    #         On such a system, only 256 bytes may be received per line. Any
    #         subsequent bytes received will be discarded. BEL (``'\a'``) is then
    #         sent to output if IMAXBEL (termios.h) is set by the tty driver.
    #         This is usually enabled by default.  Linux does not honor this as
    #         an option -- it behaves as though it is always set on.

    #         Canonical input processing may be disabled altogether by executing
    #         a shell, then stty(1), before executing the final program::

    #             >>> bash = pexpect.spawn('/bin/bash', echo=False)
    #             >>> bash.sendline('stty -icanon')
    #             >>> bash.sendline('base64')
    #             >>> bash.sendline('x' * 5000)
    #         """
    #         if self.delaybeforesend is not None:
    #             time.sleep(self.delaybeforesend)

    #         s = self._coerce_send_string(s)
    #         self._log(s, "send")

    #         b = self._encoder.encode(s, final=False)
    #         return os.write(self.child_fd, b)

    #     def sendline(self, s=""):
    #         """Wraps send(), sending string ``s`` to child process, with ``os.linesep`` automatically appended.
            
    #         Returns number of bytes
    #         written.  Only a limited number of bytes may be sent for each
    #         line in the default terminal mode, see docstring of :meth:`send`.
    #         """
    #         s = self._coerce_send_string(s)
    #         return self.send(s + self.linesep)

    #     def _log_control(self, s):
    #         """Write control characters to the appropriate log files."""
    #         if self.encoding is not None:
    #             s = s.decode(self.encoding, "replace")
    #         self._log(s, "send")

    #     def sendcontrol(self, char):
    #         r"""Helper method that wraps send() with mnemonic access for sending control.
            
    #         (e.g. Ctrl-C or Ctrl-D).  For example, to send Ctrl-G (ASCII 7, bell, '\a')::

    #         child.sendcontrol("g")

    #         See also, sendintr() and sendeof().
    #         """
    #         n, byte = self.ptyproc.sendcontrol(char)
    #         self._log_control(byte)
    #         return n

    #     def sendeof(self) -> None:
    #         """This sends an EOF to the child.
            
    #         This sends a character which causes
    #         the pending parent output buffer to be sent to the waiting child
    #         program without waiting for end-of-line. If it is the first character
    #         of the line, the read() in the user program returns 0, which signifies
    #         end-of-file. This means to work as expected a sendeof() has to be
    #         called at the beginning of a line. This method does not send a newline.
    #         It is the responsibility of the caller to ensure the eof is sent at the
    #         beginning of a line.
    #         """
    #         n, byte = self.ptyproc.sendeof()
    #         self._log_control(byte)

    #     def sendintr(self) -> None:
    #         """This sends a SIGINT to the child.
            
    #         It does not require the SIGINT to be the first character on a line.
    #         """
    #         n, byte = self.ptyproc.sendintr()
    #         self._log_control(byte)

    #     @property
    #     def flag_eof(self):
    #         return self.ptyproc.flag_eof

    #     @flag_eof.setter
    #     def flag_eof(self, value):
    #         self.ptyproc.flag_eof = value

    #     def eof(self):
    #         """This returns True if the EOF exception was ever raised."""
    #         return self.flag_eof

    #     def terminate(self, force=False):
    #         """This forces a child process to terminate.
            
    #         It starts nicely with SIGHUP and SIGINT. If "force" is True then moves onto SIGKILL. This
    #         returns True if the child was terminated. This returns False if the
    #         child could not be terminated.
    #         """
    #         if not self.isalive():
    #             return True
    #         try:
    #             self.kill(signal.SIGHUP)
    #             time.sleep(self.delayafterterminate)
    #             if not self.isalive():
    #                 return True
    #             self.kill(signal.SIGCONT)
    #             time.sleep(self.delayafterterminate)
    #             if not self.isalive():
    #                 return True
    #             self.kill(signal.SIGINT)
    #             time.sleep(self.delayafterterminate)
    #             if not self.isalive():
    #                 return True
    #             if force:
    #                 self.kill(signal.SIGKILL)
    #                 time.sleep(self.delayafterterminate)
    #                 return bool(not self.isalive())
    #             return False
    #         except OSError:
    #             time.sleep(self.delayafterterminate)
    #             return bool(not self.isalive())

    #     def wait(self):
    #         """Waits until the child exits.
            
    #         This is a blocking call. This will
    #         not read any data from the child, so this will block forever if the
    #         child has unread output and has terminated. In other words, the child
    #         may have printed output then called exit(), but, the child is
    #         technically still alive until its output is read by the parent.

    #         This method is non-blocking if :meth:`wait` has already been called
    #         previously or :meth:`isalive` method returns False.  It simply returns
    #         the previously determined exit status.
    #         """
    #         ptyproc = self.ptyproc
    #         with _wrap_ptyprocess_err():
    #             exitstatus = ptyproc.wait()
    #         self.status = ptyproc.status
    #         self.exitstatus = ptyproc.exitstatus
    #         self.signalstatus = ptyproc.signalstatus
    #         self.terminated = True

    #         return exitstatus

    #     def isalive(self):
    #         """This tests if the child process is running or not.
            
    #         This is non-blocking. If the child was terminated then this will read the
    #         exitstatus or signalstatus of the child. This returns True if the child
    #         process appears to be running or False if not. It can take literally
    #         SECONDS for Solaris to return the right status.
    #         """
    #         ptyproc = self.ptyproc
    #         with _wrap_ptyprocess_err():
    #             alive = ptyproc.isalive()

    #         if not alive:
    #             self.status = ptyproc.status
    #             self.exitstatus = ptyproc.exitstatus
    #             self.signalstatus = ptyproc.signalstatus
    #             self.terminated = True

    #         return alive

    #     def kill(self, sig) -> None:
    #         """This sends the given signal to the child application.
            
    #         In keeping with UNIX tradition it has a misleading name. It does not necessarily
    #         kill the child unless you send the right signal.
    #         """
    #         if self.isalive():
    #             os.kill(self.pid, sig)

    #     def getwinsize(self):
    #         """This returns the terminal window size of the child tty.
            
    #         The return alue is a tuple of (rows, cols).
    #         """
    #         return self.ptyproc.getwinsize()

    #     def setwinsize(self, rows, cols):
    #         """This sets the terminal window size of the child tty.
            
    #         This will cause a SIGWINCH signal to be sent to the child. This does not change the
    #         physical window size. It changes the size reported to TTY-aware
    #         applications like vi or curses -- applications that respond to the
    #         SIGWINCH signal.
    #         """
    #         return self.ptyproc.setwinsize(rows, cols)

    #     def interact(self, escape_character=chr(29), input_filter=None, output_filter=None) -> None:
    #         """Gives control of the child process to the interactive user (the human at the keyboard).
            
    #         Keystrokes are sent to the child process, and
    #         the stdout and stderr output of the child process is printed. This
    #         simply echos the child stdout and child stderr to the real stdout and
    #         it echos the real stdin to the child stdin. When the user types the
    #         escape_character this method will return None. The escape_character
    #         will not be transmitted.  The default for escape_character is
    #         entered as ``Ctrl - ]``, the very same as BSD telnet. To prevent
    #         escaping, escape_character may be set to None.

    #         If a logfile is specified, then the data sent and received from the
    #         child process in interact mode is duplicated to the given log.

    #         You may pass in optional input and output filter functions. These
    #         functions should take bytes array and return bytes array too. Even
    #         with ``encoding='utf-8'`` support, meth:`interact` will always pass
    #         input_filter and output_filter bytes. You may need to wrap your
    #         function to decode and encode back to UTF-8.

    #         The output_filter will be passed all the output from the child process.
    #         The input_filter will be passed all the keyboard input from the user.
    #         The input_filter is run BEFORE the check for the escape_character.

    #         Note that if you change the window size of the parent the SIGWINCH
    #         signal will not be passed through to the child. If you want the child
    #         window size to change when the parent's window size changes then do
    #         something like the following example::

    #             import pexpect, struct, fcntl, termios, signal, sys


    #             def sigwinch_passthrough(sig, data):
    #                 s = struct.pack("HHHH", 0, 0, 0, 0)
    #                 a = struct.unpack("hhhh", fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, s))
    #                 if not p.closed:
    #                     p.setwinsize(a[0], a[1])


    #             # Note this 'p' is global and used in sigwinch_passthrough.
    #             p = pexpect.spawn("/bin/bash")
    #             signal.signal(signal.SIGWINCH, sigwinch_passthrough)
    #             p.interact()
    #         """
    #         self.write_to_stdout(self.buffer)
    #         self.stdout.flush()
    #         self._buffer = self.buffer_type()
    #         mode = tcgetattr(self.STDIN_FILENO)
    #         tty.setraw(self.STDIN_FILENO)
    #         if escape_character is not None:
    #             escape_character = escape_character.encode("latin-1")
    #         try:
    #             self.__interact_copy(escape_character, input_filter, output_filter)
    #         finally:
    #             tcsetattr(self.STDIN_FILENO, tty.TCSAFLUSH, mode)

    #     def __interact_writen(self, fd, data):
    #         """This is used by the interact() method."""
    #         while data != b"" and self.isalive():
    #             n = os.write(fd, data)
    #             data = data[n:]

    #     def __interact_read(self, fd):
    #         """This is used by the interact() method."""
    #         return os.read(fd, 1000)

    #     def __interact_copy(self, escape_character=None, input_filter=None, output_filter=None):
    #         """This is used by the interact() method."""
    #         while self.isalive():
    #             if self.use_poll:
    #                 r = poll_ignore_interrupts([self.child_fd, self.STDIN_FILENO])
    #             else:
    #                 r, w, e = select_ignore_interrupts([self.child_fd, self.STDIN_FILENO], [], [])
    #             if self.child_fd in r:
    #                 try:
    #                     data = self.__interact_read(self.child_fd)
    #                 except OSError as err:
    #                     if err.args[0] == errno.EIO:
    #                         break
    #                     raise
    #                 if data == b"":
    #                     break
    #                 if output_filter:
    #                     data = output_filter(data)
    #                 self._log(data, "read")
    #                 os.write(self.STDOUT_FILENO, data)
    #             if self.STDIN_FILENO in r:
    #                 data = self.__interact_read(self.STDIN_FILENO)
    #                 if input_filter:
    #                     data = input_filter(data)
    #                 i = -1
    #                 if escape_character is not None:
    #                     i = data.rfind(escape_character)
    #                 if i != -1:
    #                     data = data[:i]
    #                     if data:
    #                         self._log(data, "send")
    #                     self.__interact_writen(self.child_fd, data)
    #                     break
    #                 self._log(data, "send")
    #                 self.__interact_writen(self.child_fd, data)

    # # Add this line to alias 'spawn' as 'Spawn'

    spawn = PopenSpawn
    Spawn = spawn

else:
    class Spawn:
        def __init__(self, command: str, **kwargs):
            self.command = command
            self.process = None
            self.kwargs = kwargs

        async def start(self):
            self.process = await asyncio.create_subprocess_shell(
                self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **self.kwargs
            )

        async def send(self, data: str):
            self.process.stdin.write(data.encode())
            await self.process.stdin.drain()

        async def recv(self) -> str:
            data = await self.process.stdout.read(1024)
            return data.decode()

        def is_running(self) -> bool:
            return self.process and self.process.returncode is None

        async def wait(self):
            await self.process.wait()

        async def terminate(self):
            if self.process and self.is_running():
                self.process.terminate()
                await self.process.wait()

    spawn = PopenSpawn
class aspawn(spawn): # noqa
    """Async version of spawn."""
    
    def __init__(self, command, args=None, **kwargs):
        # Remove timeout from kwargs if present to avoid duplicate argument
        timeout = kwargs.pop('timeout', 30)
        
        # Ensure we have a valid command
        if not command:
            command = "echo"
            
        # Store command for async initialization
        self._command = command
        self._args = args if args else []
        self._init_kwargs = kwargs
        
        # Initialize basic state
        self._closed = False
        self._running = False
        self.process = None
        
        # Initialize parent with echo to avoid empty command
        super().__init__("echo", timeout=timeout)

    async def _async_init(self):
        if self._running:
            return
            
        # Handle command string and args properly
        command = self._command
        if isinstance(command, (str, bytes)):
            if self._args:
                command = f"{command} {' '.join(str(a) for a in self._args)}"
        else:
            command = ' '.join(str(c) for c in ([command] + self._args))
            
        # Create process
        self.process = await asyncio.create_subprocess_shell(
            command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **self._init_kwargs
        )
        self._running = True

    async def __aenter__(self):
        await self._async_init()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.cleanup()

    async def cleanup(self) -> None:
        """Safely cleanup process resources."""
        if not self._closed and hasattr(self, 'child_fd') and self.child_fd > 0:
            try:
                self.close(force=True)
                self._closed = True
            except OSError as e:
                logging.error(f"Error during cleanup: {e}")
                raise
        self._running = False

    def isalive(self):
        """Check if process is alive by checking both process state and our tracking."""
        try:
            # First check our internal state
            if self._closed or not self._running:
                return False
            
            # Then check parent process state
            if hasattr(super(), 'isalive'):
                return super().isalive()
            
            # Finally check process object directly
            return bool(self.process and self.process.returncode is None)
        except Exception:
            return False

    def is_running(self) -> bool:
        """Check if the process is still running."""
        return not self._closed and self.isalive()

    async def aexpect(self, pattern, timeout=1, searchwindowsize=200) -> AsyncIterator[int]:
        """Async expect with proper resource management."""
        await self._async_init()  # Ensure process is started
        
        if not self.is_running():
            raise OSError("Process is not running")
            
        try:
            compiled_pattern_list = self.compile_pattern_list(pattern)
            async for item in self.aexpect_list(compiled_pattern_list, timeout, searchwindowsize):
                yield item
                return
        except OSError as e:
            logging.error(f"Expect operation failed: {e}")
            await self.cleanup()
            raise
        except Exception as e:
            logging.error(f"Expect operation failed: {e}")
            await self.cleanup()
            raise
        finally:
            logging.debug("DONE EXPECTING ASYNC")
            # Remove global task cancellation
            # Only clean up if needed
            if not self.is_running():
                await self.cleanup()

    async def aexpect_list(self, pattern_list, timeout=1, searchwindowsize=200) -> AsyncIterator[int]:
        """Async expect list with better error handling."""
        exp = None
        try:
            if not self.is_running():
                raise OSError("Process is not running")
                
            exp = Expecter(self, searcher_re(pattern_list), searchwindowsize)
            async for item in expect_async(exp, timeout=timeout):
                self.before = self.before or exp.spawn.before
                yield item
        except (EOF, TIMEOUT) as e:
            logging.debug("EOF OR TIMEOUT RECEIVED")
            if exp:
                self.before = self.before or exp.spawn.before
            raise
        except OSError as e:
            logging.error(f"OS error in expect list: {e}")
            raise
        except Exception as e:
            logging.error(f"Expect list operation failed: {e}")
            raise
        finally:
            if exp and hasattr(exp, 'spawn') and hasattr(exp.spawn, 'close'):
                try:
                    if exp.spawn.is_running():
                        exp.spawn.close()
                except OSError:
                    pass

    async def terminate(self, force=False):
        """Safely terminate the process."""
        if self.is_running():
            try:
                super().terminate(force=force)
                await self.cleanup()
            except Exception as e:
                logging.error(f"Error terminating process: {e}")
                raise
        self._running = False


class udpspawn(spawn):
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
            raise TIMEOUT("Timeout exceeded.")  # noqa: B904

if __name__ == "__main__":
    import uvloop
    from rich.console import Console
    from rich.text import Text
    console = Console()
    from mbpy.helpers._display import SPINNER
    SPINNER = SPINNER()

    async def main() -> None:
        await SPINNER.astart()
        ap = aspawn("mb install mbodiai/mbodiai")
        async for _ in  ap.aexpect(EOF):
            SPINNER.stop()
            console.print(Text.from_ansi(ap.before.decode("utf-8") or ""))

    uvloop.run(main())
