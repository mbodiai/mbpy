import _imp
import builtins
import inspect
import io
import logging
import os
import sys
import traceback
import typing
from contextlib import AbstractContextManager, contextmanager
from inspect import currentframe, getmodule
from pathlib import Path
from pydoc import (  # noqa: E402
    HTMLDoc,
    ModuleScanner,
    allmethods,
    apropos,
    classify_class_attrs,
    describe,
    help,
    locate,
    pathdirs,
    resolve,
    safeimport,
    source_synopsis,
    splitdoc,
    synopsis,
    writedoc,
    writedocs,
)
from pydoc_data import topics
from site import getuserbase
from traceback import TracebackException
from types import ModuleType, TracebackType
from typing import Self

from embdata.sample import Sample
from rich.console import Console
from rich.traceback import Traceback

from mbpy._typing import ExceptionTrap, _caller
from mbpy.graph import generate


class suppress(AbstractContextManager): # type: ignore # noqa: N801
    """Context manager to suppress specified exceptions.

    After the exception is suppressed, execution proceeds with the next
    statement following the with statement.

         with suppress(FileNotFoundError) as ex:
             os.remove(somefile)
         logging.log(traceback.format_exc())
    """

    def __init__(self, *exceptions: list[ExceptionTrap]) -> None:
        self._exceptions = exceptions
        self.exc = None
        self.exc_type = None

    def __enter__(self) -> Self:
        return self

    def __call__(self, capture: bool = False) -> Self:
        self.capture = capture
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None, /
    ):
        # Unlike isinstance and issubclass, CPython exception handling
        # currently only looks at the concrete type hierarchy (ignoring
        # the instance and subclass checking hooks). While Guido considers
        # that a bug rather than a feature, it's a fairly hard one to fix
        # due to various internal implementation details. suppress provides
        # the simpler issubclass based semantics, rather than trying to
        # exactly reproduce the limitations of the CPython interpreter.
        #
        # See http://bugs.python.org/issue12029 for more details
        if exc_type is not None and issubclass(exc_type, self._exceptions):
            self.exc_type = exc_type
            self.exc = exc_value
            self.traceback = traceback
            return True
        return False


def test_pydoc_methods():
    console.print(
        f"allmethods: {allmethods(Sample)}\n"
        f"apropos: {apropos('traceback')}\n"
        f"classify_class_attrs: {classify_class_attrs(Sample)}\n"
        f"synopsis: {synopsis(Sample)}\n"
        f"source_synopsis: {source_synopsis(Sample)}\n"
        f"splitdoc: {splitdoc(Sample)}\n"
        f"safeimport: {safeimport('traceback')}\n"
        f"describe: {describe(Sample)}\n"
        f"HTMLDoc: {HTMLDoc(ToolCall)}\n"
    )

with suppress(FileNotFoundError) as ex:
    os.remove("somefile")
console = Console()
def getcurrentmodule():
    return getmodule(currentframe())
def getparentmodule():
    return sys.modules[_caller()]

print(getcurrentmodule())
print(getparentmodule())
print(topics.topics["atom-literals"])
print(topics.topics["atom-identifiers"])
test_pydoc_methods()
exit()
def string(iterable):
    return "".join(iterable)
import sys

def isthirdparty(obj):
    if obj is None:
        return False
    if not isinstance(obj, ModuleType):
        obj = getmodule(obj)
    if obj is None:
        return False
    return obj.__name__ not in sys.builtin_module_names\
        and not obj.__name__.startswith("_")\
        and obj not in (io, os, sys, builtins, _imp, typing)\
            and hasattr(obj, "__file__") and obj.__file__ is not None

def walk_parents(traceback: TracebackType):
    """Walk the parent frames of a traceback."""
    frames = inspect.getinnerframes(traceback)
    for frame, filename, lineno, _, _, _ in frames:
        yield frame, filename, lineno

def grab_context(frame, filename, lineno, num_lines=5):
    """Grab the context of a frame."""
    lines  = [""] + Path(filename).read_text().splitlines()
    
    context = lines[max(0, lineno - num_lines):lineno + num_lines]
    


def main():
    def third_party_packages():

        if getcurrentmodule().__name__ == "__main__":
            pkg = getparentmodule().__package__
        return [v for k, v in sys.modules.items() if isthirdparty(v)]
    if ex.exc:
        logging.error("1Exception Traceback: %s", ex.exc)
        logging.error(string(TracebackException.from_exception(ex.exc).format()))
        logging.error("2Exception: %s", ex.exc)
        logging.error(ex.exc)
        logging.error("3Traceback: %s", ex.exc.__traceback__)
        logging.error(ex.exc.__traceback__)
        logging.error("4 Cause: %s", ex.exc.__cause__)
        logging.error(ex.exc.__cause__)
        logging.error("5Context: %s", ex.exc.__context__)
        logging.error(ex.exc.__context__)
        logging.error("6Third party packages: %s", third_party_packages())
        console.print(Traceback.from_exception(ex.exc_type, ex.exc, ex.traceback, suppress=third_party_packages()))
        logging.error("7User base: %s", getuserbase())
        console.print(Traceback.from_exception(ex.exc_type, ex.exc, ex.traceback))
    print(ex)


if __name__ == "__main__":
    main()