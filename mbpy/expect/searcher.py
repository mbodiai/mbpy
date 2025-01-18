from typing import Protocol, TypeVar

from mbpy.expect.exceptions import EOF, TIMEOUT

_T_co = TypeVar("_T_co", covariant=True)


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


class searcher_string(SearcherStringT[_T_co]):  # noqa
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
        """This creates an instance of searcher_string.

        This argument 'strings'
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

        for index, s in self._strings:
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


class searcher_re(SearcherStringT[_T_co]):  # noqa
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
