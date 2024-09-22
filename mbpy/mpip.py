"""Synchronizes requirements and hatch pyproject."""

import logging
import traceback
from pathlib import Path
from typing import List

import click
import requests
import tomlkit
from rich.logging import RichHandler
import argparse
logger = logging.getLogger(__name__)
logger.addHandler(RichHandler())
logger.setLevel(logging.INFO)


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
        return data['info']['version']
    except requests.RequestException as e:
        logging.error(f"Error fetching latest version for {package_name}: {e}")
    except (KeyError, ValueError) as e:
        logging.error(f"Error parsing response for {package_name}: {e}")
    except Exception as e:
        logging.exception(f"Unexpected error fetching latest version for {package_name}: {e}")
    return None

def get_package_names(query_key) -> list[str]:
    """Fetch package names from PyPI search results."""
    search_url = f"https://pypi.org/search/?q={query_key}"
    response = requests.get(search_url, timeout=20)
    response.raise_for_status()
    page_content = response.text

    # Extract package names from search results
    start_token = '<a class="package-snippet"' # noqa
    end_token = "</a>" # noqa
    name_token = '<span class="package-snippet__name">' # noqa

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


def get_package_info(package_name, verbose=False, include=None, release=None) -> dict:
    """Retrieve detailed package information from PyPI JSON API."""
    package_url = f"https://pypi.org/pypi/{package_name}/json"
    response = requests.get(package_url, timeout=10)
    response.raise_for_status()
    package_data = response.json()
    info = package_data.get("info", {})
    if release:
        info = package_data.get("releases", {}).get(release, [{}])[0]
    if not info:
        raise ValueError(f"Package not found: {package_name} {'for release' + str(release) if release else ''}")
    
    downloads = package_data.get("downloads", "unavailable")
    package_info = {
        "name": info.get("name", ""),
        "version": info.get("version", ""),
        "summary": info.get("summary", ""),
        "downloads": downloads,
        "upload_time": info.get("upload_time", ""),
        "urls": info.get("project_urls", info.get("urls", {})),
        "description": info.get("description", "")[:100],
    }

    if verbose:
        package_info["description"] = info.get("description", "")

    project_urls = info.get("project_urls", info.get("urls", {}))
    try:
        package_info["github_url"] = next(
            (url for _, url in project_urls.items() if "github.com" in url.lower()), None
        )
    except (StopIteration, TypeError, AttributeError):
        package_info["github_url"] = None

    include = [include] if isinstance(include, str) else include
    if include and "all" in include:
        include = INFO_KEYS + ADDITONAL_KEYS
    package_info["releases"] = package_info.get("releases", {})
    package_releases = package_info["releases"]
    if include and isinstance(include, list):
        for key in include:
            if key == "releases":
                releases = list(package_data.get(key, {}).keys())
                package_releases[key] = {}
                for release in releases:
                    package_releases[key][release] = {
                        release : package_data[key][release][0].get("upload_time", "")
                    }
                continue
            if key in ADDITONAL_KEYS:
                package_info[key] = package_data.get(key, {})
            elif key in INFO_KEYS:
                package_info[key] = info.get(key, "")
            else:
                raise ValueError(f"Invalid key: {key}")

    package_info["releases"] = dict(sorted(package_info["releases"].items(), key=lambda item: item[1], reverse=True))


    return package_info


def find_and_sort(query_key, limit=7, sort=None, verbose=False, include=None, release=None) -> list[dict]:
    """Find and sort potential packages by a specified key.

    Args:
        query_key (str): The key to query for.
        limit (int): The maximum number of results to return.
        sort (str): The key to sort by. Defaults to None.
        verbose (bool): Whether to include verbose output.
        include (str or list): Additional information to include.
        release (str): Specific release to search for.

    Returns:
        list[dict]: List of packages sorted by the specified key.
    """
    try:
        package_names = get_package_names(query_key)
        packages = []
        for package_name in package_names:
            package_info = get_package_info(package_name, verbose, include, release)
            packages.append(package_info)

        if sort:
            packages.sort(key=lambda x: x.get(sort, 0), reverse=True)
        return packages[:limit]

    except requests.RequestException:
        return []
    except Exception:
        return []




def modify_requirements(
    package_name,
    package_version=None,
    action="install",
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
    lines = get_requirements_packages(requirements, as_set=False)
    logging.debug(f"modifying {package_name} {package_version} {action} {requirements}")
    # Extract the base package name and optional extras
    base_package_name, *extras = package_name.split("[")
    extras_str = "[" + ",".join(extras) if extras else ""
    package_line = next(
        (
            line
            for line in lines
            if base_package_name == line.split("[")[0].split("==")[0]
        ),
        None,
    )

    if action == "install":
        if package_version is not None:
            new_line = f"{base_package_name}{extras_str}=={package_version}"
        else:
            new_line = f"{base_package_name}{extras_str}"

        if package_line:
            # Replace the line with the same base package name
            lines = [
                line
                if base_package_name != line.split("[")[0].split("==")[0]
                else new_line
                for line in lines
            ]
        else:
            lines.append(new_line)

    elif action == "uninstall":
        # Remove lines with the same base package name
        lines = [
            line
            for line in lines
            if base_package_name != line.split("[")[0].split("==")[0]
        ]
    # Ensure each line ends with a newline character
    lines = [line + "\n" for line in lines]
    with Path(requirements).open("w") as f:
        f.writelines(lines)


def is_group(line) -> bool:
    return (
        "[" in line
        and "]" in line
        and '"' not in line[line.index("[") : line.index("]")]
    )

def parse_dependencies(dependencies) -> list[str]:
    if isinstance(dependencies, str):
        dependencies = dependencies.strip()
        if dependencies.startswith('[') and dependencies.endswith(']'):
            return dependencies[1:-1].strip(), True
        return dependencies, False
    return dependencies, False

def split_dependencies(dependencies) -> list[str]:
    if isinstance(dependencies, str):
        import re
        # This regex handles package names with extras and versions
        pattern = r'([^,\s\[]+(?:\[[^\]]*\])?(?:==?[^,\s]+)?)'
        return [dep.strip() for dep in re.findall(pattern, dependencies)]
    return dependencies


def process_dependencies(dependencies, output_lines=None) -> list[str]:
    if output_lines is None:
        output_lines = []

    dependencies, add_closing_bracket = parse_dependencies(dependencies)
    if add_closing_bracket:
        output_lines.append('dependencies = [')

    deps_list = split_dependencies(dependencies)

    for dep in deps_list:
        formatted_dep = format_dependency(dep)
        output_lines.append(formatted_dep)

    if add_closing_bracket:
        output_lines.append(']')

    return output_lines

def format_dependency(dep) -> str:
    formatted_dep = dep.strip().strip('"').rstrip(',')  # Remove quotes and trailing comma
    if '[' in formatted_dep and ']' in formatted_dep:
        name, rest = formatted_dep.split('[', 1)
        extras, *version = rest.split(']')
        extras = extras.replace(',', ', ').strip()
        version = ']'.join(version).strip()
        formatted_dep = f'{name.strip()}[{extras}]{version}'
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


def base_name(package_name) -> str:
    """Extract the base package name from a package name with optional extras.

    Args:
        package_name (str): The package name with optional extras.

    Returns:
        str: The base package name without extras.
    """
    return package_name.split("[")[0].split("==")[0]


def name_and_version(package_name, upgrade=False) -> tuple[str, str]:
    if upgrade:
        version = get_latest_version(base_name(package_name))
        return base_name(package_name), version
    if "==" in package_name:
        return package_name.split("==")
    return package_name, None


def modify_pyproject_toml(
    package_name: str,
    package_version: str = "",
    action: str = "install",
    hatch_env: str | None = None,
    dependency_group: str = "dependencies",
    pyproject_path: str = "pyproject.toml",
) -> None:
    """Modify the pyproject.toml file to update dependencies based on action.

    Args:
        package_name (str): Name of the package to modify.
        package_version (str): Version of the package (optional).
        action (str): Action to perform, either 'install' or 'uninstall'.
        hatch_env (Optional[str]): Hatch environment to modify (if applicable).
        dependency_group (str): Dependency group to modify (default is 'dependencies').
        pyproject_path (str): Path to the pyproject.toml file.

    Raises:
        FileNotFoundError: If pyproject.toml is not found.
        ValueError: If Hatch environment is specified but not found in pyproject.toml.
    """
    logging.debug(f"modifying {package_name} {package_version} {action} {hatch_env} {dependency_group}")
    pyproject_path = find_toml_file(pyproject_path)
    logging.debug(f"modifying {pyproject_path}")
    if not pyproject_path.exists():
        raise FileNotFoundError("pyproject.toml not found.")

    with pyproject_path.open() as f:
        pyproject = tomlkit.parse(f.read())

    is_optional = dependency_group != "dependencies"
    is_hatch_env = hatch_env and "tool" in pyproject and "hatch" in pyproject.get("tool", {})
    if hatch_env and not is_hatch_env:
        raise ValueError("Hatch environment specified but hatch tool not found in pyproject.toml.")

    package_version_str = f"{package_name}{('==' + package_version) if package_version else ''}"
    
    if is_hatch_env:
        base_project = pyproject.setdefault("tool", {}).setdefault("hatch", {}).setdefault("envs", {}).setdefault(hatch_env, {})
    else:
        base_project = pyproject.setdefault("project", {})
    
    if is_optional:
        optional_base = base_project.setdefault("optional-dependencies", {})
        dependencies = optional_base.get(dependency_group, [])
        optional_base[dependency_group] = modify_dependencies(dependencies, package_version_str, action)
        all_group = optional_base.get("all", [])
        optional_base["all"] = modify_dependencies(all_group, package_version_str, action)
    else:
        dependencies = base_project.get("dependencies", [])
        base_project["dependencies"] = modify_dependencies(dependencies, package_version_str, action)

    # Ensure dependencies are written on separate lines
    if "dependencies" in base_project:
        base_project["dependencies"] = tomlkit.array(base_project["dependencies"])
        base_project["dependencies"].multiline(True)
        logging.debug(f"dependencies: {base_project['dependencies']}")
    with pyproject_path.open("w") as f:
        f.write(tomlkit.dumps(pyproject))
    print(f"Successfully {action}ed {package_name} {package_version or ''} in {pyproject_path}")  
    # Update requirements.txt if it exists
    requirements_path = pyproject_path.parent / "requirements.txt"
    if requirements_path.exists():
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
    package_name = base_name(package_version_str)
    
    dependencies = [
        dep for dep in dependencies
        if base_name(dep) != package_name
    ]
    if action == "install":
        dependencies.append(package_version_str.strip())
    dependencies.sort(key=lambda x: base_name(x).lower())  # Sort dependencies alphabetically
    
    return dependencies



def search_parents_for_file(file_name, max_levels=3, cwd: str | None = None) -> Path:
    """Search parent directories for a file."""
    current_dir = Path(cwd) if cwd else Path.cwd()
    it = 0
    target_file = Path(str(file_name))
    while not target_file.exists():
        logger.debug(f"Checking {current_dir}")
        if it > max_levels:
            break
        current_dir = current_dir.parent
        target_file = current_dir / file_name
    return target_file

def find_toml_file(path: str | Path = "pyproject.toml") -> Path:
    """Find the pyproject.toml file in the current directory or parent directories."""
    path = path or "pyproject.toml"
    toml_file = search_parents_for_file(path, max_levels=3)
    if not toml_file.exists():
        raise FileNotFoundError("pyproject.toml file not found in current or parent directories.")
    return toml_file

def get_requirements_packages(requirements="requirements.txt", as_set=True) -> set[str] | list[str]:
    """Get the list of packages from the requirements.txt file.

    Args:
        requirements (str): Path to the requirements file. Defaults to "requirements.txt".
        as_set (bool): Whether to return the result as a set. Defaults to True.

    Returns:
        set or list: Packages listed in the requirements file.
    """
    requirements_path = search_parents_for_file(requirements, max_levels=3)
    if not requirements_path.exists():
        click.echo(
            f"\033[93mWarning: Requirements file '{requirements}' not found. Creating an empty one.\033[0m"
        )
        requirements_path.touch()
        return set() if as_set else []
    lines = requirements_path.read_text().splitlines()
    lines = [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]
    return set(lines) if as_set else lines


def main() -> None:
    get_package_info("aider-chat")


if __name__ == "__main__":
    main()
# Copy the entire contents of the root pypip.py file here
