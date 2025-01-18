import asyncio
import concurrent.futures
import importlib
import sys
from itertools import chain
from pathlib import Path
from typing import TypeVar

from more_itertools import flatten, ilen, unique
from rich.console import Console

from mbpy.cmd import run
from mbpy.pkg.graph import build_dependency_graph
from mbpy.collect import cat, equals, filterfalse, nonzero, takewhile
from mbpy.import_utils import smart_import
console = Console()

T = TypeVar("T")


async def main(
    path_or_module: str| Path = ".", dry_run: bool = False,
):
    # Build dependency graph and adjacency list
    Path = smart_import("pathlib.Path")
    inspect = smart_import("inspect")
    importlib = smart_import("importlib")
    first_true = smart_import("more_itertools.first_true")
    ModuleNode = smart_import("mbpy.pkg.graph.ModuleNode")

    path = Path(path_or_module).resolve()
    if not path.exists():
        # Assume it's a module name
        try:
            path = Path(
                inspect.getabsfile(importlib.import_module(path_or_module)))
        except ImportError:
            raise FileNotFoundError(
                f"File or module '{path_or_module}' not found.")
    result = await build_dependency_graph(path)
    root_node = first_true(result.module_nodes.values(), pred=lambda x: x.name == "root", default=ModuleNode())
    module_nodes = result.module_nodes
    adjacency_list = result.adjacency_list
    reverse_adjacency_list = result.reverse_adjacency_list
    broken = result.broken_imports


    module_nodes = result.module_nodes
    for broken_module in broken.copy():
        if broken_module in module_nodes and module_nodes[broken_module].filepath and str(root) in module_nodes[broken_module].filepath.absolute().as_posix():
            console.print(f"Removing {broken_module} from broken imports")
            del broken[broken_module]

    # Display broken imports with file paths
    remaining_broken = {k: ilen(takewhile(equals(k), cat(broken.values()))) for k in flatten(unique(chain(broken.values())))}
    if broken:
        console.print("\n[bold red]Broken Imports:[/bold red]")
        for imp, file_paths in broken.items():
            if (await walk_broken_options(imp,dry_run)):
                console.print(f"{', '.join(file_paths)} are no longer broken by {imp}.", style="light_sea_green")
                remaining_broken.update(
                    nonzero({k: v - 1 for k, v in remaining_broken.items() if k in file_paths} or {imp: 0}),
                )


async def walk_broken_options(imp, dry_run) -> bool:
    modname = imp.split(".")[0] if len(imp.split(".")) > 1 else imp
    console.print(f"\nModule: {modname}")
    from mbpy.pkg.dependency import PyPackageInfo as PackageInfo
    from mbpy.pkg.pypi import find_and_sort
    from mbpy.cmd import arun
    results: list[PackageInfo] = await find_and_sort(modname, include="all", verbosity=2)
    from rich.pretty import pprint
    pprint(results)
    github_urls = [result.get("github_url") for result in results if result.get("github_url")]
    if not results:
        console.print(f" - No results found for {modname}", style="red")
        return False
    result = results[0]
    if not result.get("releases"):
        console.print(f" - No releases found for {modname}", style="red")

    for release in result.get("releases", []) or []:
        version = next(iter(release.keys()))
        if dry_run:
            console.print(f" - Would install: {modname}=={version}")
            return True


        result = await arun(f"pip install {modname}=={version}",show=False)
        if "ERROR" in result:
            console.print(f" Failed to install {modname}=={version}. Trying next version down", style="red")
            continue
        console.print(f" - Installed: {modname}=={version}!", style="light_sea_green")
        return True
    console.print(" - Exhausted all versions.", style="red")
    for url in github_urls:
        console.print(f" - Found github url: {url}")
        with asyncio.runners.run(None, run, f"gh repo view {url}") as result:

            run(f"gh repo clone {url}")
            run(f"cd {url.split('/')[-1] if url else '.'}")
            run("pip install -e .")
            run("cd ..")
            console.print(f" - Installed: {modname} from github to {url.split('/')[-1]}", style="light_sea_green")

    console.print("Exhausted all versions and no urls found.", style="red")
    return False

if __name__ == "__main__":
    sys.exit(all(asyncio.as_completed([main(f) for f in Path.cwd().rglob("*.py")])))
