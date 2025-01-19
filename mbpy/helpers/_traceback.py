# Copied and modified from rich
import functools
import inspect
import linecache
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from itertools import islice
from pathlib import Path
from traceback import walk_tb
from types import ModuleType, TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

from pygments.lexers import guess_lexer_for_filename
from pygments.token import Comment, Keyword, Name, Number, Operator, String, Token
from pygments.token import Text as TextToken
from pygments.util import ClassNotFound
from rich import pretty
from rich._loop import loop_last
from rich.box import Box
from rich.columns import Columns
from rich.console import Console, ConsoleOptions, ConsoleRenderable, RenderResult, group
from rich.constrain import Constrain
from rich.highlighter import RegexHighlighter, ReprHighlighter
from rich.panel import Panel
from rich.pretty import Pretty
from rich.scope import render_scope
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text, TextType
from rich.theme import Theme

if TYPE_CHECKING:
    from rich.console import ConsoleRenderable


NO_BOX = Box("    \n" * 8)
BOX_TYPE = NO_BOX


def render_scope(
    scope: "Mapping[str, Any]",
    *,
    title: Optional[TextType] = None,
    sort_keys: bool = True,
    indent_guides: bool = False,
    max_length: Optional[int] = None,
    max_string: Optional[int] = None,
) -> "ConsoleRenderable":
    """Render python variables in a given scope.

    Args:
        scope (Mapping): A mapping containing variable names and values.
        title (str, optional): Optional title. Defaults to None.
        sort_keys (bool, optional): Enable sorting of items. Defaults to True.
        indent_guides (bool, optional): Enable indentation guides. Defaults to False.
        max_length (int, optional): Maximum length of containers before abbreviating, or None for no abbreviation.
            Defaults to None.
        max_string (int, optional): Maximum length of string before truncating, or None to disable. Defaults to None.

    Returns:
        ConsoleRenderable: A renderable object.
    """
    highlighter = ReprHighlighter()
    items_table = Table.grid(padding=(0, 1), expand=False)
    items_table.add_column(justify="right")

    def sort_items(item: Tuple[str, Any]) -> Tuple[bool, str]:
        """Sort special variables first, then alphabetically."""
        key, _ = item
        return (not key.startswith("__"), key.lower())

    items = sorted(scope.items(), key=sort_items) if sort_keys else scope.items()
    for key, value in items:
        key_text = Text.assemble(
            (key, "scope.key.special" if key.startswith("__") else "scope.key"),
            (" =", "scope.equals"),
        )
        items_table.add_row(
            key_text,
            Pretty(
                value,
                highlighter=highlighter,
                indent_guides=indent_guides,
                max_length=max_length,
                max_string=max_string,
            ),
        )
    return Panel.fit(
        items_table,
        title=f"[underline]{title}[/]" if title else None,
        padding=(0, 1),
        box=BOX_TYPE,
        highlight=True,
    )


WINDOWS = sys.platform == "win32"

LOCALS_MAX_LENGTH = 100
LOCALS_MAX_STRING = 120


def install(
    *,
    console: Console | None = None,
    width: Optional[int] = 120,
    code_width: Optional[int] = 120,
    extra_lines: int = 3,
    theme: Optional[str] = None,
    word_wrap: bool = False,
    show_locals: bool = False,
    locals_max_length: int = LOCALS_MAX_LENGTH,
    locals_max_string: int = LOCALS_MAX_STRING,
    locals_hide_dunder: bool = True,
    locals_hide_sunder: Optional[bool] = None,
    indent_guides: bool = True,
    suppress: Iterable[Union[str, ModuleType]] = (),
    max_frames: int = 100,
) -> Callable[[Type[BaseException], BaseException, Optional[TracebackType]], Any]:
    """Install a rich traceback handler.

    Once installed, any tracebacks will be printed with syntax highlighting and rich formatting.


    Args:
        console (Optional[Console], optional): Console to write exception to. Default uses internal Console instance.
        width (Optional[int], optional): Width (in characters) of traceback. Defaults to 100.
        code_width (Optional[int], optional): Code width (in characters) of traceback. Defaults to 88.
        extra_lines (int, optional): Extra lines of code. Defaults to 3.
        theme (Optional[str], optional): Pygments theme to use in traceback. Defaults to ``None`` which will pick
            a theme appropriate for the platform.
        word_wrap (bool, optional): Enable word wrapping of long lines. Defaults to False.
        show_locals (bool, optional): Enable display of local variables. Defaults to False.
        locals_max_length (int, optional): Maximum length of containers before abbreviating, or None for no abbreviation.
            Defaults to 10.
        locals_max_string (int, optional): Maximum length of string before truncating, or None to disable. Defaults to 80.
        locals_hide_dunder (bool, optional): Hide locals prefixed with double underscore. Defaults to True.
        locals_hide_sunder (bool, optional): Hide locals prefixed with single underscore. Defaults to False.
        indent_guides (bool, optional): Enable indent guides in code and locals. Defaults to True.
        suppress (Sequence[Union[str, ModuleType]]): Optional sequence of modules or paths to exclude from traceback.

    Returns:
        Callable: The previous exception handler that was replaced.

    """
    traceback_console = Console(stderr=True) if console is None else console

    locals_hide_sunder = True if (traceback_console.is_jupyter and locals_hide_sunder is None) else locals_hide_sunder

    def excepthook(
        type_: Type[BaseException],
        value: BaseException,
        traceback: Optional[TracebackType],
    ) -> None:

        traceback_console.print(
            Traceback.from_exception(
                type_,
                value,
                traceback,
                width=width,
                code_width=code_width,
                extra_lines=extra_lines,
                theme=theme,
                word_wrap=word_wrap,
                show_locals=show_locals,
                locals_max_length=locals_max_length,
                locals_max_string=locals_max_string,
                locals_hide_dunder=locals_hide_dunder,
                locals_hide_sunder=bool(locals_hide_sunder),
                indent_guides=indent_guides,
                suppress=suppress,
                max_frames=max_frames,
            )
        )

    def ipy_excepthook_closure(ip: Any) -> None:  # pragma: no cover
        tb_data = {}  # store information about showtraceback call
        default_showtraceback = ip.showtraceback  # keep reference of default traceback

        def ipy_show_traceback(*args: Any, **kwargs: Any) -> None:
            """wrap the default ip.showtraceback to store info for ip._showtraceback"""
            nonlocal tb_data
            tb_data = kwargs
            default_showtraceback(*args, **kwargs)

        def ipy_display_traceback(*args: Any, is_syntax: bool = False, **kwargs: Any) -> None:
            """Internally called traceback from ip._showtraceback"""
            nonlocal tb_data
            exc_tuple = ip._get_exc_info()

            # do not display trace on syntax error
            tb: Optional[TracebackType] = None if is_syntax else exc_tuple[2]

            # determine correct tb_offset
            compiled = tb_data.get("running_compiled_code", False)
            tb_offset = tb_data.get("tb_offset", 1 if compiled else 0)
            # remove ipython internal frames from trace with tb_offset
            for _ in range(tb_offset):
                if tb is None:
                    break
                tb = tb.tb_next

            excepthook(exc_tuple[0], exc_tuple[1], tb)
            tb_data = {}  # clear data upon usage

        # replace _showtraceback instead of showtraceback to allow ipython features such as debugging to work
        # this is also what the ipython docs recommends to modify when subclassing InteractiveShell
        ip._showtraceback = ipy_display_traceback
        # add wrapper to capture tb_data
        ip.showtraceback = ipy_show_traceback
        ip.showsyntaxerror = lambda *args, **kwargs: ipy_display_traceback(*args, is_syntax=True, **kwargs)

    try:  # pragma: no cover
        # if within ipython, use customized traceback
        from IPython import get_ipython

        ip = get_ipython()  # type: ignore[name-defined]
        ipy_excepthook_closure(ip)
        return sys.excepthook
    except Exception:
        # otherwise use default system hook
        old_excepthook = sys.excepthook
        sys.excepthook = excepthook
        return old_excepthook


@dataclass
class Frame:
    filename: str
    lineno: int
    name: str
    line: str = ""
    locals: Optional[Dict[str, pretty.Node]] = None
    last_instruction: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None


@dataclass
class _SyntaxError:
    offset: int
    filename: str
    line: str
    lineno: int
    msg: str


@dataclass
class Stack:
    exc_type: str
    exc_value: str
    syntax_error: Optional[_SyntaxError] = None
    is_cause: bool = False
    frames: List[Frame] = field(default_factory=list)


@dataclass
class Trace:
    stacks: List[Stack]



class PathHighlighter(RegexHighlighter):
    highlights = [r"(?P<dim>.*/)(?P<bold>.+)"]

_ALWAYS_SAFE = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZ" b"abcdefghijklmnopqrstuvwxyz" b"0123456789" b"_.-~")
_ALWAYS_SAFE_BYTES = bytes(_ALWAYS_SAFE)
class _Quoter(dict):
    """A mapping from bytes numbers (in range(0,256)) to strings.

    String values are percent-encoded byte values, unless the key < 128, and
    in either of the specified safe set, or the always safe set.
    """

    # Keeps a cache internally, via __missing__, for efficiency (lookups
    # of cached keys don't call Python code at all).
    def __init__(self, safe):
        """safe: bytes object."""
        self.safe = _ALWAYS_SAFE.union(safe)

    def __repr__(self):
        return f"<Quoter {dict(self)!r}>"

    def __missing__(self, b):
        # Handle a cache miss. Store quoted string in cache and return.
        res = chr(b) if b in self.safe else "%{:02X}".format(b)
        self[b] = res
        return res
    
@functools.lru_cache
def _byte_quoter_factory(safe):
    return _Quoter(safe).__getitem__


def quote_from_bytes(bs, safe="/"):
    r"""Like quote(), but accepts a bytes object rather than a str, and does
    not perform string-to-bytes encoding.  It always returns an ASCII string.
    quote_from_bytes(b'abc def\x3f') -> 'abc%20def%3f'.
    """  # noqa: D205
    if not isinstance(bs, (bytes, bytearray)):
        raise TypeError("quote_from_bytes() expected bytes")
    if not bs:
        return ""
    if isinstance(safe, str):  # noqa: SIM108
        # Normalize 'safe' by converting to bytes and removing non-ASCII chars
        safe = safe.encode("ascii", "ignore")
    else:
        # List comprehensions are faster than generator expressions.
        safe = bytes([c for c in safe if c < 128])
    if not bs.rstrip(_ALWAYS_SAFE_BYTES + safe):
        return bs.decode()
    quoter = _byte_quoter_factory(safe)
    return "".join([quoter(char) for char in bs])

def quote(string, safe="/", encoding=None, errors=None):
    """quote('abc def') -> 'abc%20def'.

    Each part of a URL, e.g. the path info, the query, etc., has a
    different set of reserved characters that must be quoted. The
    quote function offers a cautious (not minimal) way to quote a
    string for most of these parts.

    RFC 3986 Uniform Resource Identifier (URI): Generic Syntax lists
    the following (un)reserved characters.

    unreserved    = ALPHA / DIGIT / "-" / "." / "_" / "~"
    reserved      = gen-delims / sub-delims
    gen-delims    = ":" / "/" / "?" / "#" / "[" / "]" / "@"
    sub-delims    = "!" / "$" / "&" / "'" / "(" / ")"
                  / "*" / "+" / "," / ";" / "="

    Each of the reserved characters is reserved in some component of a URL,
    but not necessarily in all of them.

    The quote function %-escapes all characters that are neither in the
    unreserved chars ("always safe") nor the additional chars set via the
    safe arg.

    The default for the safe arg is '/'. The character is reserved, but in
    typical usage the quote function is being called on a path where the
    existing slash characters are to be preserved.

    Python 3.7 updates from using RFC 2396 to RFC 3986 to quote URL strings.
    Now, "~" is included in the set of unreserved characters.

    string and safe may be either str or bytes objects. encoding and errors
    must not be specified if string is a bytes object.

    The optional encoding and errors parameters specify how to deal with
    non-ASCII characters, as accepted by the str.encode method.
    By default, encoding='utf-8' (characters are encoded with UTF-8), and
    errors='strict' (unsupported characters raise a UnicodeEncodeError).
    """  # noqa: D402
    if isinstance(string, str):
        if not string:
            return string
        if encoding is None:
            encoding = "utf-8"
        if errors is None:
            errors = "strict"
        string = string.encode(encoding, errors)
    else:
        if encoding is not None:
            raise TypeError("quote() doesn't support 'encoding' for bytes")
        if errors is not None:
            raise TypeError("quote() doesn't support 'errors' for bytes")
    return quote_from_bytes(string, safe)


def link_fp(line: str | Any, fn: str | Path, lineno: int | str,render=True) -> Text | str:
    """Create a clickable file link with line number."""
    stem = Path(fn).name  # Gets the filename with extension
    resolved_path = Path(fn).resolve()

    # URL-encode the file path to handle spaces and special characters
    line = str(line) if not isinstance(line, str) else line
    fn = str(fn) if not isinstance(fn, str) else fn
    lineno = int(lineno) if not isinstance(lineno, int) else lineno
    encoded_path = quote(str(resolved_path))
    uri = "vscode://file//" if any("VSCODE" in name for name in os.environ) else "file://"

    if lineno:
        # Ensure three slashes after file:// for absolute paths
        file_url = f"{uri}{encoded_path}:{lineno}"
        display_text = f"{stem}:{lineno}"
    else:
        file_url = f"{uri}{encoded_path}"
        display_text = stem
    

    markup = f"{line}[bold blue underline] [link={file_url}]{display_text}[/link][/bold blue underline] "
    return markup 
    if not render:
        return markup
    # Assemble the line with the clickable link
    return Text.from_markup(markup)


def link_fp(line, fn, lineno) -> str | Text:
    stem = Path(fn).stem
    stem = stem + Path(fn).suffix
    from urllib.parse import quote

    # URL-encode the file path to handle spaces and special characters
    encoded_path = quote(str(Path(fn).absolute()))
    uri = "vscode://file//" if any("VSCODE" in name for name in os.environ) else "file://"

    if lineno:
        # Ensure three slashes after file:// for absolute paths
        file_url = f"{uri}{encoded_path}:{lineno}"
        display_text = f"{stem}:{lineno}"
    else:
        file_url = f"{uri}{encoded_path}"
        display_text = stem


    return  f"{line}\n[link={file_url}][bold dim]{display_text}[/bold dim][/link]"
    # return f"[link=file://{str(fn) + ':' + str(lineno)}]" + str(line) + "[/link]" + "\n" + f"{fn}:{lineno}"


def safe_text(*strs: str | Text) -> Text:
        """Handle ANSI and markup in text by combining them into a Text object.
        
        Args:
            *strs: Variable number of strings or Text objects to combine
            
        Returns:
            Text: A combined Text object with preserved styling
        """
        out = []
        for s in strs:
            if isinstance(s, Text):
                out.append(s)
            elif "\x1b[" in s:  # ANSI escape sequence
                out.append(Text.from_ansi(s))
            elif "[" in s and "]" in s:  # Rich markup
                out.append(Text.from_markup(s)) 
            else:
                out.append(Text(s))
        
        return Text.assemble(*out)
class Traceback:
    """A Console renderable that renders a traceback.

    Args:
        trace (Trace, optional): A `Trace` object produced from `extract`. Defaults to None, which uses
            the last exception.
        width (Optional[int], optional): Number of characters used to traceback. Defaults to 100.
        code_width (Optional[int], optional): Number of code characters used to traceback. Defaults to 88.
        extra_lines (int, optional): Additional lines of code to render. Defaults to 3.
        theme (str, optional): Override pygments theme used in traceback.
        word_wrap (bool, optional): Enable word wrapping of long lines. Defaults to False.
        show_locals (bool, optional): Enable display of local variables. Defaults to False.
        indent_guides (bool, optional): Enable indent guides in code and locals. Defaults to True.
        locals_max_length (int, optional): Maximum length of containers before abbreviating, or None for no abbreviation.
            Defaults to 10.
        locals_max_string (int, optional): Maximum length of string before truncating, or None to disable. Defaults to 80.
        locals_hide_dunder (bool, optional): Hide locals prefixed with double underscore. Defaults to True.
        locals_hide_sunder (bool, optional): Hide locals prefixed with single underscore. Defaults to False.
        suppress (Sequence[Union[str, ModuleType]]): Optional sequence of modules or paths to exclude from traceback.
        max_frames (int): Maximum number of frames to show in a traceback, 0 for no maximum. Defaults to 100.

    """

    LEXERS = {
        "": "text",
        ".py": "python",
        ".pxd": "cython",
        ".pyx": "cython",
        ".pxi": "pyrex",
    }

    def __init__(
        self,
        trace: Optional[Trace] = None,
        *,
        width: Optional[int] = 120,
        code_width: Optional[int] = 120,
        extra_lines: int = 3,
        theme: Optional[str] = None,
        word_wrap: bool = False,
        show_locals: bool = False,
        locals_max_length: int = LOCALS_MAX_LENGTH,
        locals_max_string: int = LOCALS_MAX_STRING,
        locals_hide_dunder: bool = True,
        locals_hide_sunder: bool = False,
        indent_guides: bool = True,
        suppress: Iterable[Union[str, ModuleType]] = (),
        max_frames: int = 100,
    ):
        if trace is None:
            exc_type, exc_value, traceback = sys.exc_info()
            if exc_type is None or exc_value is None or traceback is None:
                raise ValueError("Value for 'trace' required if not called in except: block")
            trace = self.extract(exc_type, exc_value, traceback, show_locals=show_locals)
        self.trace = trace
        self.width = width
        self.code_width = code_width
        self.extra_lines = extra_lines
        self.theme = Syntax.get_theme(theme or "ansi_dark")
        self.word_wrap = word_wrap
        self.show_locals = show_locals
        self.indent_guides = indent_guides
        self.locals_max_length = locals_max_length
        self.locals_max_string = locals_max_string
        self.locals_hide_dunder = locals_hide_dunder
        self.locals_hide_sunder = locals_hide_sunder

        self.suppress: Sequence[str] = []
        for suppress_entity in suppress:
            if not isinstance(suppress_entity, str):
                assert (
                    suppress_entity.__file__ is not None
                ), f"{suppress_entity!r} must be a module with '__file__' attribute"
                path = os.path.dirname(suppress_entity.__file__)
            else:
                path = suppress_entity
            path = os.path.normpath(os.path.abspath(path))
            self.suppress.append(path)
        self.max_frames = max(4, max_frames) if max_frames > 0 else 0

    @classmethod
    def from_exception(
        cls,
        exc_type: Type[Any],
        exc_value: BaseException,
        traceback: TracebackType | None,
        *,
        width: int | None = 120,
        code_width: int | None = 120,
        extra_lines: int = 3,
        theme: str | None = None,
        word_wrap: bool = False,
        show_locals: bool = False,
        locals_max_length: int = LOCALS_MAX_LENGTH,
        locals_max_string: int = LOCALS_MAX_STRING,
        locals_hide_dunder: bool = True,
        locals_hide_sunder: bool = False,
        indent_guides: bool = True,
        suppress: Iterable[str | ModuleType] = (),
        max_frames: int = 100,
    ) -> "Traceback":
        """Create a traceback from exception info.

        Args:
            exc_type (Type[BaseException]): Exception type.
            exc_value (BaseException): Exception value.
            traceback (TracebackType): Python Traceback object.
            width (Optional[int], optional): Number of characters used to traceback. Defaults to 100.
            code_width (Optional[int], optional): Number of code characters used to traceback. Defaults to 88.
            extra_lines (int, optional): Additional lines of code to render. Defaults to 3.
            theme (str, optional): Override pygments theme used in traceback.
            word_wrap (bool, optional): Enable word wrapping of long lines. Defaults to False.
            show_locals (bool, optional): Enable display of local variables. Defaults to False.
            indent_guides (bool, optional): Enable indent guides in code and locals. Defaults to True.
            locals_max_length (int, optional): Maximum length of containers before abbreviating, or None for no abbreviation.
                Defaults to 10.
            locals_max_string (int, optional): Maximum length of string before truncating, or None to disable. Defaults to 80.
            locals_hide_dunder (bool, optional): Hide locals prefixed with double underscore. Defaults to True.
            locals_hide_sunder (bool, optional): Hide locals prefixed with single underscore. Defaults to False.
            suppress (Iterable[Union[str, ModuleType]]): Optional sequence of modules or paths to exclude from traceback.
            max_frames (int): Maximum number of frames to show in a traceback, 0 for no maximum. Defaults to 100.

        Returns:
            Traceback: A Traceback instance that may be printed.
        """
        rich_traceback = cls.extract(
            exc_type,
            exc_value,
            traceback,
            show_locals=show_locals,
            locals_max_length=locals_max_length,
            locals_max_string=locals_max_string,
            locals_hide_dunder=locals_hide_dunder,
            locals_hide_sunder=locals_hide_sunder,
        )

        return cls(
            rich_traceback,
            width=width,
            code_width=code_width,
            extra_lines=extra_lines,
            theme=theme,
            word_wrap=word_wrap,
            show_locals=show_locals,
            indent_guides=indent_guides,
            locals_max_length=locals_max_length,
            locals_max_string=locals_max_string,
            locals_hide_dunder=locals_hide_dunder,
            locals_hide_sunder=locals_hide_sunder,
            suppress=suppress,
            max_frames=max_frames,
        )

    @classmethod
    def extract(
        cls,
        exc_type: Type[BaseException],
        exc_value: BaseException,
        traceback: TracebackType | None,
        *,
        show_locals: bool = False,
        locals_max_length: int = LOCALS_MAX_LENGTH,
        locals_max_string: int = LOCALS_MAX_STRING,
        locals_hide_dunder: bool = True,
        locals_hide_sunder: bool = False,
    ) -> Trace:
        """Extract traceback information.

        Args:
            exc_type (Type[BaseException]): Exception type.
            exc_value (BaseException): Exception value.
            traceback (TracebackType): Python Traceback object.
            show_locals (bool, optional): Enable display of local variables. Defaults to False.
            locals_max_length (int, optional): Maximum length of containers before abbreviating, or None for no abbreviation.
                Defaults to 10.
            locals_max_string (int, optional): Maximum length of string before truncating, or None to disable. Defaults to 80.
            locals_hide_dunder (bool, optional): Hide locals prefixed with double underscore. Defaults to True.
            locals_hide_sunder (bool, optional): Hide locals prefixed with single underscore. Defaults to False.

        Returns:
            Trace: A Trace instance which you can use to construct a `Traceback`.
        """
        stacks: List[Stack] = []
        is_cause = False

        from rich import _IMPORT_CWD

        def safe_str(_object: Any) -> str:
            """Don't allow exceptions from __str__ to propagate."""
            try:
                return str(_object)
            except Exception:
                return "<exception str() failed>"


        
        # Try to handle custom frame first
        if hasattr(exc_value, 'caller_frame'):
            stack = Stack(
                exc_type=safe_str(exc_type.__name__),
                exc_value=safe_str(exc_value.message),
                is_cause=is_cause,
            )
            
            caller_frame = exc_value.caller_frame
            lines = linecache.getlines(caller_frame.f_code.co_filename)
            line = lines[caller_frame.f_lineno - 1].rstrip() if 0 <= caller_frame.f_lineno - 1 < len(lines) else ""
            
            frame = Frame(
                filename=caller_frame.f_code.co_filename,
                lineno=caller_frame.f_lineno,
                name=caller_frame.f_code.co_name,
                line=line,
                locals=None,  # We don't need locals for this case
            )
            
            stack.frames.append(frame)
            stacks.append(stack)
            if frame.filename and frame.lineno:  # Only return if we have valid frame info
                return Trace(stacks=stacks)
    
        while True:
            stack = Stack(
                exc_type=safe_str(exc_type.__name__),
                exc_value=safe_str(exc_value),
                is_cause=is_cause,
            )

            if isinstance(exc_value, SyntaxError):
                stack.syntax_error = _SyntaxError(
                    offset=exc_value.offset or 0,
                    filename=exc_value.filename or "?",
                    lineno=exc_value.lineno or 0,
                    line=exc_value.text or "",
                    msg=exc_value.msg,
                )

            stacks.append(stack)
            append = stack.frames.append

            def get_locals(iter_locals: Iterable[Tuple[str, object]]) -> Iterable[Tuple[str, object]]:
                """Extract locals from an iterator of key pairs."""
                if not (locals_hide_dunder or locals_hide_sunder):
                    yield from iter_locals
                    return
                for key, value in iter_locals:
                    if locals_hide_dunder and key.startswith("__"):
                        continue
                    if locals_hide_sunder and key.startswith("_"):
                        continue
                    yield key, value

            for frame_summary, line_no in walk_tb(traceback):
                filename = frame_summary.f_code.co_filename

                last_instruction: Tuple[Tuple[int, int], Tuple[int, int]] | None
                last_instruction = None
                if sys.version_info >= (3, 11):
                    instruction_index = frame_summary.f_lasti // 2
                    instruction_position = next(
                        islice(
                            frame_summary.f_code.co_positions(),
                            instruction_index,
                            instruction_index + 1,
                        )
                    )
                    (
                        start_line,
                        end_line,
                        start_column,
                        end_column,
                    ) = instruction_position
                    if (
                        start_line is not None
                        and end_line is not None
                        and start_column is not None
                        and end_column is not None
                    ):
                        last_instruction = (
                            (start_line, start_column),
                            (end_line, end_column),
                        )

                if filename and not filename.startswith("<") and not os.path.isabs(filename):
                    filename = os.path.join(_IMPORT_CWD, filename)
                if frame_summary.f_locals.get("_rich_traceback_omit", False):
                    continue

                frame = Frame(
                    filename=filename or "?",
                    lineno=line_no,
                    name=frame_summary.f_code.co_name,
                    locals=(
                        {
                            key: pretty.traverse(
                                value,
                                max_length=locals_max_length,
                                max_string=locals_max_string,
                            )
                            for key, value in get_locals(frame_summary.f_locals.items())
                            if not (inspect.isfunction(value) or inspect.isclass(value))
                        }
                        if show_locals
                        else None
                    ),
                    last_instruction=last_instruction,
                )
                append(frame)
                if frame_summary.f_locals.get("_rich_traceback_guard", False):
                    del stack.frames[:]

            cause = getattr(exc_value, "__cause__", None)
            if cause:
                exc_type = cause.__class__
                exc_value = cause
                # __traceback__ can be None, e.g. for exceptions raised by the
                # 'multiprocessing' module
                traceback = cause.__traceback__
                is_cause = True
                continue

            cause = exc_value.__context__
            if cause and not getattr(exc_value, "__suppress_context__", False):
                exc_type = cause.__class__
                exc_value = cause
                traceback = cause.__traceback__
                is_cause = False
                continue
            # No cover, code is reached but coverage doesn't recognize it.
            break  # pragma: no cover

        trace = Trace(stacks=stacks)
        return trace

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        theme = self.theme
        background_style = theme.get_background_style()
        token_style = theme.get_style_for_token

        traceback_theme = Theme(
            {
                "pretty": token_style(TextToken),
                "pygments.text": token_style(Token),
                "pygments.string": token_style(String),
                "pygments.function": token_style(Name.Function),
                "pygments.number": token_style(Number),
                "repr.indent": token_style(Comment) + Style(dim=True),
                "repr.str": token_style(String),
                "repr.brace": token_style(TextToken) + Style(bold=True),
                "repr.number": token_style(Number),
                "repr.bool_true": token_style(Keyword.Constant),
                "repr.bool_false": token_style(Keyword.Constant),
                "repr.none": token_style(Keyword.Constant),
                "scope.border": token_style(String.Delimiter),
                "scope.equals": token_style(Operator),
                "scope.key": token_style(Name),
                "scope.key.special": token_style(Name.Constant) + Style(dim=True),
            },
            inherit=False,
        )

        highlighter = ReprHighlighter()

        for last, stack in loop_last(reversed(self.trace.stacks)):
            if stack.frames:
                stack_renderable: ConsoleRenderable = Panel(
                    self._render_stack(stack),
                    title=link_fp(
                        "Traceback (most recent call last):",
                        stack.frames[-1].filename,
                        stack.frames[-1].lineno,
                    ),
                    style=background_style,
                    border_style="none",
                    expand=True,
                    box=BOX_TYPE,  # Add this line to remove the borders
                )
                stack_renderable = Constrain(stack_renderable, self.width)
                with console.use_theme(traceback_theme):
                    yield stack_renderable
            if stack.syntax_error is not None:
                with console.use_theme(traceback_theme):
                    yield Constrain(
                        Panel(
                            self._render_syntax_error(stack.syntax_error),
                            style=background_style,
                            expand=True,
                            padding=(0, 1),
                            width=self.width,
                            box=BOX_TYPE,  # Add this line to remove the borders
                        ),
                        self.width,
                    )
                yield Text.assemble(
                    (f"{stack.exc_type}: ", "traceback.exc_type"),
                    highlighter(stack.syntax_error.msg),
                    link_fp(stack.syntax_error.line, stack.syntax_error.filename, stack.syntax_error.lineno),
                )
            elif stack.exc_value:
                yield Text.assemble(
                    (f"{stack.exc_type}: ", "traceback.exc_type"),
                    highlighter(safe_text(stack.exc_value)),
                )
            else:
                yield Text.assemble((f"{stack.exc_type}", "traceback.exc_type"))

            if not last:
                if stack.is_cause:
                    yield Text.from_markup(
                        "\n[i]The above exception was the direct cause of the following exception:\n",
                    )
                else:
                    yield Text.from_markup(
                        "\n[i]During handling of the above exception, another exception occurred:\n",
                    )

    @group()
    def _render_syntax_error(self, syntax_error: _SyntaxError) -> RenderResult:
        highlighter = ReprHighlighter()
        path_highlighter = PathHighlighter()
        if syntax_error.filename != "<stdin>" and Path(syntax_error.filename).exists():
            text = Text.assemble(
                (f" {syntax_error.filename}", "pygments.string"),
                (":", "pygments.text"),
                (str(syntax_error.lineno), "pygments.number"),
                style="pygments.text",
            )
            yield link_fp(path_highlighter(text), fn=syntax_error.filename, lineno=syntax_error.lineno)
        syntax_error_text = highlighter(syntax_error.line.rstrip())
        syntax_error_text.no_wrap = True
        offset = min(syntax_error.offset - 1, len(syntax_error_text))
        syntax_error_text.stylize("bold underline", offset, offset)
        syntax_error_text += Text.from_markup(
            "\n" + " " * offset + "[traceback.offset]▲[/]",
            style="pygments.text",
        )
        yield link_fp(syntax_error_text, syntax_error.filename, syntax_error.lineno)

    @classmethod
    def _guess_lexer(cls, filename: str, code: str) -> str:
        ext = os.path.splitext(filename)[-1]
        if not ext:
            # No extension, look at first line to see if it is a hashbang
            # Note, this is an educated guess and not a guarantee
            # If it fails, the only downside is that the code is highlighted strangely
            new_line_index = code.index("\n")
            first_line = code[:new_line_index] if new_line_index != -1 else code
            if first_line.startswith("#!") and "python" in first_line.lower():
                return "python"
        try:
            return cls.LEXERS.get(ext) or guess_lexer_for_filename(filename, code).name
        except ClassNotFound:
            return "text"

    @group()
    def _render_stack(self, stack: Stack) -> RenderResult:
        path_highlighter = PathHighlighter()
        theme = self.theme

        def read_code(filename: str) -> str:
            """Read files, and cache results on filename.

            Args:
                filename (str): Filename to read

            Returns:
                str: Contents of file
            """
            return "".join(linecache.getlines(filename))

        def render_locals(frame: Frame) -> Iterable[ConsoleRenderable]:
            if frame.locals:
                yield render_scope(
                    frame.locals,
                    title="locals",
                    indent_guides=self.indent_guides,
                    max_length=self.locals_max_length,
                    max_string=self.locals_max_string,
                )

        exclude_frames: Optional[range] = None
        if self.max_frames != 0:
            exclude_frames = range(
                self.max_frames // 2,
                len(stack.frames) - self.max_frames // 2,
            )

        excluded = False
        for frame_index, frame in enumerate(stack.frames):
            if exclude_frames and frame_index in exclude_frames:
                excluded = True
                continue

            if excluded:
                assert exclude_frames is not None
                yield Text(
                    f"\n... {len(exclude_frames)} frames hidden ...",
                    justify="center",
                    style="traceback.error",
                )
                excluded = False

            first = frame_index == 0
            frame_filename = frame.filename
            suppressed = any(frame_filename.startswith(path) for path in self.suppress)

            if os.path.exists(frame.filename):
                text = Text.assemble(
                    path_highlighter(Text(frame.filename, style="pygments.string")),
                    (":", "pygments.text"),
                    (str(frame.lineno), "pygments.number"),
                    " in ",
                    (frame.name, "pygments.function"),
                    style="pygments.text",
                )
            else:
                text = Text.assemble(
                    "in ",
                    (frame.name, "pygments.function"),
                    (":", "pygments.text"),
                    (str(frame.lineno), "pygments.number"),
                    style="pygments.text",
                )
            if not frame.filename.startswith("<") and not first:
                yield ""
            yield link_fp(text, frame_filename, frame.lineno)
            if frame.filename.startswith("<"):
                yield from render_locals(frame)
                continue
            if not suppressed:
                try:
                    code = read_code(frame.filename)
                    if not code:
                        # code may be an empty string if the file doesn't exist, OR
                        # if the traceback filename is generated dynamically
                        continue
                    lexer_name = self._guess_lexer(frame.filename, code)
                    syntax = Syntax(
                        code,
                        lexer_name,
                        theme=theme,
                        line_numbers=True,
                        line_range=(
                            frame.lineno - self.extra_lines,
                            frame.lineno + self.extra_lines,
                        ),
                        highlight_lines={frame.lineno},
                        word_wrap=self.word_wrap,
                        code_width=self.code_width,
                        indent_guides=self.indent_guides,
                        dedent=False,
                    )
                    yield ""
                except Exception as error:
                    yield Text.assemble(
                        (f"\n{error}", "traceback.error"),
                    )
                else:
                    if frame.last_instruction is not None:
                        start, end = frame.last_instruction
                        syntax.stylize_range(
                            style="traceback.error_range",
                            start=start,
                            end=end,
                        )
                    yield (
                        Columns(
                            [
                                syntax,
                                *render_locals(frame),
                                link_fp(frame.line, frame.filename, frame.lineno),
                            ],
                            padding=0,
                        )
                        if frame.locals
                        else syntax
                    )


if __name__ == "__main__":  # pragma: no cover
    install(show_locals=True)
    import sys

    def bar(
        a: Any,
    ) -> None:  # 这是对亚洲语言支持的测试。面对模棱两可的想法，拒绝猜测的诱惑
        one = 1
        print(one / a)

    def foo(a: Any) -> None:
        _rich_traceback_guard = True
        zed = {
            "characters": {
                "Paul Atreides",
                "Vladimir Harkonnen",
                "Thufir Hawat",
                "Duncan Idaho",
            },
            "atomic_types": (None, False, True),
        }
        bar(a)

    def error() -> None:
        foo(0)

    error()
