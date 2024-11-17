
import importlib
import sys
from itertools import chain
from pathlib import Path

import rich_click as click
from more_itertools import flatten, ilen, unique
from rich.console import Console
from typing_extensions import TypeVar

from mbpy.commands import run
from mbpy.graph import build_dependency_graph
from mbpy.utils.collections import cat, equals, filterfalse, nonzero, takewhile

console = Console()

T = TypeVar("T")


def main(
    path_or_module: str| Path = ".", dry_run: bool = False
):
    # Build dependency graph and adjacency list
    path = Path(str(path_or_module))
    if not path.exists():
        mod = importlib.import_module(str(path))
        walk_broken_options(mod.__name__, dry_run)
    result = build_dependency_graph(
        path,
        include_site_packages=False,
        include_docs=False,
        include_signatures=False,
        include_code=False,
    )
    root = result.root
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
            if (walk_broken_options(imp,dry_run)):
                console.print(f"{', '.join(file_paths)} are no longer broken by {imp}.", style="light_sea_green")
                remaining_broken.update(
                    nonzero({k: v - 1 for k, v in remaining_broken.items() if k in file_paths} or {imp: 0})
                )

def walk_broken_options(imp, dry_run):
        modname = imp.split(".")[0] if len(imp.split(".")) > 1 else imp
        console.print(f"\nModule: {modname}")
        from mbpy.mpip import PackageInfo, find_and_sort
        results: list[PackageInfo] = find_and_sort(modname, include="releases")
        github_urls = filterfalse({result.get("github_url") for result in results if result.get("github_url")})
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
            
            
            result = run(f"pip install {modname}=={version}",show=False)
            if "ERROR" in result:
                console.print(f" Failed to install {modname}=={version}. Trying next version down", style="red")
                continue
            console.print(f" - Installed: {modname}=={version}!", style="light_sea_green")
            return True
        console.print(" - Exhausted all versions.", style="red")
        for url in github_urls:
            console.print(f" - Found github url: {url}")
            run(f"gh repo clone {url}")
            run(f"cd {url.split('/')[-1] if url else '.'}")
            run("pip install -e .")
            run("cd ..")
            console.print(f" - Installed: {modname} from github to {url.split('/')[-1]}", style="light_sea_green")

        console.print("Exhausted all versions and no urls found.", style="red")
        return False

if __name__ == "__main__":
    sys.exit(main())
