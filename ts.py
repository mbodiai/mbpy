import os
from pathlib import Path
from collections import deque
from tree_sitter import Language, Parser
import rich_click as click
from rich.console import Console
from rich.table import Table

console = Console()

# Configure Tree-sitter
LANGUAGE_PATH = Path("~/tree-sitter-languages/python.so").expanduser()
if not LANGUAGE_PATH.exists():
    console.print(f"[red]Error: Tree-sitter library not found at {LANGUAGE_PATH}[/red]")


PYTHON_LANGUAGE = Language(str(LANGUAGE_PATH), "python")
parser = Parser()
parser.set_language(PYTHON_LANGUAGE)

# Global State
STATE = {
    "graph": {},  # Full graph structure
    "history": [],  # Current traversal path
    "current_nodes": None,  # Current siblings/children
    "bookmarks": {},  # Named bookmarks
    "forks": {},  # Parallel exploration paths
}


def parse_file(file_path):
    """
    Parse the file and return its structure as a graph.
    """
    with open(file_path, "rb") as f:
        code = f.read()

    tree = parser.parse(code)
    root_node = tree.root_node

    graph = {}
    queue = deque([(None, root_node)])  # (Parent, Node)

    while queue:
        parent, node = queue.popleft()
        if 

        # Collect node information
        try:
            node_name = code[node.start_byte:node.end_byte].decode("utf-8", errors="replace").split("(")[0]
        except Exception as e:
            console.print(f"[red]Error decoding node in file {file_path}: {e}[/red]")
            node_name = f"Unnamed-{id(node)}"
        node_type = node.type
        node_info = {
            "type": node_type,
            "name": node_name.strip() or f"Unnamed-{id(node)}",
            "start_line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
            "children": [],
        }

        if parent:
            graph[parent]["children"].append(node_info["name"])
        graph[node_info["name"]] = node_info

        # Traverse children
        for child in node.children:
            queue.append((node_info["name"], child))

    return graph


@click.group()
def cli():
    """
    Tree-sitter Codebase Explorer with Fork Tracking and Navigation.
    """
    pass



def show_context():
    """
    Show the current context (siblings/children).
    """
    current_nodes = STATE["current_nodes"]
    if not current_nodes:
        # console.print("[yellow]No nodes to display in the current context.[/yellow]")
        return

    table = Table(title="Current Context")
    table.add_column("Node Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Start Line", style="green")
    table.add_column("End Line", style="green")

    for node_name, node_info in current_nodes.items():
        if node_info["type"] and node_name and node_info["start_line"] and node_info["end_line"]:
            table.add_row(
                node_name,
                node_info["type"],
                str(node_info["start_line"]),
                str(node_info["end_line"]),
            )

    from rich import inspect
    inspect(table)


@cli.command()
@click.argument("node_name", type=str)
def traverse(node_name):
    """
    Traverse into a specific node.

    Example:
        python explorer.py traverse "node_name"
    """
    if node_name not in STATE["current_nodes"]:
        console.print(f"[red]Node {node_name} not found in the current context.[/red]")
        return

    STATE["history"].append(node_name)
    STATE["current_nodes"] = {
        child: STATE["graph"][child] for child in STATE["graph"][node_name]["children"]
    }
    console.print(f"[blue]Moved into node:[/blue] {node_name}")
    show_context()


@cli.command()
def step_out():
    """
    Step out to the parent node.

    Example:
        python explorer.py step-out
    """
    if not STATE["history"]:
        # console.print("[yellow]Already at the root level.[/yellow]")
        return

    STATE["history"].pop()
    parent_name = STATE["history"][-1] if STATE["history"] else None
    if parent_name:
        STATE["current_nodes"] = {
            child: STATE["graph"][child] for child in STATE["graph"][parent_name]["children"]
        }
    else:
        # Back to root
        STATE["current_nodes"] = {
            node_name: node_info
            for node_name, node_info in STATE["graph"].items()
            if not node_info["children"]
        }

    console.print(f"[blue]Moved out to parent.[/blue]")
    show_context()


@cli.command()
@click.argument("name", type=str)
def bookmark(name):
    """
    Save the current node as a bookmark.
    """
    if not STATE["history"]:
        # console.print("[yellow]No node to bookmark (currently at root).[/yellow]")
        return

    current_node = STATE["history"][-1]
    STATE["bookmarks"][name] = current_node
    console.print(f"[green]Bookmark added:[/green] {name} -> {current_node}")


@cli.command()
def view_bookmarks():
    """
    Show all bookmarks.
    """
    if not STATE["bookmarks"]:
        # console.print("[yellow]No bookmarks available.[/yellow]")
        return

    table = Table(title="Bookmarks")
    table.add_column("Name", style="cyan")
    table.add_column("Node", style="magenta")

    for name, node in STATE["bookmarks"].items():
        table.add_row(name, node)

    console.print(table)


@cli.command()
@click.argument("name", type=str)
def fork(name):
    """
    Fork the current traversal path.
    """
    if not STATE["history"]:
        # console.print("[yellow]Cannot fork at the root level.[/yellow]")
        return

    STATE["forks"][name] = list(STATE["history"])
    console.print(f"[green]Fork created:[/green] {name}")


@cli.command()
def view_forks():
    """
    Show all active forks.
    """
    if not STATE["forks"]:
        # console.print("[yellow]No forks available.[/yellow]")
        return

    table = Table(title="Forks")
    table.add_column("Name", style="cyan")
    table.add_column("Path", style="magenta")

    for name, path in STATE["forks"].items():
        table.add_row(name, " -> ".join(path))

    console.print(table)



def switch_to_fork(name):
    """
    Switch to a forked traversal path.
    """
    if name not in STATE["forks"]:
        console.print(f"[red]Fork {name} not found.[/red]")
        return

    STATE["history"] = STATE["forks"][name]
    last_node = STATE["history"][-1]
    STATE["current_nodes"] = {
        child: STATE["graph"][child] for child in STATE["graph"][last_node]["children"]
    }
    console.print(f"[blue]Switched to fork:[/blue] {name}")
    show_context()


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
def start(file_path):
    """
    Parse a Python file or directory and initialize the graph for navigation.

    Example:
        python explorer.py start path/to/file_or_directory
    """
    file_path = Path(file_path).expanduser()

    if file_path.is_dir():
        console.print(f"[green]Parsing directory:[/green] {file_path}")
        # Recursively find all Python files in the directory
        python_files = list(file_path.rglob("*.py"))
        if not python_files:
            console.print("[yellow]No Python files found in the directory.[/yellow]")
            return

        console.print(f"[green]Found {len(python_files)} Python files. Parsing...[/green]")
        for py_file in python_files:
            console.print(f"[blue]Parsing file: {py_file}[/blue]")
            graph = parse_file(py_file)
            STATE["graph"].update(graph)  # Merge into the global graph
    elif file_path.is_file():
        console.print(f"[green]Parsing file:[/green] {file_path}")
        graph = parse_file(file_path)
        STATE["graph"] = graph
    else:
        console.print("[red]Invalid path provided.[/red]")
        return

    # Initialize the context with top-level nodes
    STATE["current_nodes"] = {
        node_name: node_info for node_name, node_info in STATE["graph"].items() if not node_info["children"]
    }
    show_context()


if __name__ == "__main__":
    cli()
