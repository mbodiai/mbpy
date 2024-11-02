"""Provides an interface like pexpect.spawn interface using subprocess.Popen."""

import codecs
import errno
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
import traceback
from io import BytesIO, StringIO
from queue import Empty, Queue
from typing import Any

string_types =(str,)

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





class Expecter(object):
    def __init__(self, spawn: "SpawnBase", searcher, searchwindowsize=-1):
        self.spawn = spawn
        self.searcher: searcher_re = searcher
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
            if not self.searchwindowsize:
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
        spawn.after = EOFError
        index = self.searcher.eof_index
        if index >= 0:
            spawn.match = EOFError
            spawn.match_index = index
            return index

        spawn.match = None
        spawn.match_index = None
        msg = str(spawn)
        msg += f"\nsearcher: {self.searcher}"
        if err is not None:
            msg = str(err) + "\n" + msg

        exc = EOFError(msg)
        exc.__cause__ = None  # in Python 3.x we can use "raise exc from None"
        raise exc

    def timeout(self, err=None) -> int:
        spawn = self.spawn

        spawn.before = spawn._before.getvalue()
        spawn.after = TimeoutError
        index = self.searcher.timeout_index
        if index >= 0:
            spawn.match = TimeoutError
            spawn.match_index = index
            return index

        spawn.match = None
        spawn.match_index = None
        msg = str(spawn)
        msg += f"\nsearcher: {self.searcher}"
        if err is not None:
            msg = str(err) + "\n" + msg

        raise TimeoutError(msg)

    def errored(self) -> None:
        spawn = self.spawn
        spawn.before = spawn._before.getvalue()
        spawn.after = None
        spawn.match = None
        spawn.match_index = None

    def expect_loop(self, timeout=-1) -> Any | int:
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
        except EOFError as e:
            return self.eof(e)
        except TimeoutError as e:
            return self.timeout(e)
        except:
            self.errored()
            raise


class searcher_string(object): # noqa: N801 UP004
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

    def __init__(self, strings):
        """This creates an instance of searcher_string.
        
        This argument 'strings'
        may be a list; a sequence of strings; or the EOFError or TimeoutErrortypes.
        """
        self.eof_index = -1
        self.timeout_index = -1
        self._strings = []
        self.longest_string = 0
        for n, s in enumerate(strings):
            if s is EOFError:
                self.eof_index = n
                continue
            if s is TimeoutError:
                self.timeout_index = n
                continue
            self._strings.append((n, s))
            if len(s) > self.longest_string:
                self.longest_string = len(s)

    def __str__(self):
        """This returns a human-readable string that represents the state of the object."""
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
        """This searches 'buffer' for the first occurrence of one of the search strings.

        'freshlen' must indicate the number of bytes at the end of
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
            # the match, if any, can only be in the fresh data,
            # or at the very end of the old data
            offset = -(freshlen + len(s)) if searchwindowsize is None else -searchwindowsize
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


class searcher_re(object): # noqa: N801 UP004
    """This is regular expression string search helper for the spawn.expect_any() method.
    
    This helper class is for powerful
       pattern matching. For speed, see the helper class, searcher_string.

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
        """This creates an instance that searches for 'patterns' Where
        'patterns' may be a list or other sequence of compiled regular
        expressions, or the EOFError or TimeoutErrortypes.
        """  # noqa: D205
        self.eof_index = -1
        self.timeout_index = -1
        self._searches = []
        for n, s in enumerate(patterns):
            if s is EOFError:
                self.eof_index = n
                continue
            if s is TimeoutError:
                self.timeout_index = n
                continue
            self._searches.append((n, s))

    def __str__(self):
        """This returns a human-readable string that represents the state of
        the object.
        """  # noqa: D205
        # ss = [(n, '    %d: re.compile("%s")' %
        #    (n, repr(s.pattern))) for n, s in self._searches]
        ss = list()
        for n, s in self._searches:
            ss.append((n, "    %d: re.compile(%r)" % (n, s.pattern)))
        ss.append((-1, "searcher_re:"))
        if self.eof_index >= 0:
            ss.append((self.eof_index, "    %d: EOF" % self.eof_index))
        if self.timeout_index >= 0:
            ss.append((self.timeout_index, "    %d: TIMEOUT" % self.timeout_index))
        ss.sort()
        ss = list(zip(*ss))[1]
        return "\n".join(ss)

    def search(self, buffer, freshlen, searchwindowsize=None):
        """This searches 'buffer' for the first occurrence of one of the regular
        expressions. 'freshlen' must indicate the number of bytes at the end of
        'buffer' which have not been searched before.

        See class spawn for the 'searchwindowsize' argument.

        If there is a match this returns the index of that string, and sets
        'start', 'end' and 'match'. Otherwise, returns -1.
        """  # noqa: D205
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


PY3 = sys.version_info[0] >= 3
text_type = str


class _NullCoder(object):
    """Pass bytes through unchanged."""

    @staticmethod
    def encode(b, final=False):
        return b

    @staticmethod
    def decode(b, final=False):
        return b


class SpawnBase(object):
    """A base class providing the backwards-compatible spawn API for Pexpect.

    This should not be instantiated directly: use :class:`pexpect.spawn` or
    :class:`pexpect.fdpexpect.fdspawn`.
    """

    encoding = None
    pid = None
    flag_eof = False

    def __init__(
        self, timeout=30, maxread=2000, searchwindowsize=None, logfile=None, encoding=None, codec_errors="strict"
    ):
        self.stdin = sys.stdin
        self.stdout = sys.stdout
        self.stderr = sys.stderr

        self.searcher = None
        self.ignorecase = False
        self.before = None
        self.after = None
        self.match = None
        self.match_index = None
        self.terminated = True
        self.exitstatus = None
        self.signalstatus = None
        # status returned by os.waitpid
        self.status = None
        # the child file descriptor is initially closed
        self.child_fd = -1
        self.timeout = timeout
        self.delimiter = EOFError
        self.logfile = logfile
        # input from child (read_nonblocking)
        self.logfile_read = None
        # output to send (send, sendline)
        self.logfile_send = None
        # max bytes to read at one time into buffer
        self.maxread = maxread
        # Data before searchwindowsize point is preserved, but not searched.
        self.searchwindowsize = searchwindowsize
        # Delay used before sending data to child. Time in seconds.
        # Set this to None to skip the time.sleep() call completely.
        self.delaybeforesend = 0.05
        # Used by close() to give kernel time to update process status.
        # Time in seconds.
        self.delayafterclose = 0.1
        # Used by terminate() to give kernel time to update process status.
        # Time in seconds.
        self.delayafterterminate = 0.1
        # Delay in seconds to sleep after each call to read_nonblocking().
        # Set this to None to skip the time.sleep() call completely: that
        # would restore the behavior from pexpect-2.0 (for performance
        # reasons or because you don't want to release Python's global
        # interpreter lock).
        self.delayafterread = 0.0001
        self.softspace = False
        self.name = "<" + repr(self) + ">"
        self.closed = True

        # Unicode interface
        self.encoding = encoding
        self.codec_errors = codec_errors
        if encoding is None:
            # bytes mode (accepts some unicode for backwards compatibility)
            self._encoder = self._decoder = _NullCoder()
            self.string_type = bytes
            self.buffer_type = BytesIO
            self.crlf = b"\r\n"
            if PY3:
                self.allowed_string_types = (bytes, str)
                self.linesep = os.linesep.encode("ascii")

                def write_to_stdout(b):
                    try:
                        return sys.stdout.buffer.write(b)
                    except AttributeError:
                        # If stdout has been replaced, it may not have .buffer
                        return sys.stdout.write(b.decode("ascii", "replace"))

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
            self.crlf = "\r\n"
            self.allowed_string_types = (text_type,)
            if PY3:
                self.linesep = os.linesep
            else:
                self.linesep = os.linesep.decode("ascii")
            # This can handle unicode in both Python 2 and 3
            self.write_to_stdout = sys.stdout.write
        # storage for async transport
        self.async_pw_transport = None
        # This is the read buffer. See maxread.
        self._buffer = self.buffer_type()
        # The buffer may be trimmed for efficiency reasons.  This is the
        # untrimmed buffer, used to create the before attribute.
        self._before = self.buffer_type()

    def _log(self, s, direction):
        if self.logfile is not None:
            self.logfile.write(s)
            self.logfile.flush()
        second_log = self.logfile_send if (direction == "send") else self.logfile_read
        if second_log is not None:
            second_log.write(s)
            second_log.flush()

    # For backwards compatibility, in bytes mode (when encoding is None)
    # unicode is accepted for send and expect. Unicode mode is strictly unicode
    # only.
    def _coerce_expect_string(self, s):
        if self.encoding is None and not isinstance(s, bytes):
            return s.encode("ascii")
        return s

    # In bytes mode, regex patterns should also be of bytes type
    def _coerce_expect_re(self, r):
        p = r.pattern
        if self.encoding is None and not isinstance(p, bytes):
            return re.compile(p.encode("utf-8"))
        # And vice-versa
        elif self.encoding is not None and isinstance(p, bytes):
            return re.compile(p.decode("utf-8"))
        return r

    def _coerce_send_string(self, s):
        if self.encoding is None and not isinstance(s, bytes):
            return s.encode("utf-8")
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
                raise EOF("End Of File (EOF). Exception style platform.")
            raise
        if s == b"":
            # BSD-style EOF
            self.flag_eof = True
            raise EOF("End Of File (EOF). Empty string style platform.")

        s = self._decoder.decode(s, final=False)
        self._log(s, "read")
        return s

    def _pattern_type_err(self, pattern):
        raise TypeError(
            "got {badtype} ({badobj!r}) as pattern, must be one"
            " of: {goodtypes}, pexpect.EOF, pexpect.TIMEOUT".format(
                badtype=type(pattern),
                badobj=pattern,
                goodtypes=", ".join([str(ast) for ast in self.allowed_string_types]),
            )
        )

    def compile_pattern_list(self, patterns):
        """This compiles a pattern-string or a list of pattern-strings.

        Patterns must be a StringType, EOF, TIMEOUT, SRE_Pattern, or a list of
        those. Patterns may also be None which results in an empty list (you
        might do this if waiting for an EOFError or TimeoutErrorcondition without
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
        for idx, p in enumerate(patterns):
            if isinstance(p, self.allowed_string_types):
                p = self._coerce_expect_string(p)
                compiled_pattern_list.append(re.compile(p, compile_flags))
            elif p is EOFError:
                compiled_pattern_list.append(EOFError)
            elif p is TimeoutError:
                compiled_pattern_list.append(TimeoutError)
            elif isinstance(p, type(re.compile(""))):
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
        successful match. This may raise exceptions for EOFError or TIMEOUT. To
        avoid the EOFError or TimeoutErrorexceptions add EOFError or TimeoutErrorto the pattern
        list. That will cause expect to match an EOFError or TimeoutError condition
        instead of raising an exception.

        If you pass a list of patterns and more than one matches, the first
        match in the stream is chosen. If more than one pattern matches at that
        point, the leftmost in the pattern list is chosen. For example::

            # the input is 'foobar'
            index = p.expect(["bar", "foo", "foobar"])
            # returns 1('foo') even though 'foobar' is a "better" match

        Please note, however, that buffering can affect this behavior, since
        input arrives in unpredictable chunks. For example::

            # the input is 'foobar'
            index = p.expect(["foobar", "foo"])
            # returns 0('foobar') if all input is available at once,
            # but returns 1('foo') if parts of the final 'bar' arrive late

        When a match is found for the given pattern, the class instance
        attribute *match* becomes an re.MatchObject result.  Should an EOF
        or TimeoutError pattern match, then the match attribute will be an instance
        of that exception class.  The pairing before and after class
        instance attributes are views of the data preceding and following
        the matching pattern.  On general exception, class attribute
        *before* is all data received up to the exception, while *match* and
        *after* attributes are value None.

        When the keyword argument timeout is -1 (default), then TimeoutError will
        raise after the default value specified by the class timeout
        attribute. When None, TimeoutError will not be raised and may block
        indefinitely until match.

        When the keyword argument searchwindowsize is -1 (default), then the
        value specified by the class maxread attribute is used.

        A list entry may be EOFError or TimeoutError instead of a string. This will
        catch these exceptions and return the index of the list entry instead
        of raising the exception. The attribute 'after' will be set to the
        exception type. The attribute 'match' will be None. This allows you to
        write code like this::

                index = p.expect(["good", "bad", pexpect.EOF, pexpect.TIMEOUT])
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
                    index = p.expect(["good", "bad"])
                    if index == 0:
                        do_something()
                    elif index == 1:
                        do_something_else()
                except EOF:
                    do_some_other_thing()
                except TIMEOUT:
                    do_something_completely_different()

        These two forms are equivalent. It all depends on what you want. You
        can also just expect the EOFError if you are waiting for all output of a
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
        if "async" in kw:
            async_ = kw.pop("async")
        if kw:
            raise TypeError("Unknown keyword arguments: {}".format(kw))

        compiled_pattern_list = self.compile_pattern_list(pattern)
        return self.expect_list(compiled_pattern_list, timeout, searchwindowsize, async_)

    def expect_list(self, pattern_list, timeout=-1, searchwindowsize=-1, async_=False, **kw):
        """This takes a list of compiled regular expressions and returns the
        index into the pattern_list that matched the child output. The list may
        also contain EOFError or TIMEOUT(which are not compiled regular
        expressions). This method is similar to the expect() method except that
        expect_list() does not recompile the pattern list on every call. This
        may help if you are trying to optimize for speed, otherwise just use
        the expect() method.  This is called by expect().


        Like :meth:`expect`, passing ``async_=True`` will make this return an
        asyncio coroutine.
        """  # noqa: D205
        if timeout == -1:
            timeout = self.timeout
        if "async" in kw:
            async_ = kw.pop("async")
        if kw:
            raise TypeError("Unknown keyword arguments: {}".format(kw))

        exp = Expecter(self, searcher_re(pattern_list), searchwindowsize)
        if async_:
            from ._async import expect_async

            return expect_async(exp, timeout)
        else:
            return exp.expect_loop(timeout)

    def expect_exact(self, pattern_list, timeout=-1, searchwindowsize=-1, async_=False, **kw):
        """This is similar to expect(), but uses plain string matching instead
        of compiled regular expressions in 'pattern_list'. The 'pattern_list'
        may be a string; a list or other sequence of strings; or TimeoutError and
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
        if "async" in kw:
            async_ = kw.pop("async")
        if kw:
            raise TypeError("Unknown keyword arguments: {}".format(kw))

        if isinstance(pattern_list, self.allowed_string_types) or pattern_list in (TIMEOUT, EOF):
            pattern_list = [pattern_list]

        def prepare_pattern(pattern):
            if pattern in (TIMEOUT, EOF):
                return pattern
            if isinstance(pattern, self.allowed_string_types):
                return self._coerce_expect_string(pattern)
            self._pattern_type_err(pattern)

        try:
            pattern_list = iter(pattern_list)
        except TypeError:
            self._pattern_type_err(pattern_list)
        pattern_list = [prepare_pattern(p) for p in pattern_list]

        exp = Expecter(self, searcher_string(pattern_list), searchwindowsize)
        if async_:
            from ._async import expect_async

            return expect_async(exp, timeout)
        else:
            return exp.expect_loop(timeout)

    def expect_loop(self, searcher, timeout=-1, searchwindowsize=-1):
        """This is the common loop used inside expect. The 'searcher' should be
        an instance of searcher_re or searcher_string, which describes how and
        what to search for in the input.

        See expect() for other arguments, return value and exceptions."""

        exp = Expecter(self, searcher, searchwindowsize)
        return exp.expect_loop(timeout)

    def read(self, size=-1):
        """This reads at most "size" bytes from the file (less if the read hits
        EOFError before obtaining size bytes). If the size argument is negative or
        omitted, read all data until EOFError is reached. The bytes are returned as
        a string object. An empty string is returned when EOFError is encountered
        immediately."""

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
        cre = re.compile(self._coerce_expect_string(".{%d}" % size), re.DOTALL)
        # delimiter default is EOF
        index = self.expect([cre, self.delimiter])
        if index == 0:
            ### FIXME self.before should be ''. Should I assert this?
            return self.after
        return self.before

    def readline(self, size=-1):
        """This reads and returns one entire line. The newline at the end of
        line is returned as part of the string, unless the file ends without a
        newline. An empty string is returned if EOFError is encountered immediately.
        This looks for a newline as a CR/LF pair (\\r\\n) even on UNIX because
        this is what the pseudotty device returns. So contrary to what you may
        expect you will receive newlines as \\r\\n.

        If the size argument is 0 then an empty string is returned. In all
        other cases the size argument is ignored, which is not standard
        behavior for a file-like object."""

        if size == 0:
            return self.string_type()
        # delimiter default is EOF
        index = self.expect([self.crlf, self.delimiter])
        if index == 0:
            return self.before + self.crlf
        else:
            return self.before

    def __iter__(self):
        """This is to support iterators over a file-like object."""
        return iter(self.readline, self.string_type())

    def readlines(self, sizehint=-1):
        """This reads until EOFError using readline() and returns a list containing
        the lines thus read. The optional 'sizehint' argument is ignored.
        Remember, because this reads until EOFError that means the child
        process should have closed its stdout. If you run this method on
        a child that is still running with its stdout open then this
        method will block until it timesout.
        """  # noqa: D205
        lines = []
        while True:
            line = self.readline()
            if not line:
                break
            lines.append(line)
        return lines

    def fileno(self):
        """Expose file descriptor for a file-like interface"""
        return self.child_fd

    def flush(self):
        """This does nothing. It is here to support the interface for a
        File-like object."""
        pass

    def isatty(self):
        """Overridden in subclass using tty"""
        return False

    # For 'with spawn(...) as child:'
    def __enter__(self):
        return self

    def __exit__(self, etype, evalue, tb):
        # We rely on subclasses to implement close(). If they don't, it's not
        # clear what a context manager should do.
        self.close()


class PopenSpawn(SpawnBase):
    def __init__(
        self,
        cmd,
        timeout=30,
        maxread=2000,
        searchwindowsize=None,
        logfile=None,
        cwd=None,
        env=None,
        encoding=None,
        codec_errors="strict",
        preexec_fn=None,
    ):
        super().__init__(
            timeout=timeout,
            maxread=maxread,
            searchwindowsize=searchwindowsize,
            logfile=logfile,
            encoding=encoding,
            codec_errors=codec_errors,
        )

        # Note that `SpawnBase` initializes `self.crlf` to `\r\n`
        # because the default behaviour for a PTY is to convert
        # incoming LF to `\r\n` (see the `onlcr` flag and
        # https://stackoverflow.com/a/35887657/5397009). Here we set
        # it to `os.linesep` because that is what the spawned
        # application outputs by default and `popen` doesn't translate
        # anything.
        if encoding is None:
            self.crlf = os.linesep.encode("ascii")
        else:
            self.crlf = self.string_type(os.linesep)

        kwargs = dict(
            bufsize=0,
            stdin=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
            cwd=cwd,
            preexec_fn=preexec_fn,
            env=env,
        )

        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs["startupinfo"] = startupinfo
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        if isinstance(cmd, string_types) and sys.platform != "win32":
            cmd = shlex.split(cmd, posix=os.name == "posix")

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
            else:
                self.flag_eof = True
                raise EOF("End Of File (EOF).")

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

        self._log(r, "read")
        return r

    def _read_incoming(self):
        """Run in a thread to move output from a pipe to a queue."""
        fileno = self.proc.stdout.fileno()
        while 1:
            buf = b""
            try:
                buf = os.read(fileno, 1024)
            except OSError as e:
                self._log(e, "read")

            if not buf:
                # This indicates we have reached EOF
                self._read_queue.put(None)
                return

            self._read_queue.put(buf)

    def write(self, s):
        """This is similar to send() except that there is no return value."""
        self.send(s)

    def writelines(self, sequence):
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
        self._log(s, "send")

        b = self._encoder.encode(s, final=False)
        if PY3:
            return self.proc.stdin.write(b)
        else:
            # On Python 2, .write() returns None, so we return the length of
            # bytes written ourselves. This assumes they all got written.
            self.proc.stdin.write(b)
            return len(b)

    def sendline(self, s=""):
        """Wraps send(), sending string ``s`` to child process, with os.linesep
        automatically appended. Returns number of bytes written."""

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

    def kill(self, sig):
        """Sends a Unix signal to the subprocess.

        Use constants from the :mod:`signal` module to specify which signal.
        """
        if sys.platform == "win32":
            if sig in [signal.SIGINT, signal.CTRL_C_EVENT]:
                sig = signal.CTRL_C_EVENT
            elif sig in [signal.SIGBREAK, signal.CTRL_BREAK_EVENT]:
                sig = signal.CTRL_BREAK_EVENT
            else:
                sig = signal.SIGTERM

        os.kill(self.proc.pid, sig)

    def sendeof(self):
        """Closes the stdin pipe from the writing end."""
        self.proc.stdin.close()


class PopenSpawn(SpawnBase):
    def __init__(
        self,
        cmd,
        timeout=30,
        maxread=2000,
        searchwindowsize=None,
        logfile=None,
        cwd=None,
        env=None,
        encoding=None,
        codec_errors="strict",
        preexec_fn=None,
    ):
        super(PopenSpawn, self).__init__(
            timeout=timeout,
            maxread=maxread,
            searchwindowsize=searchwindowsize,
            logfile=logfile,
            encoding=encoding,
            codec_errors=codec_errors,
        )

        # Note that `SpawnBase` initializes `self.crlf` to `\r\n`
        # because the default behaviour for a PTY is to convert
        # incoming LF to `\r\n` (see the `onlcr` flag and
        # https://stackoverflow.com/a/35887657/5397009). Here we set
        # it to `os.linesep` because that is what the spawned
        # application outputs by default and `popen` doesn't translate
        # anything.
        if encoding is None:
            self.crlf = os.linesep.encode("ascii")
        else:
            self.crlf = self.string_type(os.linesep)

        kwargs = dict(
            bufsize=0,
            stdin=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
            cwd=cwd,
            preexec_fn=preexec_fn,
            env=env,
        )

        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs["startupinfo"] = startupinfo
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        if isinstance(cmd, string_types) and sys.platform != "win32":
            cmd = shlex.split(cmd, posix=os.name == "posix")

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
            else:
                self.flag_eof = True
                raise EOFError("End Of File (EOF).")

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

        self._log(r, "read")
        return r

    def _read_incoming(self):
        """Run in a thread to move output from a pipe to a queue."""
        fileno = self.proc.stdout.fileno()
        while 1:
            buf = b""
            try:
                buf = os.read(fileno, 1024)
            except OSError as e:
                self._log(e, "read")

            if not buf:
                # This indicates we have reached EOF
                self._read_queue.put(None)
                return

            self._read_queue.put(buf)

    def write(self, s):
        """This is similar to send() except that there is no return value."""
        self.send(s)

    def writelines(self, sequence):
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
        self._log(s, "send")

        b = self._encoder.encode(s, final=False)
        if PY3:
            return self.proc.stdin.write(b)
        else:
            # On Python 2, .write() returns None, so we return the length of
            # bytes written ourselves. This assumes they all got written.
            self.proc.stdin.write(b)
            return len(b)

    def sendline(self, s=""):
        """Wraps send(), sending string ``s`` to child process, with os.linesep
        automatically appended. Returns number of bytes written."""

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

    def kill(self, sig):
        """Sends a Unix signal to the subprocess.

        Use constants from the :mod:`signal` module to specify which signal.
        """
        if sys.platform == "win32":
            if sig in [signal.SIGINT, signal.CTRL_C_EVENT]:
                sig = signal.CTRL_C_EVENT
            elif sig in [signal.SIGBREAK, signal.CTRL_BREAK_EVENT]:
                sig = signal.CTRL_BREAK_EVENT
            else:
                sig = signal.SIGTERM

        os.kill(self.proc.pid, sig)

    def sendeof(self):
        """Closes the stdin pipe from the writing end."""
        self.proc.stdin.close()



import os
import sys
import stat
import select
import time
import errno

try:
    InterruptedError
except NameError:
    # Alias Python2 exception to Python3
    InterruptedError = select.error

if sys.version_info[0] >= 3:
    string_types = (str,)
else:
    string_types = (unicode, str)


def is_executable_file(path):
    """Checks that path is an executable regular file, or a symlink towards one.

    This is roughly ``os.path isfile(path) and os.access(path, os.X_OK)``.
    """
    # follow symlinks,
    fpath = os.path.realpath(path)

    if not os.path.isfile(fpath):
        # non-files (directories, fifo, etc.)
        return False

    mode = os.stat(fpath).st_mode

    if sys.platform.startswith("sunos") and os.getuid() == 0:
        # When root on Solaris, os.X_OK is True for *all* files, irregardless
        # of their executability -- instead, any permission bit of any user,
        # group, or other is fine enough.
        #
        # (This may be true for other "Unix98" OS's such as HP-UX and AIX)
        return bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))

    return os.access(fpath, os.X_OK)


def which(filename, env=None):
    """This takes a given filename; tries to find it in the environment path;
    then checks if it is executable. This returns the full path to the filename
    if found and executable. Otherwise this returns None."""

    # Special case where filename contains an explicit path.
    if os.path.dirname(filename) != "" and is_executable_file(filename):
        return filename
    if env is None:
        env = os.environ
    p = env.get("PATH")
    if not p:
        p = os.defpath
    pathlist = p.split(os.pathsep)
    for path in pathlist:
        ff = os.path.join(path, filename)
        if is_executable_file(ff):
            return ff
    return None


def split_command_line(command_line):
    """This splits a command line into a list of arguments. It splits arguments
    on spaces, but handles embedded quotes, doublequotes, and escaped
    characters. It's impossible to do this with a regular expression, so I
    wrote a little state machine to parse the command line."""

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
        if state == state_basic or state == state_whitespace:
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
    (terminal resize)."""

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
    ignore signals."""

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

def spawn(*args, **kwargs) -> PopenSpawn:
    return PopenSpawn(*args, **kwargs)


if __name__ == "__main__":
    p = spawn("ls -l")
    p.expect(EOFError)
    print(p.before)
