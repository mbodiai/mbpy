import click
from rich_click import RichGroup


class GroupedRichGroup(RichGroup):
    """Custom RichGroup to enable grouping commands into categories."""
    def __init__(self, *args, command_groups=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.command_groups = command_groups or {}

    def format_commands(self, ctx, formatter) -> None:
        """Override format_commands to display grouped commands."""
        for group_name, commands in self.command_groups.items():
            rows = []
            for cmd_name in commands:
                cmd = self.get_command(ctx, cmd_name)
                if cmd is not None and not cmd.hidden:
                    rows.append((cmd_name, cmd.get_short_help_str()))
            if rows:
                with formatter.section(group_name):
                    formatter.write_dl(rows)

@click.group(
    cls=GroupedRichGroup,
    command_groups={
        "Cache Commands": ["cache"],
        "Python Commands": ["python", "pip"],
        "Global Commands": ["sync", "version"],
    },
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option("-e", "--env", default=None, help="Specify the Python environment.")
@click.option("-d", "--debug", is_flag=True, help="Enable debug logging.")
def cli(env, debug) -> None:
    """An extremely fast Python package manager."""
    if debug:
        click.echo("Debugging enabled.")

# Cache Commands
@cli.command()
def cache() -> None:
    """Manage uv's cache."""
    click.echo("Cache management command.")

# Python Commands
@cli.command()
def python() -> None:
    """Manage Python versions."""
    click.echo("Python management command.")

@cli.command()
def pip() -> None:
    """Manage Python packages with pip."""
    click.echo("Pip command.")

# Global Commands
@cli.command()
def sync() -> None:
    """Sync dependencies."""
    click.echo("Sync command.")

@cli.command()
def version() -> None:
    """Display the version."""
    click.echo("Version command.")

if __name__ == "__main__":
    cli()