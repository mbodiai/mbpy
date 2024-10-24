
import importlib
import sys

import rich_click as click
from rich.console import Console

from mbpy.graph import build_dependency_graph, display_stats, get_stats, print_tree
from mbpy.mpip import PackageInfo, find_and_sort
from mbpy.cli import install_command
console = Console()


@click.command("repair")
@click.argument("path", default=".")
def main(
    path: str = ".",
):
    # Build dependency graph and adjacency list
    result = build_dependency_graph(
        path,
        include_site_packages=False,
        include_docs=False,
        include_signatures=False,
        include_code=False,
    )
    *other, broken, _ = result


    # Display broken imports with file paths
    if broken:
        console.print("\n[bold red]Broken Imports:[/bold red]")
        for imp, file_paths in broken.items():
            console.print(f"\nModule: {imp}")
            for path in file_paths:
                console.print(f" - Imported by: {path}")
            result = find_and_sort(imp, include="releases")[0]
            modname = imp
            for release in result["releases"]:

                version = next(iter(release.keys()))
                try:
                   result = install_command(f"{modname}=={version}")

                except  (ModuleNotFoundError, ImportError, AttributeError, NameError):
                    console.print(f" Failed to install {modname}=={version}. Trying next version down", style="red")
                    continue
                console.print(f" - Installed: {modname}=={version}. Paths {file_paths} should now be resolved.", style="light_sea_green")
                break
            console.print("Exhausted all versions", style="red")

if __name__ == "__main__":
    sys.exit(main())
