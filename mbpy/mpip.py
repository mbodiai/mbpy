"""Synchronizes requirements and hatch pyproject."""

import argparse

import logging
import os
import re
import sys
import traceback
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, cast, overload

import click
import requests
import tomlkit
from rich.console import Console
from rich.prompt import Confirm
from tomlkit import array, table
from tomlkit.items import Array, Table
from typing_extensions import Literal, TypedDict

from mbpy.commands import run
from mbpy.context import suppress
from mbpy.repair import equals
from mbpy.utils.collections import PathLike, PathType, compose, first, re_iter, replace, filterfalse
console = Console()
ENV_VARS = ["CONDA_PREFIX", "VIRTUAL_ENV", "MBNIX_ENV", "COLCON_PREFIX"]
PYTHON_ENV_PATH = Path(sys.executable).parts[:-3]
INFO_KEYS = [
    "author",
    "author_email",
    "bugtrack_url",
    "classifiers",
    "description",
    "description_content_type",
    "docs_url",
    "download_url",
    "downloads",
    "dynamic",
    "home_page",
    "keywords",
    "license",
    "maintainer",
    "maintainer_email",
    "name",
    "package_url",
    "platform",
    "project_url",
    "project_urls",
    "provides_extra",
    "release_url",
    "requires_dist",
    "requires_python",
    "summary",
    "version",
    "yanked",
    "yanked_reason",
]
ADDITONAL_KEYS = ["last_serial", "releases", "urls", "vulnerabilities"]


def get_latest_version(package_name: str) -> str | None:
    """Gets the latest version of the specified package from PyPI.

    Args:
        package_name (str): The name of the package to fetch the latest version for.

    Returns:
        Optional[str]: The latest version of the package, or None if not found or on error.
    """
    try:
        response = requests.get(f"https://pypi.org/pypi/{package_name}/json", timeout=5)
        response.raise_for_status()  # Raises stored HTTPError, if one occurred.
        data = response.json()
        return data["info"]["version"]
    except requests.RequestException as e:
        logging.exception(f"Error fetching latest version for {package_name}: {e}")
    except (KeyError, ValueError) as e:
        logging.exception(f"Error parsing response for {package_name}: {e}")
    except Exception as e:
        logging.exception(f"Unexpected error fetching latest version for {package_name}: {e}")
    return ""


def get_package_names(query_key) -> list[str]:
    """Fetch package names from PyPI search results."""
    search_url = f"https://pypi.org/search/?q={query_key}"
    response = requests.get(search_url, timeout=20)
    response.raise_for_status()
    page_content = response.text

    # Extract package names from search results
    start_token = '<a class="package-snippet"'  # noqa
    end_token = "</a>"  # noqa
    name_token = '<span class="package-snippet__name">'  # noqa

    package_names = []
    start = 0
    while True:
        start = page_content.find(start_token, start)
        if start == -1:
            break
        end = page_content.find(end_token, start)
        snippet = page_content[start:end]
        name_start = snippet.find(name_token)
        if name_start != -1:
            name_start += len(name_token)
            name_end = snippet.find("</span>", name_start)
            package_name = snippet[name_start:name_end]
            package_names.append(package_name)
        start = end
    return package_names




class UploadInfo(TypedDict, total=False):
    version: Optional[str]
    upload_time: str
    requires_python: Optional[str]


class PackageInfo(TypedDict, total=False):
    name: str
    version: str
    author: str
    summary: str
    description: str
    latest_release: str
    earliest_release: UploadInfo
    urls: Dict[str, str]
    github_url: str
    description: str
    requires_python: str
    releases: List[Dict[str, UploadInfo]] | None


def ensure_backticks(text: str) -> str:
    """Ensure that backticks are completed in the given text."""
    # Triple quotes first

    open_backticks = text.count("\n```")
    close_backticks = text.count("```\n")
    while open_backticks > close_backticks:
        text += "`"
        close_backticks += 1
    while close_backticks > open_backticks:
        text = "`" + text
        open_backticks += 1
    # Single quotes next
    open_backticks = text.count(" `")
    close_backticks = text.count("` ")
    while open_backticks > close_backticks:
        text += "`"
        close_backticks += 1
    while close_backticks > open_backticks:
        text = "`" + text
        open_backticks += 1
    return text


def get_package_info(package_name, verbosity=0, include=None, release=None) -> PackageInfo:
    """Retrieve detailed package information from PyPI JSON API."""
    package_name = getbase(package_name.strip().lower().replace("-", "_"))
    package_url = f"https://pypi.org/pypi/{package_name}/json"
    response = requests.get(package_url, timeout=10)
    if response.status_code != 200:
        logging.warning(f"Package not found: {package_name}")
        return {}
    package_data: dict = deepcopy(response.json())
    logging.debug("package_data")
    logging.debug(package_data)
    info = package_data.get("info", {})
    if release:
        release_found = False
        for key in package_data.get("releases", {}):
            if release in key:
                release_found = True
                info = package_data.get("releases", {}).get(key, [{}])[0]
                break
        if not release_found:
            releases = package_data.get("releases", {}).keys()
            preview = 4 if len(releases) > 8 else 2 if len(releases) > 4 else 1
            first = ", ".join(list(releases)[:preview])
            last = ", ".join(list(releases)[-preview:])
            color = "spring_green1"
            console.print(
                f"[bold {color}]{package_name}[/bold {color}] release `{release}` not found in  {first} ... {last}"
            )

    if not info:
        raise ValueError(f"Package not found: {package_name} {'for release' + str(release) if release else ''}")

    releases = package_data.get("releases", {})

    if releases:
        releases = sorted(
            releases.items(), key=lambda x: x[1][0]["upload_time"] if len(x[1]) > 0 else "zzzzzzz", reverse=True
        )

        if releases and len(releases[0][1]) > 0 and len(releases[-1][1]) > 0:
            latest, earliest = releases[0], releases[-1]
        else:
            latest, earliest = None, None
    else:
        latest, earliest = None, None

    package_info: PackageInfo = {
        "name": info.get("name", ""),
        "version": info.get("version", ""),
        "summary": info.get("summary", ""),
        "latest_release": latest[1][0]["upload_time"] if latest else "",
        "author": info.get("author", ""),
        "earliest_release": {
            "version": earliest[0],
            "upload_time": earliest[1][0]["upload_time"],
            "requires_python": earliest[1][0].get("requires_python", ""),
        }
        if earliest
        else {},
        "urls": info.get("project_urls", info.get("urls", {})),
        "description": ensure_backticks(info.get("description", ""))[: verbosity * 250],
        "requires_python": info.get("requires_python", ""),
        "releases": [{release[0]: {"upload_time": release[1][0]["upload_time"]}} for release in releases]
        if releases and len(releases[0][1]) > 0
        else [],
    }

    if verbosity > 2:
        package_info["description"] = info.get("description", "")

    project_urls: Dict[str,str] = info.get("project_urls", info.get("urls", {}))
    try:
        package_info["github_url"] = next((url for _, url in project_urls.items() if "github.com" in url.lower()), None) or ""
    except (StopIteration, TypeError, AttributeError):
        package_info["github_url"] = ""

    include = [include] if isinstance(include, str) else include or []
    if include and "all" in include:
        include = INFO_KEYS + ADDITONAL_KEYS

    for key in include:
        if key in ("releases", "release"):
            continue
        if key in ADDITONAL_KEYS:
            package_info[key] = package_data.get(key, {})
        elif key in INFO_KEYS:
            package_info[key] = info.get(key, "")
        else:
            raise ValueError(f"Invalid key: {key}")

    if "releases" not in include:
        package_info.pop("releases", None)
    return package_info


def find_and_sort(query_key, limit=7, sort=None, verbosity=0, include=None, release=None) -> list[PackageInfo]:
    """Find and sort potential packages by a specified key.

    Args:
        query_key (str): The key to query for.
        limit (int): The maximum number of results to return.
        sort (str): The key to sort by. Defaults to None.
        verbosity (int): The verbosity level for package descriptions.
        include (str or list): Additional information to include.
        release (str): Specific release to search for.

    Returns:
        list[dict]: List of packages sorted by the specified key.
    """
    try:
        package_names = get_package_names(query_key)
        packages = []
        for package_name in package_names:
            package_info = get_package_info(package_name, verbosity, include, release)
            packages.append(package_info)

        if sort:
            packages.sort(key=lambda x: x.get(sort, 0), reverse=True)
        return packages[:limit]

    except requests.RequestException:
        logging.debug(f"Error fetching package names for {query_key}")
        traceback.print_exc()
        return []
    except Exception:
        logging.debug(f"Error fetching package info for {query_key}")
        traceback.print_exc()
        return []
equals_pkg = lambda basename : compose(equals(basename),getbase)

def modify_requirements(
    package_name:str,
    package_version: str | None = None,
    action: Literal["install", "uninstall", "upgrade"] = "install",
    requirements="requirements.txt",
) -> None:
    """Modify the requirements.txt file to install or uninstall a package.

    Args:
        package_name (str): The name of the package to install or uninstall.
        package_version (str, optional): The version of the package to install. Defaults to None.
        action (str): The action to perform, either 'install' or 'uninstall'.
        requirements (str): The path to the requirements file. Defaults to "requirements.txt".

    Raises:
        FileNotFoundError: If the requirements.txt file does not exist when attempting to read.
    """
    base_name = getbase(package_name)
    version = package_version or getversion(package_name)
    lines: list[str] = get_requirements_packages(requirements, "list")
    logging.debug(f"modifying {package_name} {version} {action} {requirements}")
    match = re.search(r"\[([^\]]+)\]", package_name)
    extras = f"[{match.group(1)}]" if match else ""

    matched_line = first(filter(equals_pkg(base_name), lines))

    if action == "install":
        new_line = pkg_str(base_name,version,extras)

        if matched_line:
            # Replace the line with the same base package name
            lines = replace(lines, equals_pkg(base_name),new_line)
        else:
            lines.append(new_line)

    elif action == "uninstall":
        # Remove lines with the same base package name
        lines = filterfalse( lines, equals_pkg(base_name))
        print(list(lines))
    Path(requirements).write_text("\n".join(lines) + "\n")


def is_group(line) -> bool:
    return "[" in line and "]" in line and '"' not in line[line.index("[") : line.index("]")]


def parse_dependencies(dependencies) -> list[str]:
    if isinstance(dependencies, str):
        dependencies = dependencies.strip()
        if dependencies.startswith("[") and dependencies.endswith("]"):
            return dependencies[1:-1].strip(), True
        return dependencies, False
    return dependencies, False


def split_dependencies(dependencies) -> list[str]:
    if isinstance(dependencies, str):
        import re

        # This regex handles package names with extras and versions
        pattern = r"([^,\s\[]+(?:\[[^\]]*\])?(?:==?[^,\s]+)?)"
        return [dep.strip() for dep in re.findall(pattern, dependencies)]
    return dependencies


def process_dependencies(dependencies, output_lines=None) -> list[str]:
    if output_lines is None:
        output_lines = []

    dependencies, add_closing_bracket = parse_dependencies(dependencies)
    if add_closing_bracket:
        output_lines.append("dependencies = [")

    deps_list = split_dependencies(dependencies)

    for dep in deps_list:
        formatted_dep = format_dependency(dep)
        output_lines.append(formatted_dep)

    if add_closing_bracket:
        output_lines.append("]")

    return output_lines


def format_dependency(dep) -> str:
    formatted_dep = dep.strip().strip('"').rstrip(",")  # Remove quotes and trailing comma
    if "[" in formatted_dep and "]" in formatted_dep:
        name, rest = formatted_dep.split("[", 1)
        extras, *version = rest.split("]")
        extras = extras.replace(",", ", ").strip()
        version = "]".join(version).strip()
        formatted_dep = f"{name.strip()}[{extras}]{version}"
    return f'  "{formatted_dep}"'


def write_pyproject(data, filename="pyproject.toml") -> None:
    """Write the modified pyproject.toml data back to the file."""
    original_data = Path(filename).read_text() if Path(filename).exists() else ""
    try:
        with Path(filename).open("w") as f:
            toml_str = tomlkit.dumps(data)
            inside_dependencies = False
            inside_optional_dependencies = False

            input_lines = toml_str.splitlines()
            output_lines = []
            for input_line in input_lines:
                line = input_line.rstrip()
                if is_group(line):
                    inside_dependencies = False
                    inside_optional_dependencies = "optional-dependencies" in line
                    output_lines.append(line)
                    continue

                if "]" in line and inside_dependencies and "[" not in line:
                    inside_dependencies = False
                    output_lines.append(line)
                    continue

                if inside_optional_dependencies:
                    process_dependencies(line, output_lines)
                    continue

                if (
                    "dependencies" in line
                    and "optional-dependencies" not in line
                    and "extra-dependencies" not in line
                    and not inside_optional_dependencies
                ):
                    inside_dependencies = True
                    inside_optional_dependencies = False
                    output_lines.extend(process_dependencies(line))
                    continue

                if inside_dependencies and not inside_optional_dependencies:
                    continue  # Skip lines inside dependencies as they are handled by process_dependencies

                output_lines.append(line)

            f.write("\n".join(output_lines))
    except Exception:
        with Path(filename).open("w") as f:
            f.write(original_data)


def getbase(package_name) -> str:
    """Extract the base package name from a package name with optional extras.

    Args:
        package_name (str): The package name with optional extras.

    Returns:
        str: The base package name without extras.
    """
    package_name =str(package_name).strip()
    package_name = package_name.split("[")[0]
    if "==" in package_name:
        return package_name.split("==")[0]
    if ">=" in package_name:
        return package_name.split(">=")[0]
    if "<=" in package_name:
        return package_name.split("<=")[0]
    if ">" in package_name:
        return package_name.split(">")[0]
    if "<" in package_name:
        return package_name.split("<")[0]
    
    return package_name

def getversion(package_name: str) -> str:
    """Get the version string from a package name."""
    if "==" in package_name:
        return package_name.split("==")[1]
    if ">=" in package_name:
        return package_name.split(">=")[1]
    if "<=" in package_name:
        return package_name.split("<=")[1]
    if ">" in package_name:
        return package_name.split(">")[1]
    if "<" in package_name:
        return package_name.split("<")[1]
    return ""

def getextras(package_name: str) -> list[str]:
    """Get the package extras from a package name."""
    l = package_name.find("[")
    r = package_name.rfind("]")
    return package_name[l:r+1].split(",")

def pkg_str(base_name, version, extras) -> str:
    """Get the package string from a base name, version, and extras."""
    extras_str = f"[{','.join(extras)}]" if extras else ""
    version_str = f">={version}" if version else ""
    return f"{base_name}{extras_str}{version_str}"
def name_and_version(package_name, upgrade=False) -> tuple[str, str]:
    if upgrade:
        version = get_latest_version(getbase(package_name))
        return getbase(package_name), ".".join(version.split(".")[:-1]) if version else ""

    return getbase(package_name), getversion(package_name)


def modify_pyproject_toml(
    package_name: str,
    package_version: str = "",
    action: Literal["install", "uninstall", "upgrade"] = "install",
    env: str | None = None,
    group: str = "dependencies",
    pyproject_path: PathType = "pyproject.toml",
) -> None:
    """Modify the pyproject.toml file to update dependencies based on action.

    Args:
        package_name (str): Name of the package to modify.
        package_version (str): Version of the package (optional).
        action (str): Action to perform, either 'install' or 'uninstall'.
        env (Optional[str]): Environment to modify (if applicable).
        group (str): Dependency group to modify (default is 'dependencies').
        pyproject_path (str): Path to the pyproject.toml file.

    Raises:
        FileNotFoundError: If pyproject.toml is not found.
        ValueError: If Hatch environment is specified but not found in pyproject.toml.
    """
    group = group.strip("-").strip(".").strip() if group is not None else "dependencies"
    logging.debug(f"modifying {package_name} {package_version} {action} {env} {group}")
    pyproject_path = find_toml_file(pyproject_path)
    logging.debug(f"modifying {pyproject_path}")
    if not pyproject_path.exists():
        raise FileNotFoundError("pyproject.toml not found.")

    with pyproject_path.open() as f:
        pyproject = tomlkit.parse(f.read())

    is_optional = group is not None and group != "dependencies"

    package_version_str = f"{package_name}{('>=' + package_version) if package_version else ''}"

    if env:
        base_project = (
            pyproject.setdefault("tool", {}).setdefault("pynix", {}).setdefault("envs", {}).setdefault(env, {})
        )
    else:
        base_project: Table = pyproject.setdefault("project", {})

    if is_optional:
        optional_base = base_project.setdefault("optional-dependencies", {})
        dependencies = optional_base.get(group, [])
        optional_base[group] = modify_dependencies(dependencies, package_version_str, action)
        all_group = optional_base.get("all", [])
        optional_base["all"] = modify_dependencies(all_group, package_version_str, action)
    else:
        dependencies = base_project.get("dependencies", [])
        base_project["dependencies"] = array(str(modify_dependencies(dependencies, package_version_str, action)))

    # Ensure dependencies are written on separate lines
    if "dependencies" in base_project:
        cast(Array,base_project["dependencies"]).multiline(True)
        logging.debug(f"dependencies: {base_project['dependencies']}")

    pyproject_path.write_text(tomlkit.dumps(pyproject))

    # Update requirements.txt if it exists
    requirements_path = pyproject_path.parent / "requirements.txt"
    if requirements_path.exists():
        package_name = str(package_name)
        modify_requirements(package_name, package_version, action, str(requirements_path))


def modify_dependencies(dependencies: List[str], package_version_str: str, action: str) -> List[str]:
    """Modify the dependencies list for installing or uninstalling a package.

    Args:
        dependencies (List[str]): List of current dependencies.
        package_version_str (str): Package with version string to modify.
        action (str): Action to perform, either 'install' or 'uninstall'.

    Returns:
        List[str]: Modified list of dependencies.
    """
    package_name = getbase(package_version_str)

    dependencies = [dep for dep in dependencies if getbase(dep) != package_name]
    if action == "install":
        dependencies.append(package_version_str.strip())
    dependencies.sort(key=lambda x: getbase(x).lower())  # Sort dependencies alphabetically

    return dependencies

def search_parents_for_file(file_name: PathType, max_levels=3, cwd: str | None = None) -> Path:
        """Search parent directories for a file. If not found, search environment variable paths located 3 directories outside of mbnix."""
        current_dir = Path(cwd) if cwd else Path.cwd()
        it = 0
        target_file = current_dir / file_name
        found_paths: list[PathLike] = []

        while it <= max_levels and not target_file.exists():
            logging.debug(f"Checking {current_dir}")
            current_dir = current_dir.parent
            target_file = current_dir / file_name
            it += 1

        if not target_file.exists():
            # Search environment variable paths, including Conda
            for env_var in ENV_VARS:
                env_path = Path(os.environ.get(env_var, ""))
                if env_path and env_path.exists():
                    try:
                        potential_path = "/".join(env_path.parts[:-3]) / PathLike(file_name)
                        if potential_path.exists():
                            found_paths.append(potential_path)
                    except IndexError:
                        logging.warning(f"Environment variable {env_var} does not have enough parent directories.")

            if len(found_paths) == 1:
                target_file = found_paths[0]
            elif len(found_paths) > 1:
                console.print(f"Multiple locations found for {file_name}:")
                for idx, path in enumerate(found_paths, 1):
                    console.print(f"{idx}. {path}")
                choice = click.prompt("Select the file path by number", type=int)
                if 1 <= choice <= len(found_paths):
                    target_file = found_paths[choice - 1]
                else:
                    raise FileNotFoundError(f"Invalid selection for {file_name}.")
            else:
                raise FileNotFoundError(
                    f"'{file_name}' not found within {max_levels} parent directories or environment paths."
                )

        return target_file


def get_ordered_environs() -> List[str]:
    """Get the ordered list of virtual environments active in the current session."""
    envs = os.environ
    env_keys = [key for key in envs if any(key.startswith(envvar) for envvar in ENV_VARS)]
    # Prioritize Conda environments first
    env_keys.sort(key=lambda x: (x.startswith("CONDA_PREFIX"), envs[x]), reverse=True)
    return env_keys

def find_toml_file(path: PathType = "pyproject.toml") -> Path:
    """Find the pyproject.toml file in the current directory or parent directories."""
    path = path or "pyproject.toml"
    toml_file = search_parents_for_file(path, max_levels=3)
    if not toml_file.exists():
        raise FileNotFoundError("pyproject.toml file not found in current or parent directories.")
    return toml_file

@overload
def get_requirements_packages(
    requirements: PathType = "requirements.txt", astype: Literal["list"] = "list"
) -> list[str]:...
@overload
def get_requirements_packages(requirements: PathType, astype: Literal["set"]) -> set[str]:...

def get_requirements_packages(requirements: PathType = "requirements.txt", astype: Literal["set", "list"] = "list"):
    """Get the list of packages from the requirements.txt file.

    Args:
        requirements (str): Path to the requirements file. Defaults to "requirements.txt".
        astype (bool): Whether to return the result as a set. Defaults to True.

    Returns:
        set or list: Packages listed in the requirements file.
    """
    requirements_path = search_parents_for_file(requirements, max_levels=3)
    if not requirements_path.exists():
        click.secho(f"Warning: Requirements file '{requirements}' not found. Creating an empty one.", color="yellow")
        requirements_path.touch()
        return set() if astype == "set" else []
    lines = requirements_path.read_text().splitlines()
    lines = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    
    return set(lines) if astype == "set" else lines

def check_gh(package):
        with suppress.logignore():
            return package.startswith("git+")
def check_editable(package):
        with suppress.logignore():
            
            return package.split("")
def check_requirements_file(requirements="requirements.txt", prompt=False) -> None:
    """Check if the requirements file exists and create it if not."""
    pkgs = []
    for package in get_requirements_packages(requirements):
        if prompt and getbase(package) not in parse_dict(run(f"pip show {getbase(package)}", show=False))\
            and Confirm.ask(
            f"{package} not found. Install?"
        ):
            from mbpy.cli import _install_command

            _install_command(package, broken="repair")
        pkgs.append(package)
        if check_gh(package) or check_editable(package):
            pkgs.append(package)
            continue
        with suppress.logignore() as e:
            getbase(package)
            extra_pkgs = getextras(package)
            version = getversion(package)
            pkgs.append(pkg_str(getbase(package),version, extra_pkgs))
        if e:
            logging.warning(f"Skipped {package} as it was incorrectly")

def parse_dict(data: str, kv_separator: str = "=", comment_marker="#") -> dict:
    """Parse a string into a dictionary."""
    pattern = rf"(\w+){kv_separator}(\w+)"
    return dict(re_iter(pattern, data))


def main() -> None:
    get_package_info("pydub")


