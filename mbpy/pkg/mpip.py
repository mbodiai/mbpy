"""Synchronizes requirements and hatch pyproject."""

from dataclasses import dataclass, field
import logging
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Callable, Dict, Generic, List, TypeVar, cast, get_args, overload

import tomlkit
from tomlkit import array
from tomlkit.items import Array, Table
from typing_extensions import Literal

from mbpy.collect import asyncaccessing
from mbpy.import_utils import smart_import


if TYPE_CHECKING:
    from typing import Iterable, Union

    from mbpy.cmd import run
    from mbpy.collect import (
        PathType,
        doesnot,
        filterfalse,
        first,
        replace,
    )
    from inspect import isawaitable
    from mbpy.import_utils import smart_import
    from mbpy.pkg.dependency import Dependency
    from mbpy.pkg.requirements import aget_requirements_packages
    from mbpy.pkg.toml import find_toml_file
    from mbpy.pkg.toml import afind_toml_file,aget_toml_config
    from mbpy.pkg.dependency import Dependencies
    Deps = Dependencies




async def write_pyproject(data, filename="pyproject.toml") -> None:
    """Write the modified pyproject.toml data back to the file."""
    print(f"Writing to {filename}")
    original_data = Path(filename).read_text() if Path(filename).exists() else ""
    import anyio
    try:
        async with await anyio.open_file(filename, "w") as f:
            await f.write(tomlkit.dumps(data))
    except Exception as e:
        logging.exception(f"Failed to write to {filename}: {e}")
        async with await anyio.open_file( filename,"w") as f:
            await f.write(original_data)

@overload
async def modify_pyproject(
    packages:"Dependencies | List[Dependency | str]",
    action: Literal["install", "uninstall", "upgrade"] = "install",
    env: str | None = None,
    group: Literal["dependencies", "optional-dependencies", "all"] | str | None = None,
    pyproject_path: "PathType" = "pyproject.toml",
) -> None:    ...

@overload
async def modify_pyproject(
    *,
    package: "Dependency | str",
    action: Literal["install", "uninstall", "upgrade"] = "install",
    env: str | None = None,
    group: Literal["dependencies" ,"optional-dependencies" ,"all"] | str | None = None,
    pyproject_path: "PathType" = "pyproject.toml",
) -> None:    ...

async def modify_pyproject(*args, **kwargs) -> None:
    """Modify the pyproject.toml file to update dependencies based on action.

    Args:
        package (str): Name of the package to modify.
        package_version (str): Version of the package (optional).
        action (str): Action to perform, either 'install' or 'uninstall'.
        env (Optional[str]): Environment to modify (if applicable).
        group (str): Dependency group to modify (default is 'dependencies').
        pyproject_path (str): Path to the pyproject.toml file.

    Raises:
        FileNotFoundError: If pyproject.toml is not found.
        ValueError: If Hatch environment is specified but not found in pyproject.toml.
    """
    if TYPE_CHECKING:
        from mbpy.pkg.dependency import Dependency
        from mbpy.pkg.toml import aget_toml_config,afind_toml_file
    else:
        aget_toml_config = smart_import("mbpy.pkg.toml.aget_toml_config")
        afind_toml_file = smart_import("mbpy.pkg.toml.afind_toml_file")


    kwargs.update(dict(zip(set(["package", "action", "env", "group", "pyproject_path"]) - set(kwargs.keys()), args)))
    env = kwargs.get("env")
    pyproject_path = Path(kwargs.get("pyproject_path", "pyproject.toml"))
    pyproject_path = await afind_toml_file(pyproject_path)
    group = kwargs.get("group")
    group = group.strip("-").strip(".").strip() if group is not None else "dependencies"
    pyproject = tomlkit.parse(pyproject_path.read_text())
    is_optional = group is not None and group != "dependencies" and env is None
    if env:
        base_project = (
            pyproject.setdefault("tool", {})
            .setdefault("mb", {})
            .setdefault("envs", {})
            .setdefault(env, {})
        )
    else:
        base_project: Table = pyproject.setdefault("project", {})



    packages = kwargs.get("packages", [kwargs.get("package", *[])])

    action = kwargs.get("action", "install")
    if isinstance(packages, str):
        packages = [packages]
    if is_optional:

        base_project.get("optional-dependencies", {})[group] = cast(Array, [await dep.project_install_cmd for dep in await modify_dependency_list(
            base_project.get("optional-dependencies", {}).get(group, []), packages, action,
        )])

    else:
        dependencies = base_project.get("dependencies", [])
        base_project["dependencies"] = cast(Array, [await dep.project_install_cmd for dep in await modify_dependency_list(
            dependencies, packages, action,
        )])
    
    all_group = base_project.get("optional-dependencies", {}).get("all", [])
    base_project.get("optional-dependencies", {})["all"] = cast(Array, [await dep.project_install_cmd for dep in await modify_dependency_list(
            all_group, packages, action,
        )])


    # Ensure dependencies are written on separate lines
    if "dependencies" in base_project:
        cast(Array, base_project["dependencies"]).multiline(True)
        logging.debug(f"dependencies: {base_project['dependencies']}")
    pyproject = cast(dict, pyproject)
    if env is not None:
        pyproject["tool"]["mb"]["envs"][env]["dependencies"] = base_project["dependencies"]
    else:
        pyproject["project"]["dependencies"] = base_project["dependencies"]
    pyproject_path.write_text(tomlkit.dumps(pyproject))

async def modify_dependencies(
    incoming: "list[Dependency|str]",
    action: Literal["install", "uninstall", "upgrade"],
    group: Literal["dependencies", "optional-dependencies", "all"] = "dependencies",
    env: str | None = None,
):

    await modify_requirements(incoming, action, group)
    await modify_pyproject(packages=incoming, action=action, group=group, env=env)


async def modify_dependency_list(
    dependencies: "list[Dependency] | list[str] | list[Dependency | str]",
    incoming: "list[Dependency|str ] | list[Dependency | str] | list[str]",
    action: Literal["install", "uninstall", "upgrade"],
    requirements: bool = False,
) -> "list[Dependency]":
    """Modify a list of dependencies based on the specified action."""
    if not TYPE_CHECKING:
        Dependency = smart_import("mbpy.pkg.dependency.Dependency")
    
    dependencies = [Dependency(dep) if isinstance(dep, str) else dep for dep in dependencies]
    incoming = [Dependency(dep) if isinstance(dep, str) else dep for dep in incoming]
    deps = cast("list[Dependency]", dependencies)
    incs = cast("list[Dependency]", incoming)
    
    if action in ("uninstall", "upgrade"):
        return [dep for dep in deps  if not any(dep.base == inc.base for inc in incs)]

        
    if action in ("install", "upgrade"):
        return incs + [dep for dep in deps if dep.base not in [inc.base for inc in incs]]

    raise ValueError(f"Invalid action: {action} . Must be one of 'install', 'uninstall', or 'upgrade'.")
    
async def modify_requirements(
        incoming: "Dependencies",
        action: Literal["install", "uninstall", "upgrade"],
        group: Literal["dependencies", "optional-dependencies", "all"] = "dependencies",
):
    """Modify the requirements.txt file to install or uninstall a package."""
    if TYPE_CHECKING:
        from mbpy.pkg.requirements import aget_requirements_packages, awrite_requirements
    else:
        aget_requirements_packages = smart_import("mbpy.pkg.requirements.aget_requirements_packages")
        awrite_requirements = smart_import("mbpy.pkg.requirements.awrite_requirements")
    
    deps = await aget_requirements_packages(astype="deps")
    modified = await modify_dependency_list(deps, incoming, action, requirements=True)
    return await awrite_requirements(modified)
