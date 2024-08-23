import subprocess
import sys
import traceback
from pathlib import Path

import click
import tomlkit
from mrender.md import Markdown
from rich import print
from rich.traceback import Traceback

from mbpy.create import create_project
from mbpy.mpip import (
    find_and_sort,
    get_package_info,
    get_requirements_packages,
    modify_pyproject_toml,
    modify_requirements,
    name_and_version,
)


@click.group(invoke_without_command=True)
@click.pass_context
@click.option(
    "-v",
    "--hatch-env",
    default=None,
    help="Specify the Hatch environment to use",
)
def cli(ctx, hatch_env) -> None:
    if ctx.invoked_subcommand is None:
        click.echo("No subcommand specified. Showing dependencies:")
        show_command(hatch_env)


@cli.command("install")
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
def install_command(
    packages,
    requirements,
    upgrade,
    editable,
    hatch_env,
    dependency_group,
) -> None:
    """Install packages and update requirements.txt and pyproject.toml accordingly.

    Args:
        packages (tuple): Packages to install.
        requirements (str, optional): Path to requirements file. If provided, install packages from this file.
        upgrade (bool, optional): Whether to upgrade the packages. Defaults to False.
        editable (bool, optional): Whether to install a package in editable mode. Defaults to False.
        hatch_env (str, optional): The Hatch environment to use. Defaults to "default".
        dependency_group (str, optional): The dependency group to use. Defaults to "dependencies".
    """
    try:
        if requirements:
            requirements_file = requirements
            if not Path(requirements_file).exists():
                click.echo(f"Requirements file {requirements_file} not found.")
                return
            
            click.echo(f"Installing packages from {requirements_file}...")
            package_install_cmd = [sys.executable, "-m", "pip", "install", "-r", requirements_file]
            if upgrade:
                package_install_cmd.append("-U")
            click.echo(f"Running command: {' '.join(package_install_cmd)}")
            try:
                process = subprocess.Popen(package_install_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                stdout, stderr = process.communicate(timeout=300)  # 5 minutes timeout
                click.echo(stdout)
                if stderr:
                    click.echo(stderr, err=True)
                if process.returncode != 0:
                    if "HINT: You are attempting to install a package literally named \"requirements.txt\"" in stdout:
                        click.echo("Error: The requirements.txt file contains an invalid entry 'requirements.txt'.")
                        click.echo("Please remove this line from your requirements.txt file and try again.")
                    else:
                        click.echo(f"Error: Installation failed with return code {process.returncode}", err=True)
                    sys.exit(process.returncode)
                if "ERROR: pip's dependency resolver does not currently take into account all the packages that are installed." in stdout:
                    click.secho("Warning: " + stdout.split("ERROR: ")[1], fg="yellow")
                if "A new release of pip is available" in stdout:
                    for line in stdout.splitlines():
                        if line.startswith("[notice]"):
                            click.echo(line)
            except subprocess.TimeoutExpired:
                click.echo("Error: Installation process timed out after 5 minutes.")
                process.kill()
                sys.exit(1)
            return

        packages = set(packages) if packages else set()
        if not packages:
            click.echo("No packages specified for installation.")
            return

        for package in packages:
            package_install_cmd = [sys.executable, "-m", "pip", "install"]
            if editable:
                package_install_cmd.append("-e")
            if upgrade:
                package_install_cmd.append("-U")
            package_install_cmd.append(package)
            stdout, stderr = subprocess.Popen(package_install_cmd, stdout=subprocess.PIPE,
                                                stderr=subprocess.PIPE,
                text=True).communicate()

            package_name, package_version = name_and_version(package, upgrade=upgrade)
            modify_pyproject_toml(
                package,
                package_version,
                action="install",
                hatch_env=hatch_env,
                dependency_group=dependency_group,
            )
            click.echo(stdout)
            click.echo(stderr, err=True)
            modify_requirements(package_name, package_version, action="install", requirements=requirements)


    except subprocess.CalledProcessError as e:
        color_code = "\033[91m"
        click.echo(f"{color_code}Error: Failed to install {package}.", err=True)
        click.echo(f"{color_code}Reason: {e}")
        sys.exit(e.returncode)


@cli.command("uninstall")
@click.argument("packages", nargs=-1)
@click.option("--hatch-env", default=None, help="Specify the Hatch environment to use")
@click.option(
    "-g",
    "--dependency-group",
    default="dependencies",
    help="Specify the dependency group to use",
)
def uninstall_command(packages, hatch_env, dependency_group) -> None:
    """Uninstall packages and update requirements.txt and pyproject.toml accordingly.

    Args:
        packages (tuple): Packages to uninstall.
        hatch_env (str, optional): The Hatch environment to use. Defaults to "default".
        dependency_group (str, optional): The dependency group to use. Defaults to "dependencies".
    """
    for package in packages:
        package_name = package.split("==")[0].split("[")[0]  # Handle extras

        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "uninstall", package_name, "-y"],
            )
            modify_requirements(package_name, action="uninstall")
            modify_pyproject_toml(
                package_name,
                action="uninstall",
                hatch_env=hatch_env,
                dependency_group=dependency_group,
            )
            click.echo(f"Successfully uninstalled {package_name}")
        except subprocess.CalledProcessError as e:
            click.echo(f"Error: Failed to uninstall {package_name}.", err=True)
            click.echo(f"Reason: {e}", err=True)
            sys.exit(e.returncode)
        except Exception as e:
            click.echo(
                f"Unexpected error occurred while trying to uninstall {package_name}:",
                err=True,
            )
            print(Traceback.from_exception(e))
            sys.exit(1)


@cli.command("show")
@click.option("--hatch-env", default=None, help="Specify the Hatch environment to use")
def show_command(hatch_env) -> None:
    """Show the dependencies from the pyproject.toml file.

    Args:
        hatch_env (str, optional): The Hatch environment to use. Defaults to "default".
    """
    try:
        with Path("pyproject.toml").open() as f:
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
            click.echo("Dependencies:")
            for dep in dependencies:
                click.echo(f"  {dep}")
        else:
            click.echo("No dependencies found.")
    except FileNotFoundError:
        click.echo("Error: pyproject.toml file not found.")
    except Exception as e:
        click.echo(f"An error occurred: {str(e)}")


@cli.command("find")
@click.argument("package")
@click.option("--limit", default=5, help="Limit the number of results")
@click.option("--sort", default="downloads", help="Sort key to use")
def find_command(package, limit, sort) -> None:
    """Find a package on PyPI and optionally sort the results.

    Args:
        package (str): The package to search for.
        limit (int, optional): Limit the number of results. Defaults to 5.
        sort (str, optional): Sort key to use. Defaults to "downloads".
    """
    try:
        packages = find_and_sort(package, limit, sort)
        md = Markdown(packages)
        md.stream()
    except Exception as e:
        traceback.print_exc()

@cli.command("search") # Alias for find
@click.argument("package")
@click.option("--limit", default=10, help="Limit the number of results")
@click.option("--sort", default="downloads", help="Sort key to use")
def search_command(package, limit, sort) -> None:
    """Find a package on PyPI and optionally sort the results.

    Args:
        package (str): The package to search for.
        limit (int, optional): Limit the number of results. Defaults to 5.
        sort (str, optional): Sort key to use. Defaults to "downloads".
    """  # noqa: D205
    try:
        packages = find_and_sort(package, limit, sort)
        md = Markdown(packages)
        md.stream()
    except Exception as e:
        traceback.print_exc()
    


@cli.command("info")
@click.argument("package")
@click.option("--detailed", "-d", is_flag=True, help="Show verbose output")
def info_command(package, detailed) -> None:
    """Get information about a package from PyPI.

    Args:
        package (str): The package to get information about.
        detailed (bool, optional): Show detailed output. Defaults to False.
    """
    try:
        package_info = get_package_info(package, detailed)
        md = Markdown(package_info)
        md.stream()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)


@cli.command("create")
@click.argument("project_name")
@click.argument("author")
@click.option("--description", default="", help="Project description")
@click.option("--deps", default=None, help="Dependencies separated by commas")
@click.option("--python-version", default="3.10", help="Python version to use")
@click.option("--no-cli", is_flag=True, help="Do not add a CLI")
def create_command(project_name, author, description, deps, python_version="3.10", no_cli=False) -> None:
    """Create a new Python project. Optionally add dependencies and a CLI."""
    try:
        if deps:
            deps = deps.split(",")
        create_project(project_name, author, description, deps, python_version, not no_cli)
        click.echo(f"Project {project_name} created successfully.")
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    cli()
