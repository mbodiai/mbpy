
import importlib
from pathlib import Path
import sys

import rich_click as click
from rich.console import Console

from mbpy.commands import run
from mbpy.graph import build_dependency_graph, display_stats, get_stats, print_tree
from mbpy.mpip import PackageInfo, find_and_sort

console = Console()

def main(
    path: str| Path = ".", dry_run: bool = False
):
    # Build dependency graph and adjacency list
    path = Path(str(path)).resolve()
    result = build_dependency_graph(
        path,
        include_site_packages=False,
        include_docs=False,
        include_signatures=False,
        include_code=False,
    )
    root = result.root_node
    broken = result.broken_imports
    module_nodes = result.module_nodes
    for broken_module in broken.copy():
        if broken_module in module_nodes and module_nodes[broken_module].filepath and str(root.filepath) in module_nodes[broken_module].filepath.absolute().as_posix():
            console.print(f"Removing {broken_module} from broken imports")
            del broken[broken_module]

    # Display broken imports with file paths
    if broken:
        console.print("\n[bold red]Broken Imports:[/bold red]")
        for imp, file_paths in broken.items():
            installed = False
            modname = imp.split(".")[0] if len(imp.split(".")) > 1 else imp
            console.print(f"\nModule: {modname}")
            for path in file_paths:
                console.print(f" - Imported by: {path}")
            results = find_and_sort(modname, include="releases")
            if not results:
                console.print(f" - No results found for {modname}", style="red")
                continue
            result = results[0]
            if not result.get("releases"):
                console.print(f" - No releases found for {modname}", style="red")
                continue
            for release in result["releases"]:
                version = next(iter(release.keys()))
                if not version:
                    continue
                if dry_run:
                    console.print(f" - Would install: {modname}=={version}")
                    installed = True
                    break
               
                
                result = run(f"pip install {modname}=={version}",show=False)
                if "ERROR" in result:
                    console.print(f" Failed to install {modname}=={version}. Trying next version down", style="red")
                    continue
                installed = True
                console.print(f" - Installed: {modname}=={version}. Paths {','.join(list(file_paths))} should now be resolved.", style="light_sea_green")
                break
            if not installed:
                console.print("Exhausted all versions", style="red")

if __name__ == "__main__":
    sys.exit(main())
