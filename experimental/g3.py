import ast
import importlib
import logging
from pathlib import Path
from typing import Dict, Set, Optional, Any, List
import networkx as nx
from collections import defaultdict
from dataclasses import dataclass, field
from rich.console import Console
from rich.table import Table

console = Console()

# Setting up logging
logging.basicConfig(level=logging.DEBUG)


# Dataclass for ContentT to enable attribute access for graph nodes
@dataclass
class ContentT:
    functions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    classes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    docs: Optional[str] = None
    signature: Optional[str] = None
    code: Optional[str] = None
    imports: List[str] = field(default_factory=list)


# Function to extract node information from Python files
def extract_node_info(
    file_path: Path, include_docs=False, include_signatures=False, include_code=False
) -> Optional[ContentT]:
    with file_path.open("r", encoding="utf-8") as f:
        source_code = f.read()
    try:
        tree = ast.parse(source_code)
    except (SyntaxError, UnicodeDecodeError, ValueError):
        return None

    imports, functions, classes = [], {}, {}
    node_contents = ContentT(
        functions=functions, classes=classes, docs=None, signature=None, code=None, imports=imports
    )

    if include_docs:
        module_doc = ast.get_docstring(tree)
        if module_doc:
            node_contents.docs = module_doc

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module if node.module else ""
            imports.append(module)
        elif isinstance(node, ast.FunctionDef):
            func_name = node.name
            func_doc = ast.get_docstring(node) if include_docs else None
            args = [arg.arg for arg in node.args.args]
            functions[func_name] = {
                "docs": func_doc,
                "args": args,
            }
        elif isinstance(node, ast.ClassDef):
            class_name = node.name
            class_doc = ast.get_docstring(node) if include_docs else None
            methods = {}
            for body_item in node.body:
                if isinstance(body_item, ast.FunctionDef):
                    method_name = body_item.name
                    method_doc = ast.get_docstring(body_item) if include_docs else None
                    args = [arg.arg for arg in body_item.args.args]
                    methods[method_name] = {
                        "docs": method_doc,
                        "args": args,
                    }
            classes[class_name] = {
                "docs": class_doc,
                "methods": methods,
            }

    node_contents.imports = imports
    node_contents.functions = functions
    node_contents.classes = classes
    return node_contents


def isexcluded(path: Path, allow_site_packages=False) -> bool:
    EXCLUDED_DIRS = {"site-packages", "vendor", "venv", ".venv", "env", ".env"}
    if allow_site_packages and "site-packages" in path.parts:
        return False
    return any(excluded in path.parts for excluded in EXCLUDED_DIRS)


# Build the dependency graph
def build_dependency_graph(
    directory_or_file: Path | str,
    include_site_packages: bool = False,
    include_docs: bool = False,
    include_signatures: bool = False,
    include_code: bool = False,
) -> Dict:
    if isinstance(directory_or_file, str):
        try:
            directory_path = Path(importlib.util.find_spec(directory_or_file).origin).parent
        except AttributeError:
            directory_path = Path(directory_or_file)
    else:
        directory_path = directory_or_file
    directory_path = directory_path.resolve()
    paths = list(directory_path.rglob("*.py"))

    module_nodes: Dict[str, ContentT] = {"root": ContentT(imports=[], functions={}, classes={})}
    adjacency_list = defaultdict(set)
    reverse_adjacency_list = defaultdict(set)
    broken_imports = defaultdict(set)

    for file_path in paths:
        if isexcluded(file_path, allow_site_packages=include_site_packages):
            logging.debug(f"Skipping {file_path}")
            continue

        node_info = extract_node_info(
            file_path, include_docs=include_docs, include_signatures=include_signatures, include_code=include_code
        )
        if node_info is None:
            continue

        relative_path = file_path.relative_to(directory_path)
        parts = relative_path.with_suffix("").parts
        module_name = ".".join(parts) if relative_path.name != "__init__.py" else ".".join(parts[:-1])
        parent_module_name = ".".join(parts[:-1]) if len(parts) > 1 else "root"

        module_nodes[module_name] = ContentT(
            functions=node_info.functions,
            classes=node_info.classes,
            docs=node_info.docs,
            signature=node_info.signature,
            code=node_info.code,
            imports=node_info.imports,
        )

        adjacency_list[parent_module_name].add(module_name)
        adjacency_list[module_name] = set()
        reverse_adjacency_list[module_name].add(parent_module_name)

        for imp in node_info.imports:
            adjacency_list[module_name].add(imp)
            reverse_adjacency_list[imp].add(module_name)
            if imp not in module_nodes:
                module_nodes[imp] = ContentT(imports=[])
            if not attempt_import(imp):
                broken_imports[imp].add(file_path.as_posix())

    return {
        "module_nodes": module_nodes,
        "adjacency_list": adjacency_list,
        "reverse_adjacency_list": reverse_adjacency_list,
        "broken_imports": broken_imports,
    }


# Attempt importing a module by name
def attempt_import(module_name: str) -> bool:
    if not module_name:
        return False
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


# Compute statistics for the dependency graph
def get_stats(
    module_nodes: Dict[str, ContentT], adjacency_list: Dict[str, Set[str]], reverse_adjacency_list: Dict[str, Set[str]]
) -> Dict:
    num_modules = len(module_nodes)
    num_imports = sum(len(node.imports) for node in module_nodes.values())
    num_functions = sum(len(node.functions) for node in module_nodes.values())
    num_classes = sum(len(node.classes) for node in module_nodes.values())

    G = nx.DiGraph()
    for node, neighbors in adjacency_list.items():
        for neighbor in neighbors:
            G.add_edge(node, neighbor)

    for node in module_nodes:
        if node not in G:
            G.add_node(node)

    try:
        pg = nx.pagerank(G)
    except Exception as e:
        logging.error(f"PageRank computation failed: {e}")
        pg = {node: 0.0 for node in G.nodes()}

    avg_degree = sum(dict(G.degree()).values()) / float(len(G)) if len(G) > 0 else 0
    avg_degree = round(avg_degree, 2)

    scc = list(nx.strongly_connected_components(G))
    scc = sorted(scc, key=len, reverse=True)

    effective_sizes = nx.effective_size(G)

    sizes_with_neighbors = {
        node: {
            "effective_size": effective_sizes.get(node, 0.0),
            "neighbors": len(adjacency_list.get(node, [])) + len(reverse_adjacency_list.get(node, [])),
            "pagerank": pg.get(node, 0.0),
        }
        for node in adjacency_list
    }

    size_importance = sorted(sizes_with_neighbors.items(), key=lambda x: x[1]["pagerank"], reverse=True)

    return {
        "num_modules": num_modules,
        "num_imports": num_imports,
        "num_functions": num_functions,
        "num_classes": num_classes,
        "avg_degree": avg_degree,
        "scc": scc,
        "size_importance": size_importance,
    }


# Display functions
def display_stats(stats, exclude: Set[str] = None) -> None:
    exclude = exclude or set()
    title = "Dependency Graph Statistics"
    console.print(f"\n[bold light_goldenrod2]{title}[/bold light_goldenrod2]\n")
    for key, value in stats.items():
        if key in exclude or key in {"pagerank", "scc", "sizes"}:
            continue
        if isinstance(value, list) and value:
            console.print(f"[bold]{key}[/bold]")
            table = Table(title=key, style="light_goldenrod2")
            _, first_dict = value[0]
            for column in first_dict.keys():
                table.add_column(column.replace("_", " ").capitalize())
            table.add_column("Node")
            for node, metrics in value[:10]:  # Display top 10 entries
                row = [
                    f"{metrics[col]:.2f}" if isinstance(metrics[col], float) else str(metrics[col])
                    for col in first_dict.keys()
                ]
                row.append(node)
                table.add_row(*row)
            console.print(table)
            console.print("")
        else:
            console.print(f"[bold]{key.capitalize()}[/bold]: {value}\n")


# Main execution with stats display
if __name__ == "__main__":
    graph = build_dependency_graph(
        directory_or_file="requests",
        include_site_packages=True,
        include_docs=False,
        include_signatures=True,
        include_code=False,
    )
    stats = get_stats(
        module_nodes=graph["module_nodes"],
        adjacency_list=graph["adjacency_list"],
        reverse_adjacency_list=graph["reverse_adjacency_list"],
    )
    display_stats(stats)
