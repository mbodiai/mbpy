from functools import partial
import rich_click as click
from mbpy.import_utils import smart_import
def cli(*args,commands: tuple|list, **kwargs):
    """
    Command Line Interface (CLI) decorator for handling subcommands and CLI operations.

    This decorator transforms a function into a CLI command handler, providing command registration,
    execution flow control, and basic debugging support.

    Args:
        *args: Variable positional arguments passed to the decorator.
        commands (tuple|list): Collection of command functions to be registered and executed.
        **kwargs: Variable keyword arguments, supporting:
            - debug (bool): Enable debug mode logging when True.
            - ctx: Command context object for subcommand handling.

    Returns:
        Union[Context, Awaitable]: Returns either the command context for subcommands
        or runs the first command asynchronously if no subcommand is specified.

    Examples:
        ```python
        @cli(commands=[cmd1, cmd2])
        async def my_cli():
            # CLI implementation
            pass

        @cli(commands=[cmd1, cmd2], debug=True)
        async def debug_cli():
            # CLI with debug logging
            pass
        ```

    Notes:
        - Automatically configures debug logging when debug flag is set
        - Handles subcommand routing through context object
        - Falls back to first command execution if no subcommand specified
        - Integrates with smart console output handling

    Raises:
        ImportError: If console dependencies cannot be imported
        RuntimeError: If command execution fails
    """
    from mbpy.main import AsyncGroup,run_async,get_help_config
    logging = smart_import('logging')
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
    def _cli(ctx: click.RichContext, env, debug):
        import sys
        from mbpy.main import run_async

        console = smart_import('mbpy.helpers._display.getconsole')()
        if sys.flags.debug or debug:
            logging.basicConfig(level=logging.DEBUG, force=True)

        if ctx.invoked_subcommand:
            return ctx

        console.print("No subcommand specified. Showing dependencies:")
        return run_async(commands[0])

    for command in commands:
        _cli.add_command(command)
    return _cli(**kwargs)

def entrypoint(*commands):
    return  partial(cli,commands=commands)
    

