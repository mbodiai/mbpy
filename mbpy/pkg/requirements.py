
from typing import TYPE_CHECKING, Literal, overload

from mbpy.import_utils import smart_import

if TYPE_CHECKING:
    from pathlib import Path

    from mbpy.collect import PathType
    from mbpy.pkg.dependency import Dependency

async def aget_requirements_file(
    requirements: "PathType" = "requirements.txt",
) -> "Path | None":
    """Get the list of packages from the requirements.txt file.

    Args:
        requirements (str): Path to the requirements file. Defaults to "requirements.txt".
        astype (bool): Whether to return the result as a set. Defaults to True.

    Returns:
        set or list: Packages listed in the requirements file.
        
    """
    if TYPE_CHECKING:
        from mbpy.helpers._display import getconsole
        from mbpy.helpers.traverse import asearch_parents_for_file
        console = getconsole()
    else:
        asearch_parents_for_file = smart_import("mbpy.helpers.traverse.asearch_parents_for_file")
        console = smart_import("mbpy.helpers._display.getconsole")()
        
    requirements_path = await asearch_parents_for_file(requirements, max_levels=3)


    if not requirements_path.exists():
        console.print(
            f"Warning: Requirements file '{requirements}' not found. Creating an empty one.",
            style="yellow",
        )
        requirements_path.touch()
        return requirements_path
    return requirements_path

@overload
async def aget_requirements_packages(

    astype: Literal["list"] = "list",
    requirements: "PathType" = "requirements.txt",
) -> list[str]:    ...
@overload
async def aget_requirements_packages(

    astype: Literal["set"] = "set",
    requirements: "PathType" = "requirements.txt",
) -> set[str]:    ...
@overload
async def aget_requirements_packages(

    astype: Literal["deps"] = "deps",
    requirements: "PathType" = "requirements.txt",
) -> "list[Dependency]":    ...

async def aget_requirements_packages(*args, **kwargs):
    """Get the list of packages from the requirements.txt file.

    Args:
        requirements (str): Path to the requirements file. Defaults to "requirements.txt".
        astype (str): Return type format ("set", "list", or "deps"). Defaults to "set".

    Returns:
        Union[set[str], list[str], Dependencies]: Packages listed in the requirements file.
    """
    requirements = kwargs.get("requirements", args[-1] if len(args) > 0 and args[-1] not in ("set", "list", "deps") else "requirements.txt")
    astype = kwargs.get("astype", args[0] if len(args) > 0 and args[0] in ("set", "list", "deps") else "set")
    requirements_path = await aget_requirements_file(requirements)
    Dependency = smart_import("mbpy.pkg.dependency.Dependency")
    if not requirements_path:
        return set() if astype == "set" else [] if astype == "list" else []
        
    try:
        lines = requirements_path.read_text().splitlines()
        # Filter out comments and empty lines
        lines = [
            line.strip()
            for line in lines
            if line.strip() and not line.strip().startswith("#")
        ]
        
        # Handle different return types
        if astype == "set":
            return set(lines)
        if astype == "list":
            return lines

        return [Dependency(l) for l in lines]
            
    except Exception as e:
        import logging
        logging.error(f"Error reading requirements file: {e}")
        return set() if astype == "set" else [] if astype == "list" else []
async def awrite_requirements(
    packages: "list[Dependency]",
    requirements: "PathType" = "requirements.txt",
):
    """Write the list of packages to the requirements.txt file.

    Args:
        packages (set): Set of packages to write to the requirements file.
        requirements (str): Path to the requirements file. Defaults to "requirements.txt".
        
    """
    if TYPE_CHECKING:
        from pathlib import Path

        from aiofiles import open
    else:
        open = smart_import("aiofiles.open") 
        Path = smart_import("pathlib.Path")
    requirements_path = await aget_requirements_file(requirements)
    requirements_path = requirements_path or Path(requirements)
    if not requirements_path.exists():
        requirements_path.touch()
    async with open(requirements_path, "w") as f:
        await f.write("\n".join([await p.requirements_name for p in packages]))
        await f.write("\n")