import logging
from pathlib import Path
from typing import TYPE_CHECKING

from mbpy.collect import PathLike, PathType
from mbpy.helpers._cache import acache, cache
from mbpy.import_utils import smart_import

if TYPE_CHECKING:
    from mbpy.collect import PathLike, PathType

@cache
def search_parents_for_file(
    file_name: PathType,
    max_levels=3,
    cwd: "PathType | None" = None,
) -> "PathLike":
    """Search parent directories for a file."""
    file_name = PathLike(file_name)
    logging.debug(f"exists ? {file_name.exists()}")
    file_name = file_name.name if file_name.is_absolute() else file_name
    logging.debug(f"Searching for {file_name} in parent directories of {cwd}")
    current_dir = PathLike(cwd) if cwd else Path.cwd()
    it = 0
    target_file = current_dir / file_name
    while it <= max_levels and not target_file.exists():
        logging.debug(f"Checking {target_file}")
        current_dir = current_dir.parent
        target_file = current_dir / file_name
        it += 1

    if target_file.exists():
        return target_file
    raise FileNotFoundError(f"File '{file_name}' not found in parent directories.")


@acache
async def asearch_parents_for_file(
    file_name: "PathType",
    max_levels=3,
    cwd: "PathType | None" = None,
) -> "PathLike":
    """Search parent directories for a file."""
    if TYPE_CHECKING:
        from asyncio.threads import to_thread
    else:
        to_thread = smart_import("asyncio.threads.to_thread")
    return await to_thread(search_parents_for_file, file_name, max_levels, cwd)


async def asearch_children_for_file(
    file_name: "PathType",
    max_levels=3,
    cwd: "PathType | None" = None,
) -> "PathLike":
    """Search parent directories for a file."""
    if TYPE_CHECKING:
        from asyncio.threads import to_thread
    else:
        to_thread = smart_import("asyncio.threads.to_thread")
    return await to_thread(search_children_for_file, file_name, max_levels, cwd)


def search_children_for_file(
    file_name: "PathType",
    max_levels=3,
    cwd: "PathType | None" = None,
) -> "PathLike":
    """Search parent directories for a file."""
    if TYPE_CHECKING:
        from typing import cast
    else:
        cast = smart_import("typing.cast")
    file_name = PathLike(file_name)
    file_name = file_name.name if file_name.is_absolute() else file_name
    logging.debug(f"Searching for {file_name} in child directories of {cwd}")
    current_dir = PathLike(cwd) if cwd else Path.cwd()
    it = 0
    visited = set()
    target_file = current_dir / file_name
    q = [current_dir]
    while it <= max_levels and not target_file.exists() and q:
        current_dir = q.pop(0)
        visited.add(current_dir)
        logging.debug(f"Checking {current_dir}")
        for child in current_dir.iterdir():
            if child not in visited:
                if child.is_dir():
                    q.append(child)
                elif child.name == file_name:
                    target_file = child
                    break
        it += 1
    if target_file.exists():
        return cast("PathLike", target_file)
    raise FileNotFoundError(f"File '{file_name}' not found in parent directories.")
