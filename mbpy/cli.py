import asyncio
import json
import logging
import logging.handlers
import os
import re
import subprocess
import sys
import traceback
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, AsyncGenerator, AsyncIterator, Literal, Sequence

import rich_click as click
import tomlkit
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from pydantic import AnyUrl
from rich.console import Console
from rich.pretty import pprint
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text
from rich.traceback import Traceback

from mbpy import SPINNER, context, isverbose
from mbpy.bump import bump as bump_pkg
from mbpy.commands import arun, arun_command, interact, run, run_command
from mbpy.create import create_project, find_readme, setup_documentation
from mbpy.mpip import (
    ADDITONAL_KEYS,
    INFO_KEYS,
    PackageInfo,
    find_and_sort,
    find_toml_file,
    format_pkg,
    get_package_info,
    get_requirements_packages,
    getbase,
    modify_pyproject_toml,
    modify_requirements,
)
from mbpy.repair import main as repair_main
from mbpy.utils._env import get_executable
from mbpy.utils.collect import PathLike, PathType, compose, first
from mbpy.uv import uv
from mbpy.workflow.notion import append_notion_table_row
from mrender.md import Markdown

logger = logging.getLogger()


console = Console()
today = datetime.today

# Helper function to run asynchronous coroutines
def run_async(coro):
    """Run an asynchronous coroutine within an existing event loop or create a new one."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # If an event loop is already running, create a new task
        return asyncio.create_task(coro)
    else:
        # If no loop is running, create a new one and run the coroutine
        return asyncio.run(coro)
# Custom Click Group to handle asynchronous commands
class AsyncGroup(click.RichGroup):
    """Custom Click Group that supports asynchronous command callbacks."""

    def invoke(self, ctx: click.Context) -> Any:
        """Override the invoke method to handle async commands."""
        coro = super().invoke(ctx)
        if asyncio.iscoroutine(coro):
            return run_async(coro)
        return coro

    def __call__(self, *args, **kwargs):
        """Override call to support asynchronous invocation."""
        return super().__call__(*args, **kwargs)


# TODO add a timeout option and support windows.
@click.group("mb",cls=AsyncGroup)
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
def cli(ctx: click.RichContext, env, debug) -> None:
    # if isverbose():
    #     logging.basicConfig(level=logging.DEBUG, force=True)
    if ctx.invoked_subcommand:
        # await asyncio.to_thread(ctx.command,ctx.params)
        pass
    else:
        pass
        # run_async(_show_command(None, env=env, debug=debug))



# cli.add_command(uv)
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
@click.option("--env", default=None, help="Specify the python, hatch, conda, or mbnix environment")
@click.option(
    "-g",
    "--group",
    default="dependencies",
    help="Specify the dependency group to use",
)
@click.option("-d", "--debug", is_flag=True, help="Enable debug logging")
@click.option(
    "-b", "--broken", type=click.Choice(["skip", "ask", "repair"]), default="skip", help="Behavior for broken packages"
)
def install_command(
    packages,
    requirements,
    upgrade,
    editable,
    env,
    group,
    *,
    debug=False,
    broken: Literal["skip", "ask", "repair"],
) -> None:
    """Install packages and update requirements.txt and pyproject.toml accordingly.

    Args:
        packages (tuple): Packages to install.
        requirements (str, optional): Requirements file to install packages from. Defaults to None.
        upgrade (bool, optional): Upgrade the package(s). Defaults to False.
        editable (bool, optional): Install a package in editable mode. Defaults to False.
        env (str, optional): The Hatch environment to use. Defaults to "default".
        group (str, optional): The dependency group to use. Defaults to "dependencies".
        debug (bool, optional): Enable debug logging. Defaults to False.
        broken (Literal["skip", "ask", "repair"], optional): Behavior for broken packages. Defaults to "skip".
    """
    asyncio.run(_install_command(packages, requirements, upgrade=upgrade, editable=editable, env=env, group=group, debug=debug, broken=broken))

# async def try_repo(repo: str):
#     if "@" in repo:
#         repo = repo.split("@")[0]
#     if repo.startswith("git+"):
#         repo = repo[4:]
#     if not repo.startswith("https"):
#         repo = f"https://github.com/{repo}"
#     repo = repo.split(".com/")[-1]
#     with context.suppress() as e, repo_context(repo) as repo_dir:
#        pyproject_toml =find_toml_file(repo_dir)
#        project_name = tomlkit.parse(Path(pyproject_toml).read_text())["project"]["name"]
       
#     if e:
#         console.print(f"Error: {e}", style="bold red")
#         return False
#     return None



def format_timestamp(timestamp: str) -> str:
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

    return dt.strftime("%B %d, %Y")  # e.g. "November 22, 2024"
    
# async def suggest_similar(package: AnyUrl | str, outs: Sequence[dict[str, str] | PackageInfo]|None=None) -> None:
#     if not outs:
#         outs = await find_and_sort(str(package))
#     if not outs:
#         return
#     console.print("\n")
#     console.print(f"Repository not found: {package}. Did you mean one of these?",style="bold yellow")
#     console.print("\n")
#     table = Table()
#     table.add_column("Name",style="cyan")
#     table.add_column("Updated At",style="cyan")
#     for i,repo in enumerate(outs[:10]):
#         table.add_row(
#             f"[link={repo.get('github_url')}] {repo.get('name')} [/link]",
#             str(format_timestamp(repo.get("latest_release"))),
#         )
#     console.print(table)
#     console.print("\n")

async def check_repo(repo:str,version=None,quiet=True):
    if "==" in repo:
        repo = repo.split("==")[0]
        version = repo.split("==")[1]
    if "@" in repo:
        version = repo.split("@")[1]
        repo = repo.split("@")[0]
    out =  str(await arun(f"gh repo view {repo} --json name {'--branch ' + version if version else ''}",show=not quiet)).lower()
    if "could not resolve to a repository" in out:
        repo = repo.split("/")[-1]
        out: str = str(await arun(f"gh search repos --json name --json updatedAt --json url --json stargazersCount  {repo}",show=False)).lower()
        if not out:
            console.print(f"Repository not found: {repo}",style="bold red")
            return False
        
      
        with context.suppress() as e:
            out = out[out.find("["):out.rfind("]")].strip()
            outs = []
            if e or not out:
                return False
            
            outs = sorted(
                [json.loads(o[o.find("{"):].strip().rstrip("}") + "}") for o in out.split("},") if o and "{" in o],
                key=lambda x: x["updatedat"],
                reverse=True,
            )
            console.print("\n")
            console.print(f"Repository not found: {repo}. Did you mean one of these?",style="bold yellow")
            console.print("\n")
            table = Table()
            table.add_column("Name",style="cyan")
            table.add_column("Updated At",style="cyan")
            table.add_column("Stars",style="cyan")
            for i,repo in enumerate(outs[:10]):
                table.add_row(f"[link={repo['url']}] {repo['name']} [/link]",str(format_timestamp(repo["updatedat"])),str(repo["stargazerscount"]))
            console.print(table)
            console.print(table)
            console.print("\n")
        return False
    if repo.startswith("git+"):
        repo = repo[4:]
    if not repo.startswith("https"):
        repo = f"git+https://github.com/{repo}"
    return repo
    
async def repo_exists(repo, version=None):
    return await check_repo(repo,version)

def uv_error(line) -> bool:
    line = str(line)
    return line.lower().strip().startswith("error") or "failed" in line.lower() or "error" in line.lower() or "fatal" in line.lower() or "ERROR" in line

def build_pip_command(
    executable: str,
    package: str | None = None,
    requirements: bool = False,
    upgrade: bool = False,
    editable: bool = False,
) -> list[str]:
    """Construct pip install command."""
    cmd = [executable, "-m", "pip", "install"]
    if requirements:
        cmd.extend(["-r", package] if package else [])
    else:
        if editable:
            cmd.append("-e")
        if upgrade:
            cmd.append("-U")
        if package:
            cmd.append(package)
    return cmd

async def process_package_path(package: str) -> str | None:
    """Process package path/repo and return valid package spec."""
    if PathLike(package).exists():
        return str(Path(package).resolve())
    if "/" in package:
        if pkg := await repo_exists(package):
            return pkg
        console.print(
            f"\nPackage not found or invalid github repo: {package}.\n"
            "Only local paths or GitHub repos in `org/repo` format are supported.",
            style="bold red",
        )
        console.print(
            "\nFor example, [bold light_goldenrod2]'mbodiai/mb'[/bold light_goldenrod2]"
            " will search for a local path first then a valid github repo.",
            style="bold red",
        )
        return None
    return package

async def handle_install_output(
    output: AsyncIterator[str],
    package: str,
    executable: str,
    broken: str,
) -> tuple[bool, str | None]:
    """Process installation output stream and handle errors."""
    lines = ""
    success = True
    version = None  # Initialize version
    
    # Get initial state
    before = await arun(f"{executable} -m pip freeze", show=False)
    before_pkgs = parse_pip_freeze(before)
    
    async for line in output:
        SPINNER.stop()
        lines += line
        
        if uv_error(line):
            console.print(Text.from_ansi(line))
            if broken == "forbid":
                console.print("Installation failed. Exiting...", style="bold red")
                sys.exit(1)
            if broken == "ask" and Confirm.ask("Would you like to continue?"):
                repair_main(package)
            await suggest_similar(package)
            success = False
            break
            
        console.print(Text.from_ansi(line))
        
        if "Successfully installed" in line:
            # Get final state
            after = await arun(f"{executable} -m pip freeze", show=False)
            after_pkgs = parse_pip_freeze(after)
            
            # Find diff
            for pkg_name, spec in after_pkgs.items():
                if pkg_name not in before_pkgs or before_pkgs[pkg_name] != spec:
                    version = spec
                    return True, version
        
        elif "Requirement already satisfied" in line:
            # Fetch the current version of the package
            version = await get_package_version(package, executable)
            if version:
                return True, version
    
    return success, version

def parse_pip_freeze(output: str) -> dict[str, str]:
    """Parse pip freeze output into package->version/location mapping."""
    packages = {}
    # Pattern to match package specifications with proper boundaries
    pattern = r"""
        (?:
            (?:-e\s+)?                               # Optional editable flag
            git\+[^\s]+?(?:\#egg=[^\s&]+)           # Git URL with egg
            |
            (?:[a-zA-Z0-9][a-zA-Z0-9\-_\.]+?)      # Package name (made greedier)
            ==                                       # Version separator (exact match)
            (?:[0-9][0-9a-zA-Z\-_\.]+)              # Version string (must start with number)
        )
    """
    matches = re.finditer(pattern, output, re.VERBOSE)
    for match in matches:
        line = match.group(0).strip()
        try:
            if line.startswith('-e'):
                # Editable install: -e git+url@commit#egg=package
                egg_part = line.split('#egg=')[-1]
                pkg_name = egg_part.split('&')[0].strip()
                packages[pkg_name] = line
            elif ' @ ' in line:
                # Direct reference: package @ git+url@commit
                pkg_name, location = line.split(' @ ', 1)
                packages[pkg_name.strip()] = location.strip()
            elif '==' in line:
                # Regular package: package==version
                pkg_name, version = line.split('==', 1)
                # Clean any trailing version specs from concatenated output
                version = re.split(r'[a-zA-Z]', version)[0].strip()
                packages[pkg_name.strip()] = version.strip()
            else:
                logger.warning(f"Unknown pip freeze format: {line}")
        except Exception as e:
            logger.error(f"Error parsing pip freeze line '{line}': {e}")
            continue
    return packages

async def install_single_package(
    package: str,
    executable: str,
    upgrade: bool,
    editable: bool,
    broken: str,
) -> tuple[str | None, str | None]:
    """Install a single package."""
    cmd = build_pip_command(executable, package, upgrade=upgrade, editable=editable)
    success, version = await handle_install_output(
        (arun_command(cmd)).astreamlines(show=False),
        package,
        sys.executable,
        broken,
    )
    
    if not success:
        return None, None
        
    # If no version found from pip output, try getting it directly
    if not version:
        version = await get_package_version(package, executable)
        
    return package, version


async def update_pyproject_toml(
    packages: list[str],
    env: str,
    group: str,
) -> None:
    """Update pyproject.toml with installed packages."""
    console.print("Updating pyproject.toml with installed packages...")
    console.print("\n")
    for package in packages:

        console.print(f"Updating pyproject.toml with {package}")
        await modify_pyproject_toml(
                package=package,
                action="install",
                env=env,
                group=group
            )
async def get_package_version(package: str, executable: str) -> str:
    """Extract version from pip show output."""
    try:
        result = await arun(f"{executable} -m pip show {package}", show=False)
        for line in result.splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    except Exception as e:
        logger.error(f"Error getting version for {package}: {e}")
    return ""

async def install_from_requirements(
    *,
    requirements_file: PathType,
    executable: str,
    upgrade: bool,
    broken: str,
) -> tuple[list[str], list[str]]:
    """Install packages from requirements file."""
    cmd = build_pip_command(executable, requirements_file, requirements=True, upgrade=upgrade)
    installed = []
    versions = []
    add_uvcommand()
    if success and version:
        installed.append(getbase(line))
        versions.append(version)
            
    reqs = await get_requirements_packages(requirements_file)
    installed.extend(reqs)
    return installed, versions

async def _install_command(
    packages: str | list[str],
    requirements_file: PathType | None = None,
    *,
    upgrade: bool = False,
    editable: bool = False,
    env: str | None = None,
    group: str | None = "dependencies",
    debug: bool = False,
    broken: Literal["ask", "repair", "skip"] = "skip",
) -> None:
    """Main installation command handler."""
    if sys.flags.debug or debug:
        logging.basicConfig(level=logging.DEBUG, force=True)

    executable = get_executable(env)
    installed_packages = []
    installed_versions = []

    try:
        # Process requirements file if provided
        if requirements_file is not None:
            req_packages, req_versions = await install_from_requirements(
                requirements_file=requirements_file,
                executable=executable,
                editable=editable,
                upgrade=upgrade,
                broken=broken
            )
            installed_packages.extend(req_packages)
            installed_versions.extend(req_versions)

        # Process individual packages
        if packages:
            processed_packages = []
            for package in packages:
                if pkg := await process_package_path(package):
                    processed_packages.append(pkg)

            for package in set(processed_packages):
                cmd = build_pip_command(executable, package, upgrade=upgrade, editable=editable)
                async for line in (arun_command(cmd)).astreamlines(show=False):
                    console.print(Text.from_ansi(line))
                lines =run(f"{executable} -m pip freeze", show=False).splitlines()
                logging.debug(f"Lines: {[(line,package) for line in lines]}")
                matched_line = first(lambda line: package.strip() in line, lines)
                
                if matched_line:
                    installed_packages.append(format_pkg(matched_line))
                else:
                    console.print(f"Error: Failed to install {package}.", style="bold red")
                    await suggest_similar(package)
                    continue
        # Update pyproject.toml if there are any installed packages
        if installed_packages:
            await update_pyproject_toml(installed_packages, env, group)
            console.print("pyproject.toml updated successfully.", style="bold green")
        else:
            console.print("No packages to install or update.", style="bold yellow")

    except FileNotFoundError as e:
        console.print(f"Error: {e}", style="bold red")
    except Exception as e:
        traceback.print_exc()
        console.print(f"Unexpected error: {e}", style="bold red")
        if debug:
            raise

@cli.command("uninstall", no_args_is_help=True)
@click.argument("packages", nargs=-1)
@click.option("--env", default=None, help="Specify the Hatch environment to use")
@click.option(
    "-g",
    "--group",
    default="dependencies",
    help="Specify the dependency group to use",
)
@click.option("-d", "--debug", is_flag=True, help="Enable debug logging")
def uninstall_command(packages, env, group, debug) -> None:
    """Uninstall packages and update requirements.txt and pyproject.toml accordingly.

    Args:
        packages (tuple): Packages to uninstall.
        env (str, optional): The Hatch environment to use. Defaults to "default".
        group (str, optional): The dependency group to use. Defaults to "dependencies".
        debug (bool, optional): Enable debug logging. Defaults to False.
    """
    return  asyncio.run(_uninstall_command(packages, env, group, debug=debug))


async def _uninstall_command(packages, env, group, *, debug=False) -> None:
    if sys.flags.debug or debug:
        logging.basicConfig(level=logging.DEBUG, force=True)
    for package in packages:
        package_name = getbase(package)

        try:
            await modify_requirements(package_name, action="uninstall")
            await modify_pyproject_toml(
                package=package_name,
                action="uninstall",
                env=env,
                group=group,
                pyproject_path=await find_toml_file(),
            )
            print_success = None
            console.print(f"Uninstalling {package_name}...")
            warning = False
            async for line in (arun_command([get_executable(env) or "python3", "-m", "pip", "uninstall", "-y", package_name])):
                console.print(Text.from_ansi(line), end="")
                if "WARNING" in line or "warning" in line.lower() or "error" in line.lower():
                    warning = True
                print_success = partial(compose(console.print, Text.from_ansi), f"\nSuccessfully uninstalled {package_name}") if not "WARNING" in line else None
            print_success() if print_success and not warning else None
        except subprocess.CalledProcessError as e:
            console.print(f"Error: Failed to uninstall {package_name}.", style="bold red")
            console.print(f"Error: {e}")
            sys.exit(e.returncode)
        except Exception as e:
            console.print(f"Error: Failed to uninstall {package_name}.", style="bold red")
            logging.exception(Traceback.from_exception(e.__class__, e, e.__traceback__))


@cli.command("show", no_args_is_help=False)
@click.argument("package", default=" ")
@click.option("--env", default=None, help="Specify a python, hatch, conda, or mbnix environment")
@click.option("-d", "--debug", is_flag=True, help="Enable debug logging")
def show_command(package=None, env=None, debug=False) -> None:
    """Show the dependencies from the pyproject.toml file.

    Args:
        package (str, optional): The package to show information about. Defaults to None.
        env (str, optional): The Hatch environment to use. Defaults to "default".
        debug (bool, optional): Enable debug logging. Defaults to False.
    """
    console.print(f"ay ")
    return
    _show_command(package, env=env, debug=debug)


def _show_command(package: str | None = None, *, env=None, debug: bool = False) -> None:
    """Show the dependencies from the pyproject.toml file.

    Args:
        package (str, optional): The package to show information about. Defaults to None.
        env (bool, optional): Whether to show the environment. Defaults to None.
        debug (bool, optional): Enable debug logging. Defaults to False.
    """
    run(f"{sys.executable} -m pip list", show=True)
    exit()
    # if sys.flags.debug or debug:
    #     logging.basicConfig(level=logging.DEBUG, force=True)
    # if env:
    #     pprint(os.environ)
    # if package is not None and package.strip():
    #     try:
    #         run(f"{sys.executable} -m pip show {package}", show=True)
    #         return
    #     except Exception:
    #         traceback.print_exc()
    # toml_path = await find_toml_file()
    # try:

    #     content = Path(toml_path).read_text()
    #     pyproject = tomlkit.parse(content)


    #     async for line in arun_command(f"{get_executable(env)} -m pip list").astreamlines(show=False):
    #         console.print(Text.from_ansi(line))
    #     logging.debug("Finished lines")
    #     # Determine if we are using Hatch or defaulting to project dependencies
    #     if env is not None and "tool" in pyproject and "hatch" in pyproject.get("tool", {}):
    #         dependencies = (
    #             pyproject.get("tool", {}).get("hatch", {}).get("envs", {}).get(env, {}).get("dependencies", [])
    #         )
    #     else:
    #         dependencies = pyproject.get("project", {}).get("dependencies", [])

    #     if dependencies:
    #         table = Table(title=Text("Dependencies for project:", style="bold cyan"))
    #         table.add_column("Package", style="cyan")
    #         for dep in dependencies:
    #             table.add_row(dep)
    #         console.print(table)
    #     else:
    #         console.print("No dependencies found.", style="bold yellow")
    # except FileNotFoundError:
    #     console.print("No pyproject.toml file found.", style="bold red")
    # except Exception as e:
    #     console.print(f"Error: {e}", style="bold red")


@cli.command("search", no_args_is_help=True)
@click.argument("package", type=str, nargs=-1)
@click.option("--limit", default=10, help="Limit the number of results")
@click.option("--sort", default="downloads", help="Sort key to use")
@click.option(
    "-i",
    "--include",
    multiple=True,
    # type=click.Choice(["all"] + INFO_KEYS + ADDITONAL_KEYS),
    default=None,
    help="Include additional information",
)
@click.option("--release", default=None, help="Release version to use")
@click.option("-d", "--debug", is_flag=True, help="Enable debug logging")
async def search_command(package, limit, sort, include, release, debug) -> None:
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
        packages = await find_and_sort(package, limit=limit, sort=sort, include=include, release=release)

        md = Markdown(packages)
        if debug:
            logging.debug(packages)
        SPINNER.stop()
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
        package_info = asyncio.run(get_package_info(package, verbose))
        md = Markdown(package_info)
        SPINNER.stop()
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
@click.option("--autodoc", type=click.Choice(["sphinx", "mkdocs"]), default="sphinx", help="Documentation type to use")
def create_command(project_name, author, description, deps, python="3.11", no_cli=False, autodoc="sphinx") -> None:
    """Create a new Python project. Optionally add dependencies and a CLI."""
    python_version = python
    try:
        if deps:
            deps = deps.split(",")
        asyncio.run(create_project(
            project_name=project_name,
            author=author,
            description=description,
            python_version=python_version,
            dependencies=deps,
            add_cli=not no_cli,
            autodoc=autodoc,
        ))
        console.print(f"Project {project_name} created successfully.", style="bold light_goldenrod2")   
    except Exception:
        traceback.print_exc()


@cli.command("sync", no_args_is_help=True)
@click.argument("docs", type=click.Path(exists=True), nargs=-1)
@click.option(
    "--provider", "-p", type=click.Choice(["github", "notion", "slack"]), default="github", help="The provider to use."
)
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
            "gh",
            "hatch",
            "uv",
            "nix",
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
        console.print(
            f"GitHub CLI not found. Please install it to use this feature by running {platform_install_cmd}.",
            style="bold red",
        )
        return
    if not auth:
        auth = os.getenv("GIT_TOKEN") if package_manager == "github" else os.getenv("PYPI_TOKEN")
    version = None
    try:
        if bump:
            version = bump_pkg()
        out = ""
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
            out = run(
                ["gh", "release", "create", version or f"{today().strftime('%d-%m-%Y')}"],
                show=True,
            )
        if "error" in out[-1].lower():
            console.print("Error occurred while creating release.", style="bold red")
        else:
            console.print(f"Release created successfully for version {version}.", style="bold light_goldenrod2")

    except Exception:
        traceback.print_exc()


@cli.command("add", no_args_is_help=True)
@click.argument("packages", nargs=-1)
@click.option("--dev", is_flag=True, help="Add as a development dependency")
@click.option("-e", "--editable", is_flag=True, help="Add as an optional dependency")
@click.option("--env", default=None, help="Specify the Hatch, Conda, or mbnix environment to use")
@click.option("-g", "--group", default=None, help="Specify the dependency group to use")
@click.option("-U", "--upgrade", is_flag=True, help="Upgrade the package(s)")
@click.option("-r","--requirements", type=click.Path(exists=True), help="Requirements file to install packages from")
@click.option("-b", "--broken", type=click.Choice(["skip", "ask", "repair"]), default="skip", help="Behavior for broken packages")
@click.option("-d", "--debug", is_flag=True, help="Enable debug logging")
async def add_uvcommand(
    packages: tuple[str, ...],
    dev: bool,
    editable: bool,
    env: str | None,
    group: str | None,
    upgrade: bool,
    requirements: str | None,
    broken: Literal["skip", "ask", "repair"],
    debug: bool,
) -> None:
    """Add a package to the dependencies in pyproject.toml.

    Args:
        package (tuple[str, ...]): Packages to add.
        dev (bool): Add as a development dependency.
        editable (bool): Add as an optional dependency.
        env (str | None): Specify the Hatch, Conda, or mbnix environment to use.
        group (str | None): Specify the dependency group to use.
        upgrade (bool): Upgrade the package(s).
        requirements (str | None): Requirements file to install packages from.
        broken (Literal["skip", "ask", "repair"]): Behavior for broken packages.
        debug (bool): Enable debug logging.
    """
    if dev and group:
        if group != "dev":
            msg = "Cannot specify both --dev and --group"
            raise click.UsageError(msg)
        group = None
    if requirements and not Path(requirements).exists():
        console.print(f"Requirements file {requirements} does not exist.", style="bold red")
        return
    if requirements and packages:
        console.print("Cannot specify both packages and a requirements file.", style="bold red")
        return
    if run("which uv"):
        command = "uv add "
        command += " --dev " if dev else ""
        command += " --optional " + group if group else ""
        command += "  --editable " if editable else ""
        command += " --upgrade " if upgrade else ""
        command += " -r " + requirements if requirements else ""
        command += " ".join(packages) if packages else ""
        for line in run_command(command, show=False).streamlines():
            if "error" in line.lower() or "warning" in line.lower() or "failed" in line.lower():
                return asyncio.run(_uninstall_command(packages, env, group, debug=debug))
        
            console.print(Text.from_ansi(line))

    return await _install_command(packages, env, group=group, upgrade=upgrade, editable=editable, broken=broken, debug=debug)


@cli.command("conan", no_args_is_help=True)
@click.argument("packages", nargs=-1)
@click.option("--env", default=None, help="Specify the python, hatch, conda, or mbnix environment")
@click.option("-g", "--group", default=None, help="Specify the dependency group to use")
@click.option("-d", "--debug", is_flag=True, help="Enable debug logging")
def conan_install_command(packages, env, group, debug) -> None:
    """Install packages using Conan."""
    if not run("which conan"):
        console.print("Conan is not installed. Please install with  `pip install \"mb[conan]\"`", style="bold red")
        return
    asyncio.run(_conan_cmd(packages, env=env, group=group, debug=debug))
    
async def _conan_cmd(packages, env, group, debug) -> None:
    """Install packages using Conan."""
    if sys.flags.debug or debug:
        logging.basicConfig(level=logging.DEBUG, force=True)
    for package in packages:
        try:
            await arun(f"conan install {package}", show=True)
        except Exception as e:
            console.print(f"Error: {e}", style="bold red")
            if debug:
                raise
@cli.command("remove", no_args_is_help=True)
@click.argument("packages", nargs=-1)
@click.option("--dev", is_flag=True, help="Remove as a development dependency")
@click.option("--env", default=None, help="Specify the python, hatch, conda, or mbnix environment")
@click.option("-g", "--group", default=None, help="Specify the dependency group to use")
@click.option("-d", "--debug", is_flag=True, help="Enable debug logging")
def remove_command(packages, dev, env, group, debug) -> None:
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
        command += " ".join(packages)
        for line in run_command(command, show=False).streamlines():
            if "error" in line.lower() or "warning" in line.lower() or "failed" in line.lower():
                return asyncio.run(_uninstall_command(packages, env, group, debug=debug))
        
            console.print(Text.from_ansi(line))

    return asyncio.run(_uninstall_command(packages, env, group, debug=debug))


@cli.command("run", no_args_is_help=True, context_settings={"ignore_unknown_options": True})
@click.argument("command", nargs=-1)
def run_cli_command(command: str) -> None:
    """Run a command."""
    try:
        run(command,show=True)
    except Exception:
        traceback.print_exc()


@cli.command("docs", no_args_is_help=True)
@click.argument("name", type=str)
@click.argument("author", type=str)
@click.option(
    "--readme", default="", help="Project README.md to convert to documentation. If all, consider all .md files."
)
@click.option("--kind", type=click.Choice(["sphinx", "mkdocs"]), default="sphinx", help="Documentation type to use")
async def docs_command(name: str, author: str, readme: str | None, kind: str) -> None:
    readme = str(readme)

    try:
        await setup_documentation(project_name=name, author=author, description=readme or str(find_readme()), autodoc=kind)
    except Exception:
        traceback.print_exc()
        click.secho("Error: Failed to setup documentation.", err=True)


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
    from mb.graph import generate as generate_report

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
    from mb.graph import who_imports

    try:
        who_imports(module_name, path, site_packages=site_packages)
    except Exception:
        traceback.print_exc()


@cli.command("repair", no_args_is_help=True)
@click.argument("path", default=".")
@click.option("-d", "--dry-run", is_flag=True, help="Dry run")
def repair_command(path, dry_run) -> None:
    """Repair broken imports."""
    try:
        repair_main(path, dry_run)
    except Exception:
        traceback.print_exc()



    
def main():
    cli()
    # asyncio.run(cli())


if __name__ == "__main__":
    main()
