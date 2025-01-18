from pathlib import Path
from typing import TYPE_CHECKING, Literal, overload
from mbpy.collect import PathType,wraps

from mbpy.import_utils import smart_import

if TYPE_CHECKING:
    from tomlkit import table as Table
else:
    Table = smart_import("tomlkit.table")


def is_group(line) -> bool:
    return "[" in line and "]" in line and '"' not in line[line.index("[") : line.index("]")]

def find_toml_file(path: PathType = "pyproject.toml", cwd: PathType | None = None) -> Path:
    """Find the pyproject.toml file in the current directory or parent directories."""
    from mbpy.helpers.traverse import search_parents_for_file,search_children_for_file
    fc = search_children_for_file(path, max_levels=1, cwd=cwd)
    if fc:
        return fc
    f = search_parents_for_file(path, max_levels=1, cwd=cwd)
    if f:
        return f
    
    fc = search_children_for_file(path, max_levels=2, cwd=cwd)
    if fc:
        return fc
    f = search_parents_for_file(path, max_levels=2, cwd=cwd)
    if f:
        return f
    return search_parents_for_file(path, max_levels=3, cwd=cwd)

async def afind_toml_file(path: "PathType" = "pyproject.toml", cwd: "PathType | None" = None) -> Path:
    """Find the pyproject.toml file in the current directory or parent directories."""
    from mbpy.helpers.traverse import asearch_parents_for_file,asearch_children_for_file
    
    fc = await asearch_children_for_file(path, max_levels=1, cwd=cwd)
    if fc:
        return fc
    f = await asearch_parents_for_file(path, max_levels=1, cwd=cwd)
    if f:
        return f
    
    fc = await asearch_children_for_file(path, max_levels=2, cwd=cwd)
    if fc:
        return fc
    f = await asearch_parents_for_file(path, max_levels=2, cwd=cwd)
    if f:
        return f
    return await asearch_parents_for_file(path, max_levels=3, cwd=cwd)


def get_toml_config(env: str | None = None, group: Literal["dependencies", "optional-dependencies", "all"] | str | None = None, pyproject_path: "PathType" = "pyproject.toml"):
    if TYPE_CHECKING:
        from mbpy.pkg.dependency import Project,Dependency
        import tomlkit
        from typing import cast
    else:
        tomlkit = smart_import("tomlkit")
        cast = smart_import("typing").cast



    group = group.strip("-").strip(".").strip() if group is not None else "dependencies"

    pyproject_path = find_toml_file(pyproject_path)
    pyproject = tomlkit.parse(pyproject_path.read_text())
    is_optional = group is not None and group != "dependencies"
    if env:
        base_project = (
            pyproject.setdefault("tool", {})
            .setdefault("hatch", {})
            .setdefault("envs", {})
            .setdefault(env, {})
        )
    else:
        base_project = pyproject.setdefault("project", {})

    if is_optional:
        base_project = base_project.setdefault("optional-dependencies", [])
    else:
        base_project = base_project.setdefault("dependencies", [])

    return Project(python=[Dependency(dep) for dep in base_project])


async def aget_toml_config(
    *,
    env: str | None = None,
    group: Literal["dependencies", "optional-dependencies", "all"] | str | None = None,
    pyproject_path: "PathType" = "pyproject.toml",
) -> "Project":
    if TYPE_CHECKING:
        from mbpy.pkg.dependency import Project ,Dependency
        import tomlkit
    else:
        tomlkit = smart_import("tomlkit")
        Deps: type[Project] = smart_import("mbpy.pkg.dependency.Project")
        Dependency = smart_import("mbpy.pkg.dependency.Dependency")
    pyproject_path = await afind_toml_file(pyproject_path)
    group = group.strip("-").strip(".").strip() if group is not None else "dependencies"
    pyproject = tomlkit.parse(pyproject_path.read_text())
    is_optional = group is not None and group != "dependencies"
    if env:
        base_project = await (
            pyproject.setdefault("tool", {})
            .setdefault("mb", {})
            .setdefault("envs", {})
            .setdefault(env, {})
        )
    else:
        base_project: dict = pyproject.setdefault("project", {})

    if is_optional:
        base_project = base_project.setdefault("optional-dependencies", {})
    else:
        base_project = base_project.setdefault("dependencies", {})

    return Project(python=[Dependency(dep) for dep in base_project])
