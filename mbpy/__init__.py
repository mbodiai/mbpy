# SPDX-FileCopyrightText: 2024-present Sebastian Peralta <sebastian@mbodi.ai>
#
# SPDX-License-Identifier: apache-2.0
import asyncio
import atexit
import logging
import signal
import sys
import threading
from time import sleep
from typing import TYPE_CHECKING

from rich.live import Live
from rich.logging import RichHandler
from rich.pretty import install
from rich.spinner import Spinner as RichSpinner
from rich.traceback import install as install_traceback

from .utils.import_utils import smart_import

DataModel = smart_import("pydantic.BaseModel", "type_safe_lazy") or smart_import("typing_extension.TypedDict")

if TYPE_CHECKING:
    from pydantic import BaseModel

    DataModel = BaseModel


def isverbose(*args):
    if not args:
            args = set(sys.argv)
    if isvverbose(*args):
        return True
    return any(arg in {"-v", "--verbose", "debug", "-d", "--debug"} for arg in args)


def isvverbose(*args):
    if not args:
        args = set(sys.argv)
    return any(arg in {"-vv", "--DEBUG", "-vvv", "DEBUG"} for arg in args)



logging.getLogger().addHandler(RichHandler())
if isverbose():
    logging.getLogger().setLevel(logging.DEBUG)
if isvverbose():
    logging.getLogger().setLevel(logging.DEBUG)
install(max_length=10, max_string=80)
install_traceback(show_locals=isvverbose(*sys.argv))


class Spinner:
    def __init__(self, text: str = "Working...", spinner_type: str = "dots2"):
        self.text = text
        self.spinner_type = spinner_type
        self.spinning = False
        self.stop_requested = False
        self._spinner = RichSpinner(spinner_type, text)
        self._live = Live(self._spinner, refresh_per_second=20, transient=True)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Register cleanup handlers
        atexit.register(self.cleanup)
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGQUIT, signal.SIGHUP, signal.SIGABRT, signal.SIGUSR1):
            signal.signal(sig, self.cleanup)

    def _spin(self):
        """Internal method to handle spinning in a separate thread."""
        with self._live:
            while not self._stop_event.is_set():
                sleep(0.1)
            self.spinning = False

    async def astart(self) -> None:
        """Start the spinner asynchronously using asyncio.to_thread."""
        await asyncio.to_thread(self.start)

    def start(self) -> None:
        """Start the spinner in a separate thread."""
        if self.spinning:
            return  # Already spinning

        self.spinning = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the spinner and perform cleanup."""
        if not self.spinning or self.stop_requested:
            return

        self.stop_requested = True
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join()
            self._thread = None

        self._live.stop()
        self.spinning = False

    def cleanup(self, signum: int | None= None, frame= None) -> None:
        """Cleanup handler to stop the spinner gracefully."""
        self.stop()
        if signum is not None:
            sys.exit(0)


# Instantiate the SpinnerHandler
SPINNER = Spinner()







from . import cli, commands, context, mpip  # noqa: E402
from .utils import collect, import_utils  # noqa: E402

__all__ = ["context", "mpip","DataModel", "context", "mpip",
           "cli", "commands", "collect", "import_utils","isverbose","isvverbose", "SPINNER"]

