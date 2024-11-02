
import logging
import logging.handlers
import os
import subprocess
import sys
import traceback
from asyncio.subprocess import PIPE
from functools import partial
from pathlib import Path

import rich_click as click
import tomlkit
from rich.console import Console
from rich.traceback import Traceback

from mbpy.bump import bump as bump_pkg
from mbpy.commands import interact, run, run_command
from mbpy.create import create_project
from mbpy.mpip import (
    ADDITONAL_KEYS,
    INFO_KEYS,
    base_name,
    find_and_sort,
    find_toml_file,
    get_package_info,
    modify_pyproject_toml,
    modify_requirements,
    name_and_version,
)
from mbpy.sync import append_notion_table_row
from mrender.md import Markdown

console = Console()
# TODO add a timeout option and support windows.
@click.group("mbpy")
@click.pass_context
@click.option(
    "-v",
    "--hatch-env",
    default=None,
    help="Specify the Hatch environment to use",
)
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    help="Enable debug logging",
)
def cli(ctx: click.Context, hatch_env, debug) -> None:
    if sys.flags.debug or debug:
        logging.basicConfig(level=logging.DEBUG, force=True)
    if ctx.invoked_subcommand is None:
        console.print("No subcommand specified. Showing dependencies:")
        show_command(hatch_env)


@cli.command("install", no_args_is_help=True)
@click.argument("packages", nargs=-1)
@click.option(
    "-r",
    "--requirements",
    type=click.Path(exists=True),
    help="Install packages from the given requirements file",
)
@click.option("-U", "--upgrade", is_flag=True, help="Upgrade the package(s)")
@click.option(
    "-e",
    "--editable",
    is_flag=True,
    help="Install a package in editable mode",
)
@click.option("--hatch-env", default=None, help="Specify the Hatch environment to use")
@click.option(
    "-g",
    "--dependency-group",
    default="dependencies",
    help="Specify the dependency group to use",
)
@click.option("-d", "--debug", is_flag=True, help="Enable debug logging")
def install_command(
    packages,
    requirements,
    upgrade,
    editable,
    hatch_env,
    dependency_group,
    *,
    debug=False,
) -> None:
    """Install packages and update requirements.txt and pyproject.toml accordingly.

    Args:
        packages (tuple): Packages to install.
        requirements (str, optional): Requirements file to install packages from. Defaults to None.
        upgrade (bool, optional): Upgrade the package(s). Defaults to False.
        editable (bool, optional): Install a package in editable mode. Defaults to False.
        hatch_env (str, optional): The Hatch environment to use. Defaults to "default".
        dependency_group (str, optional): The dependency group to use. Defaults to "dependencies".
        debug (bool, optional): Enable debug logging. Defaults to False.
    """
    _install_command(packages, requirements, upgrade, editable, hatch_env, dependency_group, debug)
    
def _install_command(packages, requirements, upgrade, editable, hatch_env, dependency_group, debug=False) -> None:
    if sys.flags.debug or debug:
        logging.basicConfig(level=logging.DEBUG, force=True)
        logging.info("Debug logging enabled.")
    processed_packages = []
    for package in packages:
        if "/" in package and Path(package).exists():
            package = Path(package).resolve()
        elif "/" in package and len(package.split("/")) == 2:
            package = f"git+https://github.com/{package}"
        elif "/" in package:
            console.print(
                f"Invalid package: {package}. Only local paths or GitHub URLs are supported.", style="bold red"
            )
            console.print(
                "[bold light_goldenrod2] Eg.'mbodiai/mbpy' [/bold light_goldenrod2] will search for a local path first then a valid github repo. Skipping...",
                style="bold red",
            )
        processed_packages.append(package)
    packages = processed_packages

    try:
        installed_packages = []
        if requirements:
            requirements_file = requirements
            
            package_install_cmd = [sys.executable, "-m", "pip", "install", "-r", requirements_file]
            if upgrade:
                package_install_cmd.append("-U")
            for line in run_command(package_install_cmd,show=False):
                pass
            # Get installed packages from requirements file
            with Path(requirements_file).open() as req_file:
                installed_packages = [line.strip() for line in req_file if line.strip() and not line.startswith("#")]
        
        if packages:
            for package in packages:
                package_install_cmd = [sys.executable, "-m", "pip", "install"]
                if editable:
                    package_install_cmd.append("-e")
                if upgrade:
                    package_install_cmd.append("-U")
                package_install_cmd.append(package)
                lines  = ""
                for line in run_command(package_install_cmd,show=False):
                    if "error" in line.lower() or "failed" in line.lower() or "fatal" in line.lower():
                        console.print(line,style="bold red")
                    elif "warning" in line.lower():
                        console.print(line,style="bold yellow")
                    else:
                        console.print(line)
                    lines += line
                if "error: subprocess-exited-with-error" in lines.lower():
                    console.print(f"Failed to install {package}. Skipping...",style="bold red")
                    continue
                installed_packages.append(package)

        for package in installed_packages:
            package_name, package_version = name_and_version(package, upgrade=upgrade)
            logging.debug(f"installing {package_name} {package_version}")
            modify_pyproject_toml(
                package_name,
                package_version,
                action="install",
                hatch_env=hatch_env,
                dependency_group=dependency_group,
            )

        if not requirements and not packages:
            click.secho("No packages specified for installation.", err=True)

    except FileNotFoundError as e:
        click.secho("Error: Installation failed.", err=True)
    finally:
        logging.info("")


@cli.command("uninstall", no_args_is_help=True)
@click.argument("packages", nargs=-1)
@click.option("--hatch-env", default=None, help="Specify the Hatch environment to use")
@click.option(
    "-g",
    "--dependency-group",
    default="dependencies",
    help="Specify the dependency group to use",
)
@click.option("-d", "--debug", is_flag=True, help="Enable debug logging")
def uninstall_command(packages, hatch_env, dependency_group, debug) -> None:
    """Uninstall packages and update requirements.txt and pyproject.toml accordingly.

    Args:
        packages (tuple): Packages to uninstall.
        hatch_env (str, optional): The Hatch environment to use. Defaults to "default".
        dependency_group (str, optional): The dependency group to use. Defaults to "dependencies".
        debug (bool, optional): Enable debug logging. Defaults to False.
    """
    return _uninstall_command(packages, hatch_env, dependency_group, debug)
def _uninstall_command(packages, hatch_env, dependency_group,*, debug=False) -> None:
    if sys.flags.debug or debug:
        logging.basicConfig(level=logging.DEBUG, force=True)
    for package in packages:
        package_name = base_name(package)

        try:
            modify_requirements(package_name, action="uninstall")
            modify_pyproject_toml(
                package_name,
                action="uninstall",
                hatch_env=hatch_env,
                dependency_group=dependency_group,
                pyproject_path=find_toml_file(),
            )
            print_success = None
            console.print(f"Uninstalling {package_name}...")
            for line in run_command([sys.executable, "-m", "pip", "uninstall", "-y", package_name]):
                click.echo(line, nl=False)
                print_success = partial(click.echo, f"Successfully uninstalled {package_name}")
            print_success() if print_success else None
        except subprocess.CalledProcessError as e:
            click.echo(f"Error: Failed to uninstall {package_name}.", err=True)
            click.echo(f"Reason: {e}", err=True)
            sys.exit(e.returncode)
        except Exception as e:
            click.echo(
                f"Unexpected error occurred while trying to uninstall {package_name}: {e}",
                err=True,
            )
            console.print(Traceback.from_exception(e.__class__, e, e.__traceback__))



@cli.command("show", no_args_is_help=False)
@click.argument("package", default=" ")
@click.option("--hatch-env", default=None, help="Specify the Hatch environment to use")
@click.option("-d", "--debug", is_flag=True, help="Enable debug logging")
def show_command(package:str | None =None, hatch_env=None, debug: bool = False) -> None:
    """Show the dependencies from the pyproject.toml file.

    Args:
        package (str, optional): The package to show information about. Defaults to None.
        hatch_env (str, optional): The Hatch environment to use. Defaults to "default".
    """
    if sys.flags.debug or debug:
        logging.basicConfig(level=logging.DEBUG, force=True)
    if package is not None and package.strip():
        try:
            run_command([sys.executable, "-m", "pip", "show", package or "mbpy"], show=False).readlines(show=False)
        except Exception:
            traceback.print_exc()
    toml_path = find_toml_file()
    try:
        with Path(toml_path).open() as f:
            content = f.read()
            pyproject = tomlkit.parse(content)

        # Determine if we are using Hatch or defaulting to project dependencies
        if "tool" in pyproject and "hatch" in pyproject["tool"] and hatch_env is not None:
            dependencies = (
                pyproject.get("tool", {}).get("hatch", {}).get("envs", {}).get(hatch_env, {}).get("dependencies", [])
            )
        else:
            dependencies = pyproject.get("project", {}).get("dependencies", [])

        if dependencies:
            from rich.table import Table
            from rich.text import Text
            table = Table(title=Text("\nDependencies", style="bold cyan"))
            table.add_column("Package", style="cyan")
            for dep in dependencies:
                table.add_row(dep)
            console.print(table)
        else:
            click.secho("No dependencies found.",styles=["bold"])
    except FileNotFoundError:
        click.secho("Error: pyproject.toml file not found.", err=True)
    except Exception as e:
        click.secho(f"An error occurred: {str(e)}", err=True)



SEARCH_DOC = """Find a package on PyPI and optionally sort the results.\n

    Args:\n
        package (str): The package to search for.
        limit (int, optional): Limit the number of results. Defaults to 5.
        sort (str, optional): Sort key to use. Defaults to "downloads".
        include (str, optional): Include pre-release versions. Defaults to None.
        release (str, optional): Release type to use. Defaults to None.
        full list of options:
    """  # noqa: D205


@cli.command("search", no_args_is_help=True)
@click.argument("package", type=str, nargs=-1)
@click.option("--limit", default=10, help="Limit the number of results")
@click.option("--sort", default="downloads", help="Sort key to use")
@click.option("-i","--include", multiple=True,type=click.Choice(["all"]+INFO_KEYS+ADDITONAL_KEYS), default=None, help="Include additional information")
@click.option("--release", default=None, help="Release version to use")
@click.option("-d", "--debug", is_flag=True, help="Enable debug logging")
def search_command(package, limit, sort, include, release, debug) -> None:
    """Find a package on PyPI and optionally sort the results.
    
    Args:
        package (str): The package to search for.s
        limit (int, optional): Limit the number of results. Defaults to 5.
        sort (str, optional): Sort key to use. Defaults to "downloads".
        include (str, optional): Include pre-release versions. Defaults to None.
        release (str, optional): Release type to use. Defaults to None.
        debug (bool, optional): Enable debug logging. Defaults to False.
    """
    if not isinstance(package, str):
        package = " ".join(package)
    if debug:
        logging.basicConfig(level=logging.DEBUG, force=True)
    try:
        packages = find_and_sort(package, limit=limit, sort=sort, include=include, release=release)

        md = Markdown(packages)
        md.stream()
    except Exception:
        traceback.print_exc()


@cli.command("info", no_args_is_help=True)
@click.argument("package")
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
def info_command(package, verbose) -> None:
    """Get information about a package from PyPI.

    Args:
        package (str): The package to get information about.
        verbose (bool, optional): Show detailed output. Defaults to False.
    """
    try:
        package_info = get_package_info(package, verbose)
        md = Markdown(package_info)
        md.stream()
    except Exception:
        traceback.print_exc()


@cli.command("create", no_args_is_help=True)
@click.argument("project_name")
@click.argument("author")
@click.option("--description", default="", help="Project description")
@click.option("--deps", default=None, help="Dependencies separated by commas")
@click.option("--python", default="3.11", help="Python version to use")
@click.option("--no-cli", is_flag=True, help="Do not add a CLI")
@click.option("--doc-type", type=click.Choice(["sphinx", "mkdocs"]), default="sphinx", help="Documentation type to use")
def create_command(project_name, author, description, deps, python="3.11", no_cli=False, doc_type="sphinx") -> None:
    """Create a new Python project. Optionally add dependencies and a CLI."""
    python_version = python
    try:
        if deps:
            deps = deps.split(",")
        create_project(project_name=project_name, author=author, description=description, python_version=python_version,
                          dependencies=deps, add_cli=not no_cli, doc_type=doc_type)
        click.secho(f"Project {project_name} created successfully with {doc_type} documentation.", fg="green")
    except Exception:
        traceback.print_exc()

@cli.command("sync", no_args_is_help=True)
@click.argument("docs", type=click.Path(exists=True), nargs=-1)
@click.option("--provider", "-p",type=click.Choice(["github","notion","slack"]),default="github", help="The provider to use.")
@click.option("--token", default=None, help="API token")
@click.option("--endpoint", default=None, help="URL Endpoint for documentation destination i..e. Notion table URL")
def sync_notion_command(package, token, table) -> None:
    """Sync a package's data to a Notion table."""
    try:
        append_notion_table_row(package, token, table)
    except Exception:
        traceback.print_exc()

@cli.command("bump", no_args_is_help=True)
def bump_command() -> None:
    """Bump the version of a package."""
    try:
        bump_pkg()
    except Exception:
        traceback.print_exc()

@cli.command("publish", no_args_is_help=True)
@click.option("--bump", "-b", is_flag=True, help="Bump the version before publishing")
@click.option("--build", "-B", is_flag=True, help="Build the package before publishing")
@click.option(
    "--package-manager",
    "-p",
    type=click.Choice(
        [
            "github",
            "hatch",
            "uv",
        ]
    ),
    default="github",
    help="Package manager to use",
)
@click.option(
    "--auth",
    "-a",
    help="PyPI or GitHub authentication token. Defaults to PYPI_TOKEN or GIT_TOKEN environment variable.",
)
@click.option("--gh-release", is_flag=True, help="Create a GitHub release")
def publish_command(bump=False, build=False, package_manager="github", auth=None, gh_release=False) -> None:
    r"""Publish a package to PyPI or GitHub.

    Note: Git features require the GitHub CLI to be installed. See https://cli.github.com/ for more information.
    """
    if not run("which gh", show=False) and (package_manager == "github" or gh_release):
        platform_install_cmd = "`brew install gh`" if run("which brew") else "`sudo snap install gh --classic`"
        console.print(f"GitHub CLI not found. Please install it to use this feature by running {platform_install_cmd}.",style="bold red")
        return
    if not auth:
        auth = os.getenv("GIT_TOKEN") if package_manager == "github" else os.getenv("PYPI_TOKEN")
    version = None
    try:
        if bump:
            version = bump_pkg()
        if build:
            run(["rm", "-rf", "dist"], show=False)
            out = run([package_manager, "build"], show=True)
        if package_manager == "github":
            out = interact(["gh", "pr", "create", "--fill"], show=True)
            outs = ""
            for o in out:
                outs += o
                if "error" in o.lower():
                    console.print("Error occurred while creating pull request.", style="bold red")
                    return
            return
            out = outs or "Pull request created successfully."
        elif package_manager == "uv":
            out = run(["twine", "upload", "dist/*", "-u", "__token__", "-p", auth], show=True)
        elif package_manager == "hatch":
            out = run(["hatch", "publish", "-u", "__token__", "-a", auth], show=True)
        else:
            console.print("Invalid package manager specified.", style="bold red")
        
        if "error" in out[-1].lower():
            console.print("Error occurred while publishing package.", style="bold red")
        else:
            console.print(
                f"Package published successfully with {('version ' + version) if version else 'current version.'}",
                style="bold light_goldenrod2",
            )

        if gh_release:
            out = run(["gh", "release", "create", version], show=True)
        if "error" in out[-1].lower():
            console.print("Error occurred while creating release.", style="bold red")
        else:
            console.print(f"Release created successfully for version {version}.", style="bold light_goldenrod2")
       
    except Exception:
        traceback.print_exc()

@cli.command("add", no_args_is_help=True)
@click.argument("package", nargs=-1)
@click.option("--dev", is_flag=True, help="Add as a development dependency")
@click.option("-e", "--editable", is_flag=True, help="Add as an optional dependency")
@click.option("--hatch-env", default=None, help="Specify the Hatch environment to use")
@click.option("-g", "--group", default=None, help="Specify the dependency group to use")
@click.option("-U", "--upgrade", is_flag=True, help="Upgrade the package(s)")
def add_command(package, dev, editable, hatch_env, group, upgrade) -> None:
    """Add a package to the dependencies in pyproject.toml."""
    if dev and group:
        if group != "dev":
            msg = "Cannot specify both --dev and --group"
            raise click.UsageError(msg)
        group = None
    if "not found" not in run("which uv").lower():
        command = "uv add "
        command += "--upgrade " if upgrade else ""
        command += " --dev " if dev else ""
        command += " --optional " + group if group else ""
        command += " --editable " if editable else ""
        command += " " + " ".join(package)
        run(command, show=True)
    else:
        _install_command([package], None, upgrade, editable, hatch_env, group, False)

@cli.command("remove", no_args_is_help=True)
@click.argument("package", nargs=-1)
@click.option("--dev", is_flag=True, help="Remove as a development dependency")
@click.option("-e", "--editable", is_flag=True, help="Remove as an optional dependency")
@click.option("--hatch-env", default=None, help="Specify the Hatch environment to use")
@click.option("-g", "--group", default=None, help="Specify the dependency group to use")
def remove_command(package, dev, editable, hatch_env, group) -> None:
    """Remove a package from the project using uv or pip."""
    if dev and group:
        if group != "dev":
            msg = "Cannot specify both --dev and --group"
            raise click.UsageError(msg)
        group = None
    if run("which uv"):
        command = "uv remove "
        command += " --dev " if dev else ""
        command += " --optional " + group if group else ""
        command += " --editable " if editable else ""
        command += " ".join(package)
        run(command, show=True)
    else:
        _uninstall_command([package], hatch_env, group, False)

@cli.command("run", no_args_is_help=True, context_settings={"ignore_unknown_options": True})
@click.argument("command", nargs=-1)
def run_cli_command(command) -> None:
    """Run a command."""
    from mbpy.commands import run
    try:
        run(command,show=True)
    except Exception:
        traceback.print_exc()

@cli.command("docs", no_args_is_help=True)
@click.argument("source", type=click.Path(exists=True))
@click.argument("name", type=str)
@click.argument("author", type=str)
@click.option("--description", default="", help="Project description")
@click.option("--kind", type=click.Choice(["sphinx", "mkdocs"]), default="sphinx", help="Documentation type to use")
def docs_command(source,name,author,description,kind) -> None:
    from mbpy.create import setup_documentation
    try:
        setup_documentation(source, name, author, description, kind)
    except Exception:
        traceback.print_exc()


@cli.command("graph", no_args_is_help=True)
@click.argument("path", default=".")
@click.option("--sigs", is_flag=True, help="Include function and method signatures")
@click.option("--docs", is_flag=True, help="Include docstrings in the output")
@click.option("--code", is_flag=True, help="Include source code of modules in the output")
@click.option("--who-imports", is_flag=True, help="Include modules that import each module")
@click.option("--stats", is_flag=True, help="Include statistics and flow information")
@click.option("--site-packages", is_flag=True, help="Include site-packages and vendor directories")
def graph_command(path, sigs, docs, code, who_imports, stats, site_packages) -> None:
    """Generate a dependency graph of a Python project."""
    from mbpy.graph import generate as generate_report
    try:
        generate_report(path, sigs, docs, code, who_imports, stats, site_packages)
    except Exception:
        traceback.print_exc()

@cli.command("who-imports")
@click.argument("module_name")
@click.argument("path", default=".")
@click.option("--site-packages", is_flag=True, help="Include site-packages and vendor directories")
def who_imports_command(module_name, path, site_packages) -> None:
    """Find modules that import a given module."""
    from mbpy.graph import who_imports
    try:
        who_imports(module_name, path, site_packages)
    except Exception:
        traceback.print_exc()

@cli.command("repair", no_args_is_help=True)
@click.argument("path", default=".")
@click.option("-d","--dry-run", is_flag=True, help="Dry run")
def repair_command(path, dry_run) -> None:
    """Repair broken imports."""
    from mbpy.repair import main
    try:
        main(path, dry_run)
    except Exception:
        traceback.print_exc()

def main() -> None:
    cli()
if __name__ == "__main__":
    main()
