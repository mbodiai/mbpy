import _imp
import builtins
import inspect
import io
import logging
import os
import sys
import traceback
import traceback as tb
import typing
from contextlib import AbstractContextManager
from inspect import currentframe, getmodule
from io import StringIO
from pathlib import Path
from pydoc import (
    HTMLDoc,
    allmethods,
    apropos,
    classify_class_attrs,
    describe,
    locate,
    safeimport,
    source_synopsis,
    splitdoc,
    synopsis,
)
from pydoc_data import topics
from site import getuserbase
from traceback import TracebackException

# context.py
from types import FrameType, ModuleType, SimpleNamespace, TracebackType
from typing import Callable, Iterable, List, Optional, Self, Tuple, Type, TypeAlias, TypeVar, Union, cast
from typing_extensions import Final

from mrender import Markdown
from rich.console import Console
from rich.traceback import Traceback

from mbpy.utils import import_utils
from mbpy.utils._typing import caller
from mbpy.utils.collections import compose

T = TypeVar("T")


def onlyone(iterable: Iterable[T] | T) -> T:
    if not isinstance(iterable, Iterable):
        return iterable
    return next(iter(iterable))

def walk_parents(traceback: TracebackType):
    """Walk the parent frames of a traceback."""
    frames = inspect.getinnerframes(traceback)
    for frame, filename, lineno, _, _, _ in frames:
        yield frame, filename, lineno


def grab_context(frame, filename, lineno, num_lines=5):
    """Grab the context of a frame."""
    lines = [""] + Path(filename).read_text().splitlines()

    return lines[max(0, lineno - num_lines) : lineno + num_lines]


def get_window(frames: Iterable[Tuple[FrameType, str, int]], num_lines=5):
    for frame, filename, lineno in frames:
        yield from grab_context(frame, filename, lineno, num_lines=num_lines)
        yield f"at {filename}:{lineno}"


class ExceptionHolder(Exception):
    def __init__(self, step: int = 0):
        self.exc: Optional[BaseException] = None
        self.tb: Optional[TracebackType] = None  # Store traceback
    def set_exception(self, exc: Optional[BaseException], tb: Optional[TracebackType] = None):
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
        if self.exc and not attr in ("__dict__", "__class__"):
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


class suppress(AbstractContextManager):
    """Context manager to suppress specified exceptions and capture them.
    ```
    Usage:
        with suppress(Exception) as ex:
            some_problematic_code()
        if ex:
           handle_problematic_code(ex)
    
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

    def __init__(
        self,
        *exceptions: Type[BaseException],
        dontignore: Optional[Type[BaseException]] = None,
        log: bool = False,
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
        self.callbacks = []
        self.filters = []
        
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
        self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException], tb: Optional[TracebackType]
    ) -> bool:
        if exc_type and issubclass(exc_type, self._exceptions) and not issubclass(exc_type, self.dontignore):
            self.holder.set_exception(exc_value, tb)  # Store both exception and traceback
            if self.log and not any(f(exc_value) for f in self.filters):
                logging.error(f"{exc_type.__name__}: {exc_value}") 
                if self.windowsize:
                    logging.error("".join(traceback.format_exception(exc_type, exc_value, tb, limit=self.windowsize)))
                else:
                    logging.exception(exc_value)
                
                logging.warning("The above exception was suppressed.")
            if self.callbacks:
                compose(type(self).then(func) for func in self.callbacks)(exc_value)
            return True  # Suppress the exception
        return False  # Do not suppress other exceptions

    def add_filter(self, filter: Callable[...,bool]):
        self.filters.append(filter)
    @classmethod
    def logignore(cls, *exceptions: Type[BaseException]):
        """Convenience method to create a suppress context manager with logging enabled."""
        return cls(*exceptions, log=True)

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
        return cls(Exception, dontignore=KeyboardInterrupt, step=step)

    @classmethod
    def nothirdparty(cls, *exceptions:Type[BaseException]):
        cls = cls(*exceptions)
        cls.add_filter(isthirdparty)
        return cls
    @classmethod
    def then(cls, func):
        """Suppress exceptions then run a function that accepts the exception. Can be chained."""
        ctx = cls(Exception)
        ctx.callbacks.append(func)
        return ctx

console = Console()


def test_pydoc_methods() -> None:


    console.print(
        f"allmethods: {allmethods(Markdown)}\n"
        f"apropos: {apropos('Markdown')}\n"
        f"classify_class_attrs: {classify_class_attrs(Markdown)}\n"
        f"synopsis: {synopsis(Markdown.__file__)}\n"
        f"source_synopsis: {source_synopsis(StringIO(Path(Markdown.__file__).read_text()))}\n"
        f"splitdoc: {splitdoc(Markdown.__doc__)}\n"
        f"safeimport: {safeimport('mrender')}\n"
        f"describe: {describe(Markdown)}\n"
        f"locate: {locate('mrender')}\n"
    )
    Path("html").write_text(HTMLDoc().docmodule(Markdown))


def isthirdparty(obj):
    if obj is None:
        return False
    if not isinstance(obj, ModuleType):
        obj = getmodule(obj)
    if obj is None:
        return False
    return (
        obj.__name__ not in sys.builtin_module_names
        and not obj.__name__.startswith("_")
        and obj not in (io, os, sys, builtins, _imp, typing)
        and hasattr(obj, "__file__")
        and obj.__file__ is not None
    )




def getcurrentmodule():
    return getmodule(currentframe()) or SimpleNamespace({"__file__": "Unknown"})


def getparentmodule():
    return sys.modules[caller() or "__main__"]


def string(iterable):
    return "".join(iterable)


import sys
BaseT: Final = cast(type,import_utils.smart_import("pydantic.BaseModel") or dict)

class RequestModel(BaseT):
    args: list
    kwargs: dict

def third_party_packages():
    if getattr(getcurrentmodule(), "__name__", None) == "__main__":
        pkg = getparentmodule().__package__
    return [v for k, v in sys.modules.items() if isthirdparty(v)]


def main():
    console = Console()
    with suppress.step() as ex:

        r = RequestModel.model_json_schema(mode=32)
    if ex:
        for line in ex:
            console.print(line)
        exit()
        tb =Traceback.from_exception(type(ex), ex, ex.tb)
        console.print(tb)
        # logging.error("6Third party packages: %s", third_party_packages())
        # console.print(Traceback.from_exception(type(ex), ex, ex.__traceback__))
        # logging.error("8Current module: %s", getcurrentmodule())
        # logging.error("9Parent module: %s", "")
        # console.print("hello")
        # console.print(
        #     Traceback.from_exception(type(ex), ex, ex.__traceback__,width=console.width)
        # )
        console.print(f"Current module:[link]{getcurrentmodule().__file__}[/link]")
    else:
        console.print("No exception")

if __name__ == "__main__":
    main()
