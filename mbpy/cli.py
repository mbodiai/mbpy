from __future__ import annotations
import asyncio
import logging
import os
from functools import lru_cache
from typing import Any, Awaitable, Coroutine, Iterable, TypeVar, TYPE_CHECKING, Union, overload
import rich_click as click

from mbpy.import_utils import smart_import

def get_process_executor() -> "ProcessPoolExecutor":
    """Get an optimized ProcessPoolExecutor."""
    import atexit
    import os
    import signal
    if TYPE_CHECKING:
        import multiprocessing as mp
        import os
        import sys
        from concurrent.futures import ProcessPoolExecutor

    else:
        ProcessPoolExecutor = smart_import('concurrent.futures.ProcessPoolExecutor')
        mp = smart_import('multiprocessing')
        ctx = mp.get_context('fork')
        os = smart_import('os')
        signal = smart_import('signal')
        atexit = smart_import('atexit')

    ProcessPoolExecutor = ssmart_import('concurrent.futures.ProcessPoolExecutor')
    ctx = mp.get_context('fork')
    # Calculate optimal workers based on CPU cores and task type
    cpu_count = os.cpu_count() or 1
    max_workers = min(cpu_count * 2, 32) # Double CPU count but cap at 32

    executor = ProcessPoolExecutor(
        max_workers=max_workers,
        mp_context=ctx,
        initializer=_process_initializer,
    )

    def _cleanup():
        executor.shutdown(wait=False, cancel_futures=True)
    atexit.register(_cleanup)

    # Improved signal handling
    def _signal_handler(signum, frame):
        executor.shutdown(wait=False, cancel_futures=True)
        sys.exit(128 + signum)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    return executor

def _process_initializer():
    """Initialize process worker."""
    signal = smart_import('signal')
    signal.signal(signal.SIGINT, signal.SIG_IGN)
T = TypeVar("T")
async def process_tasks(tasks: "Iterable[Awaitable[T]]") -> "AsyncIterator[T]":
    """Process tasks with improved error handling and cancellation."""
    async def worker(task: Awaitable[T]) -> T | None:
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            return None
        except Exception as e:
            logging.error(f"Task failed: {e}")
            return None

    pending = {asyncio.create_task(worker(task)) for task in tasks}

    while pending:
        done, pending = await asyncio.wait(
            pending,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            try:
                result = await task
                if result is not None:
                    yield result
            except Exception as e:
                logging.error(f"Failed to process result: {e}")



@overload
def get_executor(kind: Literal["process"])-> "ProcessPoolExecutor":...
@overload
def get_executor(kind: Literal["thread"])-> "ThreadPoolExecutor":...
@overload
def get_executor(kind: Literal["as_completed"]) -> "Iterable[Coroutine[Any, Any, Any]]":...
@lru_cache(None)
def get_executor(kind: Literal["process", "thread", "as_completed"]) -> "ThreadPoolExecutor | ProcessPoolExecutor | Iterable[Coroutine[Any, Any, Any]]":
    """Get cached executor instance."""
    lru_cache = smart_import('functools.lru_cache')
    ThreadPoolExecutor = smart_import('concurrent.futures.ThreadPoolExecutor')
    as_completed = smart_import('concurrent.futures.as_completed')
    if kind == "thread":
        return ThreadPoolExecutor(
            max_workers=min(12, (os.cpu_count() or 1) * 4),
        )
    if kind == "process":
        return get_process_executor()
    if kind == "as_completed":
        return as_completed
    raise ValueError(f"Invalid executor kind: {kind}")


def run_async(coro):
    """Run an asynchronous coroutine within an existing event loop or create a new one."""
    uvloop = smart_import('uvloop')

    try:
        # Try to get the running loop first
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # If no running loop, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        return uvloop.Loop.get_task_factory(coro)

    logging.debug("Running coroutine in event loop")
    return loop.run_until_complete(coro)





class AsyncGroup(click.RichGroup):
    """Custom Click Group that supports asynchronous command callbacks."""

    def invoke(self, ctx: click.Context) -> Any:
        """Override the invoke method to handle async commands."""
        if ctx.invoked_subcommand is not None and "-h" in ctx.params or "--help" in ctx.params:
            SPINNER = smart_import('mbpy.helpers._display.SPINNER')()
            SPINNER.stop()
        coro = super().invoke(ctx)
        if asyncio.iscoroutine(coro):
            return run_async(coro)
        return coro

    def __call__(self, *args, **kwargs):
        """Override call to support asynchronous invocation."""
        return super().__call__(*args, **kwargs)

def get_help_config():
    r"""Get the help formatter configuration. for Rich Help Configuration class.

    When merging multiple RichHelpConfigurations together, user-defined values always
    take precedence over the class's defaults. When there are multiple user-defined values
    for a given field, the right-most field is used.
    ```python
    # FIND:
    # (?<field>[a-zA-Z_]+): (?<typ>.*?) = field(default=.*?)
    # REPLACE:
    # ${field}: ${typ} = field(default_factory=_get_default(\\\"\\U${field}\\E\\\"))
    ```

    # Default styles
    style_option: \\\"rich.style.StyleType\\\" = field(default=\\\"bold cyan\\\")
    style_argument: \\\"rich.style.StyleType\\\" = field(default=\\\"bold cyan\\\")
    style_command: \\\"rich.style.StyleType\\\" = field(default=\\\"bold cyan\\\")
    style_switch: \\\"rich.style.StyleType\\\" = field(default=\\\"bold green\\\")
    style_metavar: \\\"rich.style.StyleType\\\" = field(default=\\\"bold yellow\\\")
    style_metavar_append: \\\"rich.style.StyleType\\\" = field(default=\\\"dim yellow\\\")
    style_metavar_separator: \\\"rich.style.StyleType\\\" = field(default=\\\"dim\\\")
    style_header_text: \\\"rich.style.StyleType\\\" = field(default=\\\"\\\")
    style_epilog_text: \\\"rich.style.StyleType\\\" = field(default=\\\"\\\")
    style_footer_text: \\\"rich.style.StyleType\\\" = field(default=\\\"\\\")
    style_usage: \\\"rich.style.StyleType\\\" = field(default=\\\"yellow\\\")
    style_usage_command: \\\"rich.style.StyleType\\\" = field(default=\\\"bold\\\")
    style_deprecated: \\\"rich.style.StyleType\\\" = field(default=\\\"red\\\")
    style_helptext_first_line: \\\"rich.style.StyleType\\\" = field(default=\\\"\\\")
    style_helptext: \\\"rich.style.StyleType\\\" = field(default=\\\"dim\\\")
    style_option_help: \\\"rich.style.StyleType\\\" = field(default=\\\"\\\")
    style_option_default: \\\"rich.style.StyleType\\\" = field(default=\\\"dim\\\")
    style_option_envvar: \\\"rich.style.StyleType\\\" = field(default=\\\"dim yellow\\\")
    style_required_short: \\\"rich.style.StyleType\\\" = field(default=\\\"red\\\")
    style_required_long: \\\"rich.style.StyleType\\\" = field(default=\\\"dim red\\\")
    style_options_panel_border: \\\"rich.style.StyleType\\\" = field(default=\\\"dim\\\")
    style_options_panel_box: Optional[Union[\\\"str\\\", \\\"rich.box.Box\\\"]] = field(default=\\\"ROUNDED\\\")
    align_options_panel: \\\"rich.align.AlignMethod\\\" = field(default=\\\"left\\\")
    style_options_table_show_lines: bool = field(default=False)
    style_options_table_leading: int = field(default=0)
    style_options_table_pad_edge: bool = field(default=False)
    style_options_table_padding: \\\"rich.padding.PaddingDimensions\\\" = field(default_factory=lambda: (0, 1))
    style_options_table_box: Optional[Union[\\\"str\\\", \\\"rich.box.Box\\\"]] = field(default=\\\"\\\")
    style_options_table_row_styles: Optional[List[\\\"rich.style.StyleType\\\"]] = field(default=None)
    style_options_table_border_style: Optional[\\\"rich.style.StyleType\\\"]] = field(default=None)
    style_commands_panel_border: \\\"rich.style.StyleType\\\" = field(default=\\\"dim\\\")
    style_commands_panel_box: Optional[Union[\\\"str\\\", \\\"rich.box.Box\\\"]] = field(default=\\\"ROUNDED\\\")
    align_commands_panel: \\\"rich.align.AlignMethod\\\" = field(default=\\\"left\\\")
    style_commands_table_show_lines: bool = field(default=False)
    style_commands_table_leading: int = field(default=0)
    style_commands_table_pad_edge: bool = field(default=False)
    style_commands_table_padding: \\\"rich.padding.PaddingDimensions\\\" = field(default_factory=lambda: (0, 1))
    style_commands_table_box: Optional[Union[\\\"str\\\", \\\"rich.box.Box\\\"]] = field(default=\\\"\\\")
    style_commands_table_row_styles: Optional[List[\\\"rich.style.StyleType\\\"]] = field(default=None)
    style_commands_table_border_style: Optional[\\\"rich.style.StyleType\\\"]] = field(default=None)
    style_commands_table_column_width_ratio: Optional[Union[Tuple[None, None], Tuple[int, int]]] = field(
        default_factory=lambda: (None, None)
    )
    style_errors_panel_border: \\\"rich.style.StyleType\\\" = field(default=\\\"red\\\")
    style_errors_panel_box: Optional[Union[\\\"str\\\", \\\"rich.box.Box\\\"]] = field(default=\\\"ROUNDED\\\")
    align_errors_panel: \\\"rich.align.AlignMethod\\\" = field(default=\\\"left\\\")
    style_errors_suggestion: \\\"rich.style.StyleType\\\" = field(default=\\\"dim\\\")
    style_errors_suggestion_command: \\\"rich.style.StyleType\\\" = field(default=\\\"blue\\\")
    style_aborted: \\\"rich.style.StyleType\\\" = field(default=\\\"red\\\")
    width: Optional[int] = field(default_factory=terminal_width_default)
    max_width: Optional[int] = field(default_factory=terminal_width_default)
    color_system: Optional[Literal[\\\"auto\\\", \\\"standard\\\", \\\"256\\\", \\\"truecolor\\\", \\\"windows\\\"]] = field(default=\\\"auto\\\")
    force_terminal: Optional[bool] = field(default_factory=force_terminal_default)
    
    # Fixed strings
    header_text: Optional[Union[\\\"str\\\", \\\"rich.text.Text\\\"]] = field(default=None)
    footer_text: Optional[Union[\\\"str\\\", \\\"rich.text.Text\\\"]] = field(default=None)
    deprecated_string: str = field(default=\\\"(Deprecated) \\\"")
    default_string: str = field(default=\\\"[default: {}]\\\")
    envvar_string: str = field(default=\\\"[env var: {}]\\\")
    required_short_string: str = field(default=\\\"*\\\")
    required_long_string: str = field(default=\\\"[required]\\\")
    range_string: str = field(default=\\\" [{}]\\\")
    append_metavars_help_string: str = field(default=\\\"({})\\\")
    arguments_panel_title: str = field(default=\\\"Arguments\\\")
    options_panel_title: str = field(default=\\\"Options\\\")
    commands_panel_title: str = field(default=\\\"Commands\\\")
    errors_panel_title: str = field(default=\\\"Error\\\")
    errors_suggestion: Optional[Union[\\\"str\\\", \\\"rich.text.Text\\\"]] = field(default=None)
    \\\"Defaults to Try 'cmd -h' for help. Set to False to disable.\\\"
    errors_epilogue: Optional[Union[\\\"str\\\", \\\"rich.text.Text\\\"]] = field(default=None)
    aborted_text: str = field(default=\\\"Aborted.\\\")
    
    # Behaviours
    show_arguments: bool = field(default=False)
    \\\"Show positional arguments\\\"
    show_metavars_column: bool = field(default=True)
    \\\"Show a column with the option metavar (eg. INTEGER)\\\"
    append_metavars_help: bool = field(default=False)
    \\\"Append metavar (eg. [TEXT]) after the help text\\\"
    group_arguments_options: bool = field(default=False)
    \\\"Show arguments with options instead of in own panel\\\"
    option_envvar_first: bool = field(default=False)
    \\\"Show env vars before option help text instead of after\\\"
    text_markup: Literal[\\\"ansi\\\", \\\"rich\\\", \\\"markdown\\\", None\\\"] = \\\"ansi\\\"
    use_markdown: bool = field(default=False)
    \\\"Silently deprecated; use `text_markup` field instead.\\\"
    use_markdown_emoji: bool = field(default=True)
    \\\"Parse emoji codes in markdown :smile:\\\"
    use_rich_markup: bool = field(default=False)
    \\\"Silently deprecated; use `text_markup` field instead.\\\"
    command_groups: Dict[str, List[CommandGroupDict]] = field(default_factory=lambda: {})
    \\\"Define sorted groups of panels to display subcommands\\\"
    option_groups: Dict[str, List[OptionGroupDict]] = field(default_factory=lambda: {})
    \\\"Define sorted groups of panels to display options and arguments\\\"
    use_click_short_help: bool = field(default=False)
    \\\"Use click's default function to truncate help text\\\"
    highlighter: Optional[\\\"rich.highlighter.Highlighter\\\"]] = field(default=None, repr=False, compare=False)
    \\\"(Deprecated) Rich regex highlighter for help highlighting\\\"
    
    highlighter_patterns: List[str] = field(
        default_factory=lambda: [
        r\"(^|[^\\w\\-])(?P<switch>-([^\\W0-9][\\w\\-]*\\w|[^\\W0-9]))\",
        r\"(^|[^\\w\\-])(?P<option>--([^\\W0-9][\\w\\-]*\\w|[^\\W0-9]))\",
        r\"(?P<metavar><[^>]+>)\",
        ]
    )
    """
    from dataclasses import asdict, dataclass, field
    from typing import Dict, List, Union

    import rich
    import rich.align
    import rich.box
    import rich.style
    PINK_BOLD: str = "bold #ffd7e5"
    GOLD_BOLD: str = "bold #ffd7af"
    WHITE_BOLD: str = "bold white"
    RED_BOLD: str = "bold red"
    @dataclass
    class RichHelpConfig:
        """Streamlined help configuration with consistent branding."""

        # Core brand colors
        PINK_BOLD = "bold #ffd7e5"
        GOLD_BOLD = "bold #ffd7af"
        WHITE_BOLD = "bold white"

        # Essential styles
        style_command: "rich.style.StyleType" = field(default=GOLD_BOLD)
        style_option: "rich.style.StyleType" = field(default=PINK_BOLD)
        style_usage: "rich.style.StyleType" = field(default=PINK_BOLD)
        style_header_text: "rich.style.StyleType" = field(default=WHITE_BOLD)
        style_helptext: "rich.style.StyleType" = field(default="white")

        # Remove all panels/boxes
        style_options_panel_box: Union[str, "rich.box.Box"] | None = field(default="")
        style_commands_panel_box: Union[str, "rich.box.Box"] | None = field(default="")
        style_errors_panel_box: Union[str, "rich.box.Box"] | None = field(default="")

        # Layout settings
        align_options_panel: "rich.align.AlignMethod" = field(default="left")
        align_commands_panel: "rich.align.AlignMethod" = field(default="left")
        style_options_table_show_lines: bool = field(default=False)
        style_commands_table_show_lines: bool = field(default=False)
        style_options_table_padding: "rich.padding.PaddingDimensions" = field(default_factory=lambda: (0, 2))

        # Section titles
        arguments_panel_title: str = field(default="ARGUMENTS:")
        options_panel_title: str = field(default="FLAGS:")
        commands_panel_title: str = field(default="COMMANDS:")

        # Error handling
        style_errors_suggestion: "rich.style.StyleType" = field(default="dim")
        style_errors_suggestion_command: "rich.style.StyleType" = field(default=PINK_BOLD)

        # Width settings
        width: int | None = field(default=100)
        max_width: int | None = field(default=100)

        # Enable command grouping
        group_arguments_options: bool = field(default=True)
        command_groups: Dict[str, List[dict]] = field(default_factory=lambda: {})

        # Text handling
        text_markup: Literal["ansi", "rich", "markdown", None] = "ansi"
    return asdict(RichHelpConfig())



@click.rich_config(help_config=get_help_config())
@click.help_option("-h", "--help")
@click.group("mbpy", cls=AsyncGroup)
@click.pass_context
@click.option(
    "-e",
    "--env",
    default=None,
    help="Specify the python, hatch, conda, or mbnix environment",
)
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    help="Enable debug logging",
)
def cli(ctx: click.RichContext, env, debug):
    SPINNER = smart_import('mbpy.helpers._display.SPINNER')()
    SPINNER.start()
    import sys
    if sys.flags.debug or debug:
        logging.basicConfig(level=logging.DEBUG, force=True)
    ctx.debug = debug
    ctx.params["debug"] = debug
    console = smart_import('mbpy.helpers._display.getconsole',debug=debug)()
    if debug:
        console.print("Debug mode enabled.", style="bold blue")
    if ctx.invoked_subcommand:
        return ctx

    return run_async(_show_command(env=env, debug=debug))



@overload
def base_args(env=True,debug=True,help=True) -> click.Command:...
@overload
def base_args(func) -> click.Command:...
def base_args(*args,**kwargs):
    """Add base arguments to a command."""
        
    if TYPE_CHECKING:
        from mbpy.collect import wraps
        from more_itertools import first
        from functools import partial
    else:
        wraps = smart_import('mbpy.collect.wraps')
        first = smart_import('more_itertools.first')
        partial = smart_import('functools.partial')

    if len(args) == 1 and callable(args[0]):
        args = list(args)
        func = args.pop(0)
        def decorator(func,*args,**kwargs):
            @wraps(func)
            def wrapper(*args,env=None,debug=None,**kwargs):
                if debug:
                    log = smart_import('mbpy.log')
                    log.debug().set()
                return func(*args,**kwargs)
            return wrapper
        return click.option(
            "-e",
            "--env",
            default=None,
            help="Specify the python, hatch, conda, or mb environment",
        )(
            click.option("-d", "--debug", is_flag=True, help="Enable debug logging")(
            click.help_option("-h", "--help")(
                decorator(partial(func,*args,**kwargs))
            )
            ),
        )
    args = list(args)
    env = kwargs.get('env',args.pop(0) if args else True)
    debug = kwargs.get('debug',args.pop(0) if args else True)
    help = kwargs.get('help',args.pop(0) if args else True)
    def decorator(func):
        @wraps(func)
        def wrapper(*args,env=None,debug=None,**kwargs):
            if debug:
                log = smart_import('mbpy.log')
                log.debug().set()
            return func(*args,**kwargs)

        if env:
            env_wrapper =  click.option(
            "-e",
            "--env",
            default=None,
            help="Specify the python, hatch, conda, or mb environment",
        )
        else:
            env_wrapper = lambda x: x
        if debug:
            debug_wrapper = click.option("-d", "--debug", is_flag=True, help="Enable debug logging")
        else:
            debug_wrapper = lambda x: x
        if help:
            help_wrapper = click.help_option("-h", "--help")
        else:
            help_wrapper = lambda x: x
        return help_wrapper(debug_wrapper(env_wrapper(wrapper)))
    return decorator
    



