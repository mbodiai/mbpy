import rich_click as click

from mbpy.cmd import arun


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-q", "--quiet", is_flag=True, help="Do not print any output")
@click.option("-v", "--verbose", count=True, help="Use verbose output")
@click.option(
    "--color",
    type=click.Choice(["auto", "always", "never"], case_sensitive=False),
    default="auto",
    show_default=True,
    help="Control colors in output",
)
@click.option(
    "--native-tls",
    is_flag=True,
    help="Whether to load TLS certificates from the platform's native certificate store",
)
@click.option("--offline", is_flag=True, help="Disable network access")
@click.option(
    "--allow-insecure-host",
    multiple=True,
    metavar="ALLOW_INSECURE_HOST",
    help="Allow insecure connections to a host",
)
@click.option("--no-progress", is_flag=True, help="Hide all progress outputs")
@click.option(
    "--directory",
    type=click.Path(),
    metavar="DIRECTORY",
    help="Change to the given directory prior to running the command",
)
@click.option(
    "--project",
    type=click.Path(),
    metavar="PROJECT",
    help="Run the command within the given project directory",
)
@click.option(
    "--config-file",
    type=click.Path(),
    metavar="CONFIG_FILE",
    help="The path to a `uv.toml` file to use for configuration",
)
@click.option(
    "--no-config",
    is_flag=True,
    help="Avoid discovering configuration files (`pyproject.toml`, `uv.toml`)",
)
@click.version_option(
    prog_name="uv",
    message="uv %(version)s",
    version="0.5.5",
    help="Display the uv version",
)
def uv(
    quiet,
    verbose,
    color,
    native_tls,
    offline,
    allow_insecure_host,
    no_progress,
    directory,
    project,
    config_file,
    no_config,
) -> None:
    """An extremely fast Python package manager."""
    pass


@uv.command()
@click.argument("args", nargs=-1)
async def run_command(args) -> None:
    """Run a command or script."""
    await arun(f"uv run {' '.join(args)}")


@uv.command()
@click.argument("args", nargs=-1)
async def init(args) -> None:
    """Create a new project."""
    await arun(f"uv init {' '.join(args)}")


@uv.command()
@click.argument("args", nargs=-1)
async def add(args) -> None:
    """Add dependencies to the project."""
    await arun(f"uv add {' '.join(args)}")


@uv.command()
@click.argument("args", nargs=-1)
async def remove(args) -> None:
    """Remove dependencies from the project."""
    await arun(f"uv remove {' '.join(args)}")


@uv.command()
@click.argument("args", nargs=-1)
async def sync(args) -> None:
    """Update the project's environment."""
    await arun(f"uv sync {' '.join(args)}")


@uv.command()
@click.argument("args", nargs=-1)
async def lock(args) -> None:
    """Update the project's lockfile."""
    await arun(f"uv lock {' '.join(args)}")


@uv.command()
@click.argument("args", nargs=-1)
async def export(args) -> None:
    """Export the project's lockfile to an alternate format."""
    await arun(f"uv export {' '.join(args)}")


@uv.command()
@click.argument("args", nargs=-1)
async def tree(args) -> None:
    """Display the project's dependency tree."""
    await arun(f"uv tree {' '.join(args)}")


@uv.command()
@click.argument("args", nargs=-1)
async def tool(args) -> None:
    """Run and install commands provided by Python packages."""
    await arun(f"uv tool {' '.join(args)}")


@uv.command()
@click.argument("args", nargs=-1)
async def python(args) -> None:
    """Manage Python versions and installations."""
    await arun(f"uv python {' '.join(args)}")


@uv.command()
@click.argument("args", nargs=-1)
async def pip(args) -> None:
    """Manage Python packages with a pip-compatible interface."""
    await arun(f"uv pip {' '.join(args)}")


@uv.command()
@click.argument("args", nargs=-1)
async def venv(args) -> None:
    """Create a virtual environment."""
    await arun(f"uv venv {' '.join(args)}")


@uv.command()
@click.argument("args", nargs=-1)
async def build(args) -> None:
    """Build Python packages into source distributions and wheels."""
    await arun(f"uv build {' '.join(args)}")


@uv.command()
@click.argument("args", nargs=-1)
async def publish(args) -> None:
    """Upload distributions to an index."""
    await arun(f"uv publish {' '.join(args)}")


@uv.command()
@click.argument("args", nargs=-1)
async def cache(args) -> None:
    """Manage uv's cache."""
    await arun(f"uv cache {' '.join(args)}")


@uv.command()
@click.argument("args", nargs=-1)
async def self(args) -> None:
    """Manage the uv executable."""
    await arun(f"uv self {' '.join(args)}")


@uv.command()
@click.argument("args", nargs=-1)
async def version(args) -> None:
    """Display uv's version."""
    await arun(f"uv version {' '.join(args)}")


if __name__ == "__main__":
    uv()
