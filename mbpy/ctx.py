import _imp
import builtins
import inspect
import io
import logging
import os
import sys
import traceback
import typing
from contextlib import AbstractContextManager
from inspect import currentframe, getmodule
from pathlib import Path
from pydoc import (
    HTMLDoc,
    allmethods,
    describe,
    locate,
    safeimport,
    source_synopsis,
    splitdoc,
    synopsis,
)
from types import FrameType, ModuleType, SimpleNamespace, TracebackType
from typing import Any, Callable, Generator, Generic, Iterable, Literal, NewType, Protocol, Tuple, Type, TypeAlias, TypeVar, TypeVarTuple, Union, Unpack, cast

from mrender import Markdown
from rich.console import Console
from rich.traceback import Traceback
from typing_extensions import Final

from mbpy import import_utils
from mbpy.collect import reduce
from mbpy.helpers._typing import caller

T = TypeVar("T")


def onlyone(iterable: Iterable[T] | T) -> T:
    if not isinstance(iterable, Iterable):
        return iterable
    return next(iter(iterable))

def walk_parents(traceback: TracebackType) -> Generator[tuple[FrameType ,str ,int], None, None]:
    """Walk the parent frames of a traceback."""
    frames = inspect.getinnerframes(traceback)
    for frame, filename, lineno, _, _, _ in frames:
        yield frame, filename, lineno


def surrounding_ctx(frame, filename, lineno, num_lines=5) -> list[str]:
    """Grab the context of a frame."""
    lines = [""] + Path(filename).read_text().splitlines()

    return lines[max(0, lineno - num_lines) : lineno + num_lines]


def get_window(frames: Iterable[Tuple[FrameType, str, int]], num_lines=5):
    for frame, filename, lineno in frames:
        yield from surrounding_ctx(frame, filename, lineno, num_lines=num_lines)
        yield f"at {filename}:{lineno}"


class ExceptionHolder(Exception):
    def __init__(self, step: int = 0):
        self.exc: BaseException | None = None
        self.tb: TracebackType | None = None  # Store traceback
    def set_exception(self, exc: BaseException | None, tb: TracebackType | None = None) -> None:
        self.exc = exc
        self.tb = tb
        object.__setattr__(self, "__traceback__", tb)
        object.__setattr__(self,"__name__",getattr(exc.__class__,"__name__",None))
        object.__setattr__(self,"__module__",getattr(exc.__class__,"__module__",None))
        object.__setattr__(self,"__qualname__", getattr(exc.__class__,"__qualname__",None))
        object.__setattr__(self,"__package__",getattr(exc.__class__,"__package__",None))
        self.__dict__.update(exc.__dict__)
        self.__class__.__name__ = exc.__class__.__name__

    def __getattr__(self, attr):
        if self.exc and attr not in ("__dict__", "__class__"):
            return getattr(self.exc, attr)
        raise AttributeError(f"'ExceptionHolder' object has no attribute '{attr}'")

    def __bool__(self):
        return self.exc is not None
    
    def windowed(self, windowsize: int = 5, step=-1):
        """Print a window of code around each parent frame in the traceback."""
        if self.tb:
            yield from  list(get_window(reversed(list(walk_parents(self.tb))), num_lines=windowsize))[:step]
        return "None"
    def __str__(self):
        if self.exc and self.tb:
   
            return str(str(self.exc))
        return "None"

    def __repr__(self):
        if self.exc:
            return repr(self.exc)
        return "None"

    def windowed_repr(self, windowsize: int = 5):
        """Print a window of code around each parent frame in the traceback."""
        if self.tb:
            return "\n".join(list(self.windowed(windowsize)))
        return "None"
    def __await__(self):
        return self
class FakeException(BaseException):
    pass
Ts = TypeVarTuple("Ts")



Shape = tuple
CRITICAL = 50
FATAL = CRITICAL
ERROR = 40
WARNING = 30
WARN = WARNING
INFO = 20
DEBUG = 10
NOTSET = 0
LOGLEVEL = Literal["CRITICAL", "FATAL", "ERROR", "WARNING", "WARN", "INFO", "DEBUG", "NOTSET"]

class suppress(AbstractContextManager):
    """Context manager to suppress specified exceptions and capture them.
    
    ```
    Usage:
        with suppress(Exception) as ex:
            some_problematic_code()
        if ex:
           handle_problematic_code(ex).
    
        with supress.logignore(Exception) as ex:
            some_problematic_code()
    ```
    Args:
        exceptions: Exception types to suppress. Defaults to all exceptions.
        dontignore: Exception types not to suppress.
        log: Log the suppressed exception.
        windowsize: Number of lines of code to display around the exception.
        step: Number of lines to step through the traceback.

    Class Initializers:
        logignore: Suppress exceptions and log them.
        noncritical: Suppress all exceptions except KeyboardInterrupt.
        windowed: Suppress exceptions with a limited traceback window size.
        step: Suppress exceptions and return a generator to step through the traceback.
        then: Suppress exceptions then run a function that accepts the exception.

    """
    callbacks: list[Callable | Callable[[Exception],Any]] = []
    def __init__(
        self,
        *exceptions: Type[BaseException],
        dontignore: Type[BaseException] | None = None,
        log: bool | LOGLEVEL = False,
        windowsize: int = 0,
        step: int = 0,
    ) -> None:
        """Suppress exceptions and capture them.
        
        Args:
            exceptions: Exception types to suppress. Defaults to all exceptions.
            dontignore: Exception types not to suppress.
            log: Log the suppressed exception.
            windowsize: Number of lines of code to display around the exception.
            step: Number of lines to step through the traceback.
        """
        self._exceptions = exceptions or (Exception,)
        self.log = log
        self.holder = ExceptionHolder(step=step)
        self.dontignore = dontignore or FakeException
        self.windowsize = windowsize
        self._step = step
        self.callbacks: list[Callable | Callable[[Exception],Any]]
        self.filters = []
        self.result = None
    def __enter__(self) -> ExceptionHolder | Iterable[str]:
        if self._step:
            return self.holder.windowed(self._step)
        return self.holder
    def __aenter__(self) -> ExceptionHolder | Iterable[str]:
        return self.__enter__()
    def __aexit__(self, exc_type, exc_value, tb) -> bool:
        return self.__exit__(exc_type, exc_value, tb)
    def __await__(self):
        return self
    def __exit__(
        self, exc_type: Type[BaseException] | None, exc_value: BaseException | None, tb: TracebackType | None,
    ) -> bool:
        if exc_type and issubclass(exc_type, self._exceptions) and not issubclass(exc_type, self.dontignore):
            self.holder.set_exception(exc_value, tb)  # Store both exception and traceback
            if self.log is True  and (not self.log is False or not any(f(exc_value) for f in self.filters) and logging.getLogger().isEnabledFor(self.log)):
                logging.error(f"{exc_type.__name__}: {exc_value}") 
                if self.windowsize:
                    logging.error("".join(traceback.format_exception(exc_type, exc_value, tb, limit=self.windowsize)))
                else:
                    logging.exception(exc_value)
                
                logging.warning("The above exception was suppressed.")
            if getattr(self,"callbacks",None):
                self.result = reduce(lambda acc, fn: fn(acc), self.callbacks, exc_value)
            return True  # Suppress the exception
        return False  # Do not suppress other exceptions

    def add_filter(self, filter: Callable[...,bool]) -> None:
        self.filters.append(filter)
    @classmethod
    def logignore(cls, *exceptions: Type[BaseException], when: bool | LOGLEVEL = False):
        """Convenience method to create a suppress context manager with logging enabled."""
        return cls(*exceptions, log=when)

    
    @classmethod
    def noncritical(cls):
        """Suppress all exceptions except KeyboardInterrupt."""
        return cls(Exception, dontignore=KeyboardInterrupt)

    @classmethod
    def windowed(cls, windowsize: int = 5):
        """Suppress exceptions with a limited traceback window size."""
        return cls(Exception, dontignore=KeyboardInterrupt, windowsize=windowsize)

    @classmethod
    def step(cls, step: int = 5):
        """Returns a suppress context manager that returns a generator to step through the traceback."""
        return cls(Exception, dontignore=KeyboardInterrupt, step=step).step()

    @classmethod
    def no_third_party(cls, *exceptions:Type[BaseException]):
        cls = cls(*exceptions)
        cls.add_filter(is_third_party)
        return cls
    
    @classmethod
    def then(cls, func):
        """Suppress exceptions then run a function that accepts the exception. Can be chained."""
        ctx = cls(Exception)
        ctx.callbacks.append(func)
        class ContextWrapper:
            def __init__(self, ctx: suppress):
                self.ctx = ctx
            def __enter__(self):
                if self.ctx.__enter__() is not None:
                    return self.ctx
                return self.ctx.result
            def __exit__(self, exc_type, exc_value, tb):
                self.ctx.__exit__(exc_type, exc_value, tb)
        
            def then(self, func):
                self.ctx.callbacks.append(func)
                return self
        return ContextWrapper(ctx)

console = Console()


def test_pydoc_methods() -> None:
    import mrender

    import mbpy

    console.print(
        f"allmethods: {allmethods(Markdown)}\n",
    )
    # YES BELOW GOOD!
    # console.print(
    #     f"apropos: {apropos('Markdown')}\n"
    # )
    console.print(
        "classify_class_attrs:",
    )
    # pprint(classify_class_attrs(Markdown))
    console.print(
        f"synopsis: {synopsis(mrender.__file__)}\n",
    )
    console.print(
        f"synopsis: {synopsis(mbpy.__file__)}\n",
    )
    console.print(
        f"synopsis: {synopsis(mbpy.__file__)}\n",
    )
    console.print(
        f"source_synopsis: {source_synopsis(Path(mrender.__file__).open())}\n",
    )
    console.print(
        f"splitdoc: {splitdoc(Markdown.__doc__)}\n",
    )
    console.print(
        f"safeimport: {safeimport('mrender')}\n",
    )
    console.print(
        f"describe: {describe(Markdown)}\n",
    )
    console.print(
        f"locate: {locate('mrender')}\n",
        
    )
    Path("html").write_text(HTMLDoc().docmodule(Markdown))


def is_third_party(candidate, currentpkg="mb") -> bool:
    if candidate is None:
        return False
    if not isinstance(candidate, ModuleType):
        candidate = getmodule(candidate)
    if candidate is None:
        return False
    return (
        candidate.__name__ not in sys.builtin_module_names
        and not candidate.__name__.startswith("_")
        and candidate not in (io, os, sys, builtins, _imp, typing)
        and hasattr(candidate, "__file__")
        and candidate.__file__ is not None
        and candidate.__package__ != currentpkg
    )

def third_party_packages() -> list[str]:
    return [mod.__name__ for mod in sys.modules.values() if is_third_party(mod)]


def currentmodule() -> ModuleType | SimpleNamespace:
    return getmodule(currentframe()) or SimpleNamespace(**{"__file__": "Unknown"})


def parentmodule() -> ModuleType:
    return sys.modules[caller() or "__main__"]


def string(iterable) -> str:
    return "".join(iterable)


BaseT: Final = cast(type,import_utils.smart_import("pydantic.BaseModel", "type_safe_lazy") or dict)

class RequestModel(BaseT):
    args: list
    kwargs: dict


def main() -> None:
    console = Console()
    test_pydoc_methods()
    with suppress.step() as ex:

        RequestModel.model_json_schema(mode=32)
    if ex:
        for line in ex:
            console.print(line)
        exit()
        tb =Traceback.from_exception(type(ex), ex, ex.tb)
        console.print(tb)
        # logging.error("6Third party packages: %s", third_party_packages())
        # console.print(Traceback.from_exception(type(ex), ex, ex.__traceback__))
        # logging.error("8Current module: %s", currentmodule())
        # logging.error("9Parent module: %s", "")
        # console.print("hello")
        # console.print(
        #     Traceback.from_exception(type(ex), ex, ex.__traceback__,width=console.width)
        # )
        console.print(f"Current module:[link]{currentmodule().__file__}[/link]")
    else:
        console.print("No exception")

if __name__ == "__main__":
    main()
