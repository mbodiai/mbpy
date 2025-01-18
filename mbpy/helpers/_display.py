import logging
from time import sleep
from typing import TYPE_CHECKING, ParamSpec, TypedDict, TypeVar, get_origin

from Cython.Plex.Regexps import Any

from mbpy.import_utils import smart_import

if TYPE_CHECKING:
    from typing import Callable, TypeVar


_console = None


def getconsole():

    from rich.console import Console
    from rich.theme import Theme

    from mbpy import THEME
    global _console
    if not _console:
        _console = Console(theme=Theme(THEME))
    return _console


def format_timestamp(timestamp: str) -> str:
    from datetime import datetime

    from dateutil.parser import parse
    from dateutil.relativedelta import relativedelta
    if not timestamp.strip():
        return ""
    dt = parse(timestamp)
    now = datetime.now(dt.tzinfo)
    rd = relativedelta(now, dt)

    if rd.days == 0:
        return "today"
    if rd.days == 1:
        return "yesterday"
    if rd.days < 7:
        return f"{rd.days} days ago"
    if rd.months == 0:
        return f"{rd.weeks} weeks ago"
    if rd.years == 0:
        return dt.strftime("%B %d")  # e.g. "November 22"

    return dt.strftime("%B %d, %Y")  # e.g. "November 22, 2024")

def display_similar_repos_table(
                              repos: list,
                              show_stars: bool = True,
                              max_results: int = 10,
                              console=None,
                              ) -> None:
    if not TYPE_CHECKING:
        Table = smart_import("rich.table.Table")
        take = smart_import("more_itertools.take")
    else:
        from more_itertools import take
        from rich.table import Table
    table = Table(show_header=True, pad_edge=False, box=None)
    console = console or _console
    # Updated columns with width constraints
    table.add_column("Name", style="cyan", width=30)
    table.add_column("Author/Org", style="cyan", width=20)
    table.add_column("Latest Update", style="cyan", width=15)
    table.add_column("Description", style="green", width=50, overflow="fold")
    if show_stars:
        table.add_column("Stars", style="cyan", justify="right", width=8)

    for repo in take(max_results, repos):
        # Get common fields with fallbacks
        name = repo.get('name', '')

        # Extract author from URL if not directly available
        author = repo.get('author', '')
        if not author and 'url' in repo:
            url_parts = repo['url'].split('/')
            if len(url_parts) > 3:
                author = url_parts[3]

        description = repo.get('description', '')
        if description and len(description) > 47:
            description = description[:47] + '...'

        # Handle different date formats
        latest_update = (
            repo.get("latest_release", {}).get("upload_time") if isinstance(repo.get("latest_release"), dict)
            else repo.get("latest_release") or
            repo.get("updated_at") or
            repo.get("updatedat") or
            ""
        )

        # Get URL with fallbacks
        if isinstance(repo, dict):
            url = (repo.get('github_url') if isinstance(repo.get('github_url'), str) else repo.get('github_url', [None])[0] if isinstance(repo.get('github_url'), list) else None) or \
                  (repo.get('url') if isinstance(repo.get('url'), str) else repo.get('url', [None])[0] if isinstance(repo.get('url'), list) else None) or \
                  (repo.get('urls', {}).get('Homepage') if isinstance(repo.get('urls', {}), dict) and isinstance(repo.get('urls', {}).get('Homepage'), str) else repo.get('urls', {}).get('Homepage', [None])[0] if isinstance(repo.get('urls', {}), dict) and isinstance(repo.get('urls', {}).get('Homepage'), list) else None) or ""
        else:
            url = ""

        row = [
            f"[link={url}]{name}[/link]",
            author,
            format_timestamp(latest_update),
            description,
        ]

        if show_stars:
            stars = str(repo.get("stargazers_count", repo.get("stargazerscount", 0)))
            row.append(stars)

        table.add_row(*row)

    console.print("\n")
    console.print(table)
    console.print("\n")

def isverbose(*args):
    import sys
    if not args:
        args = set(sys.argv)
    if isvverbose(*args):
        return True
    return any(arg in {"-v", "--verbose", "debug", "-d", "--debug"} for arg in args)

def isvverbose(*args):
    import sys
    if not args:
        args = set(sys.argv)
    return any(arg in {"-vv", "--DEBUG", "-vvv", "DEBUG"} for arg in args)


def install_logging():
    import logging
    import sys

    from rich.logging import RichHandler
    from rich.traceback import install as install_traceback

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

    log_level = "DEBUG" if isverbose() else "INFO"

    if isverbose():
        logging.getLogger().setLevel(logging.DEBUG)
    install_traceback(show_locals=isverbose(*sys.argv))

    logging.getLogger().addFilter(RichHandler())

_spinner = None


def SPINNER():
    global _spinner
    if _spinner:
        return _spinner

    import asyncio
    import signal
    import threading
    from time import sleep
    from rich.live import Live
    from rich.spinner import Spinner as RichSpinner
    from rich.console import Console
    from rich.text import Text

    class Spinner:
        def __init__(self, text: str = "Working...", spinner_type: str = "dots2", console=None):
            self.text = text
            self.spinner_type = spinner_type
            self.spinning = False
            self.stop_requested = False
            self._spinner = RichSpinner(spinner_type, text)
            self._console = console or Console()
            self._live = Live(self._spinner, refresh_per_second=20, transient=True, console=self._console)

            self._thread: threading.Thread | None = None
            self._stop_event = threading.Event()

            import atexit
            atexit.register(self.cleanup)

            for sig in (
                signal.SIGINT,
                signal.SIGTERM,
                signal.SIGQUIT,
                signal.SIGHUP,
                signal.SIGABRT,
                signal.SIGUSR1,
            ):
                signal.signal(sig, self.cleanup)

        def _spin(self):
            with self._live:
                while not self._stop_event.is_set():
                    sleep(0.1)
                    self._live.update(self._spinner)
                self.spinning = False
            self._live.console.print("")

        async def astart(self) -> None:
            await asyncio.to_thread(self.start)

        def start(self) -> None:
            if self.spinning:
                return
            self.spinning = True
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        async def astop(self) -> None:
            if not self.spinning or self.stop_requested:
                return
            self.stop()
          
        def stop(self) -> None:
            if not self.spinning or self.stop_requested:
                return
            self.stop_requested = True
            self._stop_event.set()
            if self._thread and self._thread.is_alive():
                self._thread.join()
                self._thread = None
            self._live.stop()
            self.spinning = False

        def cleanup(self, signum: int | None = None, frame=None) -> None:
            self.stop()

    _spinner = Spinner()
    return _spinner
P = ParamSpec("P")
R = TypeVar("R")

def to_click_options_args(*arg_names: str, repl: bool = False) -> "Callable[[Callable[P, R]], Callable[P, R]]":
    """A decorator to convert a function's type hints to Click options."""
    if TYPE_CHECKING:
        from functools import wraps
        from inspect import Parameter, signature
        from pathlib import Path
        from types import UnionType
        from typing import get_args, get_type_hints

        import rich_click as click
        from more_itertools import all_unique, always_iterable, replace, unique_everseen
        from rich_click import Argument, Command, Option, Parameter

        from mbpy.collect import compose, wraps
        from mbpy.import_utils import smart_import

    else:
        from mbpy.import_utils import smart_import
        click = smart_import("rich_click")
        inspect = smart_import("inspect")
        signature = smart_import("inspect").signature
        Parameter = smart_import("inspect.Parameter")
        Option = smart_import("rich_click.Option")
        Command = smart_import("rich_click.Command")
        unique_everseen = smart_import("more_itertools").unique_everseen
        all_unique = smart_import("more_itertools").all_unique
        chain = smart_import("itertools").chain
        Argument = smart_import("rich_click.Argument")
        wraps = smart_import("mbpy.collect").wraps
        compose = smart_import("mbpy.collect").compose
        get_type_hints = smart_import("typing").get_type_hints
        Path = smart_import("pathlib").Path
        replace = smart_import("more_itertools").replace
        UnionType = smart_import("types").UnionType
        get_args = smart_import("typing").get_args
        always_iterable = smart_import("more_itertools").always_iterable

    def decorator(func: "Callable[P, R]") -> "Callable[P, R]":
        sig = signature(func)
        Path = smart_import("pathlib").Path
        Literal = smart_import("typing").Literal
        logging.debug(f"sig: {sig}, func: {func}")
        type_hints = get_type_hints(
            func, globalns={"Path": Path, "Literal": Literal, **func.__globals__},
        )
        type_hints = dict(
            map(
                lambda x: (
                    x[0],
                    get_args(x[1])[0]
                    if isinstance(x[1], UnionType) and get_origin(x[1]) is not Literal
                    else click.Choice(get_args(x[1]))
                    if next(always_iterable(get_origin(x[1])), None) is Literal
                    else x[1],
                ),
                type_hints.items(),
            ),
        )
        options = []
        args = []
        allnames = set(sig.parameters.keys()) - {"self", "cls", "args", "kwargs"} - set(arg_names)
        if all_unique([a[0] for a in allnames]):
            short = dict(zip(allnames, [a[0] for a in allnames], strict=False))
        else:
            short = dict(zip(allnames, unique_everseen([a[0] for a in allnames]), strict=False))
        logging.debug(f"types: {type_hints}")
        for name, param in sig.parameters.items():
            if name in {"self", "cls", "args", "kwargs"}:
                continue
            opt_args = (
                f"--{name}",
            )
            class OptKwargs(TypedDict):
                type: click.ParamType
                is_flag: bool
                default: Any
            if short.get(name):
                opt_args += (f"-{short.get(name)}",)
            opt_kwargs = dict(
                type=type_hints[name],
                is_flag=type_hints[name] is bool,
                default=param.default,
            )
            if name in arg_names:
                args.append(
                    click.argument(
                        name,
                        type=type_hints[name],
                        required=param.default == Parameter.empty,
                    ),
                )
            elif param.default == Parameter.empty:
                options.append(
                    click.option(
                        *opt_args,
                        **opt_kwargs,
                    ),
                )
            else:
                options.append(
                    click.option(
                        *opt_args,
                        **opt_kwargs,
                    ),
                )
        @wraps(func)
        def wrapping(*args, **kwargs):
            print(f"args: {args}, kwargs: {kwargs}")
            return func(*args, **kwargs)

        wrapper = compose(
            click.command(name=func.__name__, help=func.__doc__),
            *options,
            *args,
        )(wrapping)

        return wrapper

    return decorator
