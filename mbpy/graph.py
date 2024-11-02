
import ast
from collections.abc import Iterable
import contextlib
from dataclasses import dataclass, field
import importlib.util
import inspect
import sys
from collections import defaultdict
from functools import partial
from pathlib import Path
from types import FunctionType, MappingProxyType
from typing import TYPE_CHECKING, Dict, NamedTuple, Tuple, TypeVar, Union, Unpack, _type_check, dataclass_transform, overload
from weakref import ref

# Import NetworkX for graph representation
from more_itertools import first, first_true
import networkx as nx
import numpy as np
import rich_click as click
from rich.console import Console
from rich.pretty import Pretty
from typing_extensions import (
    Annotated,
    Generic,
    Literal,
    NotRequired,
    ParamSpec,
    Required,
    TypeVarTuple,
    TypedDict,
    _caller,
    _TypedDictMeta,
    get_args,
    get_origin,
)

console = Console()
class ContentT(TypedDict):
    functions: Dict[str, Dict[str, str | list[str]]] | None
    classes: Dict[str, Dict[str, str | list[str]]] | None
    docs: str | None
    signature: str | MappingProxyType[str, type] | None
    code: str | None

class TD(TypedDict):
    name: str
    parent: Union["ref[Node]" , None]
    children: Dict[str, "Node"]
    imports: list[str]
    contents: ContentT
    importance: float
    filepath: Path | None
@dataclass()
class Node(dict):
  
    @overload
    def __getitem__(self, key: Literal["name"]) -> str:
        ...
    @overload
    def __getitem__(self, key: Literal["parent"]) -> Union["ref[Node]" , None]:
        ...
    @overload
    def __getitem__(self, key: Literal["children"]) -> Dict[str, "Node"]:
        ...
    @overload
    def __getitem__(self, key: Literal["imports"]) -> list[str]:
        ...
    @overload
    def __getitem__(self, key: Literal["contents"]) -> ContentT:
        ...
    
    def __getitem__(self, key):
        return super().__getitem__(key)

    name: str
    parent: Union["ref[Node]" , None] = None
    children: Dict[str, "Node"] = field(default_factory=dict)
    imports: list[str] = field(default_factory=list)
    contents: ContentT = field(default_factory=dict)
    importance: float = 1.0
    filepath: Path | None = None

    def to_graph(self, g=None) -> nx.DiGraph:
        """Recursively adds nodes and edges to a NetworkX graph."""
        if g is None:
            g = nx.DiGraph()
        g.add_node(self.name)
        for imp in self.imports:
            g.add_edge(self.name, imp)
        for child in self.children.values():
            child.to_graph(g)
        return g


def extract_node_info(file_path, include_docs=False, include_signatures=False, include_code=False):
    """Extracts imports, function definitions, class definitions, docstrings, and signatures from a Python file."""
    with Path(file_path).open('r', encoding='utf-8') as f:
        source_code = f.read()
    try:
        tree = ast.parse(source_code)
    except (SyntaxError, UnicodeDecodeError, ValueError, TypeError,AttributeError):
        return None  # Skip files that can't be parsed

    imports = []
    functions = {}
    classes = {}
    node_contents = {
        'imports': imports,
        'functions': functions,
        'classes': classes,
    }

    if include_docs:
        module_doc = ast.get_docstring(tree)
        if module_doc:
            node_contents['docs'] = module_doc
    if include_signatures:
        signature = None
        with contextlib.suppress(Exception):
            signature = inspect.signature(ast.parse(source_code)).parameters
        node_contents['signature'] = signature


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
                'docs': func_doc if include_docs else None,
                'args': args,
            }
            if include_signatures:
                signature[func_name] = f"{func_name}({', '.join(args)})"
            if include_code:
                start = node.lineno - 1
                end = node.end_lineno
                func_code = source_code.split('\n')[start:end]
                functions[func_name]['code'] = '\n'.join(func_code)
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
                        'docs': method_doc if include_docs else None,
                        'args': args,
                        # 'code' is optional
                    }
                    if include_signatures:
                        signature[method_name] = f"{method_name}({', '.join(args)})"
                    if include_code:
                        start = body_item.lineno - 1
                        end = body_item.end_lineno
                        method_code = source_code.split('\n')[start:end]
                        methods[method_name]['code'] = '\n'.join(method_code)
            classes[class_name] = {
                'docs': class_doc if include_docs else None,
                'methods': methods,
                # 'code' is optional
            }
            if include_code:
                start = node.lineno - 1
                end = node.end_lineno
                class_code = source_code.split('\n')[start:end]
                classes[class_name]['code'] = '\n'.join(class_code)
            


    return node_contents

def attempt_import(module_name):
    """Attempts to import a module by name. Returns True if successful, False otherwise."""
    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except (ModuleNotFoundError, ValueError, ImportError,NameError,RuntimeError):
        return False



class GraphDict(TypedDict, total=False):
    root_node: Node
    module_nodes: dict[str, Node]
    adjacency_list: dict[str, set[str]]
    reverse_adjacency_list: dict[str, set[str]]
    broken_imports: dict[str, set[str]]
    graph: nx.DiGraph
    
    

class Graph(NamedTuple):
    root_node: Node
    module_nodes: dict[str, Node]
    adjacency_list: dict[str, set[str]]
    reverse_adjacency_list: dict[str, set[str]]
    broken_imports: dict[str, set[str]]
    graph: nx.DiGraph
    
    def __setitem__(self, key, value):
        return self.__setattr__(key, value)
    
    def __getitem__(self, key):
        return self.__getattribute__(key)
    
    def asdict(self) -> GraphDict:
        return {
            'root_node': self.root_node,
            'module_nodes': self.module_nodes,
            'adjacency_list': self.adjacency_list,
            'reverse_adjacency_list': self.reverse_adjacency_list,
            'broken_imports': self.broken_imports,
            'graph': self.graph,
        }


    
def build_dependency_graph(
    directory_or_file: Path | str,
    include_site_packages: bool = False,
    include_docs: bool = False,
    include_signatures: bool = False,
    include_code: bool = False,
)-> Graph:
    directory_path = Path(directory_or_file)
   

    directory_path = directory_path.parent.resolve() if directory_path.is_file() else directory_path.resolve()
    paths = [directory_path] if directory_path.is_file() else list(directory_path.rglob('*.py'))
    root_node = Node('root', filepath=directory_path)
    module_nodes = {'root': root_node}
    adjacency_list = defaultdict(set)
    reverse_adjacency_list = defaultdict(set)  # For getting modules that import a given module
    broken_imports = defaultdict(set)  # Map broken imports to sets of file paths

    for file_path in paths:
        # Skip site-packages and vendor directories if not included
        if not include_site_packages and (("site-packages" in file_path.parts) or ("vendor" in file_path.parts)):
            continue
        try:
            # Compute module's import path
            relative_path = file_path.relative_to(directory_path)
            parts = relative_path.with_suffix('').parts  # Remove '.py' suffix
            module_name = '.'.join(parts)
            parent_module_name = '.'.join(parts[:-1]) if len(parts) > 1 else 'root'
            parent_node = module_nodes.get(parent_module_name, root_node)

            # Extract node information
            node_info = extract_node_info(
                file_path,
                include_docs=include_docs,
                include_signatures=include_signatures,
                include_code=include_code,
            )
            if node_info is None:
                continue  # Skip files that couldn't be parsed

            # Create or get the module node
            module_node = Node(module_name, parent=parent_node, filepath=file_path)
            module_node.imports = node_info.get('imports', [])
            module_node.contents['functions'] = node_info.get('functions', {})
            module_node.contents['classes'] = node_info.get('classes', {})
            # Include optional fields if they exist
            if include_docs and 'docs' in node_info:
                module_node.contents['docs'] = node_info['docs']
            if include_signatures and 'signatures' in node_info:
                module_node.contents['signatures'] = node_info['signatures']
            if include_code and 'code' in node_info:
                module_node.contents['code'] = node_info['code']

            module_nodes[module_name] = module_node

            # Add to parent's children
            parent_node.children[module_name] = module_node

            # Update adjacency list for PageRank
            for imp in module_node.imports:
                adjacency_list[module_name].add(imp)
                reverse_adjacency_list[imp].add(module_name)
                # Initialize the importance of imported modules if not already
                if imp not in module_nodes:
                    module_nodes[imp] = Node(imp)

                # Update importance
                module_nodes[imp].importance += module_node.importance / max(len(module_node.imports), 1)

                # Attempt to import the module
                if not attempt_import(imp):
                    modname = imp.split(".")[0] if len(imp.split(".")) > 1 else imp
                    # Add the file path to the broken import's set
                    broken_imports.setdefault(modname, set()).add(file_path.as_posix())

        except (SyntaxError, UnicodeDecodeError, ValueError):
            continue
    return Graph(**{
        'root_node': root_node,
        'module_nodes': module_nodes,
        'adjacency_list': adjacency_list,
        'reverse_adjacency_list': reverse_adjacency_list,
        'broken_imports': broken_imports,
        'graph': root_node.to_graph(),
    })

def print_tree(node: Node, level=0, include_docs=False, include_signatures=False, include_code=False):
    if level == 0:
        console.print("[bold light_goldenrod2]Dependency Graph:[/bold light_goldenrod2]")
    indent = '  ' * level

    console.print(f"{indent}[bold light_goldenrod2]{node.name}[/bold light_goldenrod2]:")
    if node.imports:
        console.print(f"{indent}  Imports: {node.imports}")
    if node.contents.get('functions') or node.contents.get('classes'):
        console.print(f"{indent}  Contents:")
        for func_name, func_info in node.contents.get('functions', {}).items():
            console.print(f"{indent}    Function: {func_name}")
            if include_signatures:
                signature = node.contents.get('signatures', {}).get(func_name, '')
                if signature:
                    console.print(f"{indent}      Signature: {signature}")
            if include_docs and func_info.get('docs'):
                console.print(f"{indent}      Docstring: {func_info['docs']}")
        for class_name, class_info in node.contents.get('classes', {}).items():
            console.print(f"{indent}    Class: {class_name}")
            if include_docs and class_info.get('docs'):
                console.print(f"{indent}      Docstring: {class_info['docs']}")
            for method_name, method_info in class_info.get('methods', {}).items():
                console.print(f"{indent}      Method: {method_name}")
                if include_signatures:
                    signature = node.contents.get('signatures', {}).get(method_name, '')
                    if signature:
                        console.print(f"{indent}        Signature: {signature}")
                if include_docs and method_info.get('docs'):
                    console.print(f"{indent}        Docstring: {method_info['docs']}")
    if include_code and node.contents.get('code'):
        console.print(f"{indent}  Code:\n{node.contents['code']}")
    for child_node in node.children.values():
        print_tree(
            child_node,
            level=level+1,
            include_docs=include_docs,
            include_signatures=include_signatures,
            include_code=include_code,
        )


class GraphStats(TypedDict):
    num_modules: int
    num_imports: int
    num_functions: int
    num_classes: int
    avg_degree: float
    scc: list[set[str]]
    importance_scores: dict[str, float]
    effective_sizes: dict[str, float]
    sizes: dict[str, float]
    pagerank: dict[str, float]
    
    
def get_stats(module_nodes: Dict[str, Node] | Iterable[Node], adjacency_list: dict[str, set[str]], reverse_adjacency_list: dict[str, set[str]]) -> GraphStats:
    """Computes statistics for the dependency graph."""
    module_nodes = {node.name: node for node in module_nodes} if not isinstance(module_nodes, Dict) else module_nodes
    num_modules = len(module_nodes)
    num_imports = sum(len(node.imports) for node in module_nodes.values())
    num_functions = sum(len(node.contents.get('functions', {})) for node in module_nodes.values())
    num_classes = sum(len(node.contents.get('classes', {})) for node in module_nodes.values())
     # Apply PageRank to determine module importance
    importance_scores = {node_name: node.importance for node_name, node in module_nodes.items()}
    total_importance = sum(importance_scores.values())
    # Normalize the importance scores
    if total_importance > 0:
        importance_scores = {node: score / total_importance for node, score in importance_scores.items()}
    else:
        importance_scores = {node: 0 for node in importance_scores}



    G = module_nodes['root'].to_graph()
    pg = nx.algorithms.link_analysis.pagerank_alg.pagerank(G)
    avg_degree = sum(dict(G.degree()).values()) / float(len(G)) if len(G) > 0 else 0

    pg = {k: round(v, 4) for k, v in pg.items()}
    avg_degree = round(avg_degree, 2)

   # Find strongly connected components and rank them by size  
    scc = list(nx.strongly_connected_components(G))  
    # Rank SCCs by number of nodes  
    scc = sorted(scc, key=lambda x: len(x), reverse=True)  
    sizes = nx.effective_size(G)


    sizes_with_neighbors = {  
        node: {  
            "effective_size": sizes[node],  
            "neighbors": len(adjacency_list[node]) + len(reverse_adjacency_list[node]),
            "pagerank": round(pg[node] * G.number_of_edges(), 4)
        }  
        for node in G.nodes()  
    }  

    return {
        'num_modules': num_modules,
        'num_imports': num_imports,
        'num_functions': num_functions,
        'num_classes': num_classes,
        'avg_degree': avg_degree,
        'scc': scc,
        "sizes": sizes,
        "size_importance": sorted(sizes_with_neighbors.items(), key=lambda x: x[1]["effective_size"], reverse=True),
        "pagerank": sorted(pg.items(), key=lambda x: x[1], reverse=True)
    }

from rich.table import Table, Column
def display_stats(stats: GraphStats, exclude: set[str] = None) -> None:
    """Displays statistics for the dependency graph."""
    exclude = exclude or set()
    title = "Dependency Graph Statistics"
    console.print(f"\n[bold light_goldenrod2]{title}[/bold light_goldenrod2]")
    
    for key, value in stats.items():
        if key in exclude or key in ("pagerank",  "scc", "sizes"):
            continue
        console.print(f"{key}")
        if isinstance(value, list):
            v = value[0]
            values = sorted(value, key=lambda x: x[1]["pagerank"], reverse=True)
            table = Table(title=key,style="light_goldenrod2")
            table.add_column("Node")
            for k in v[1].keys():
                table.add_column(k)
            for v in values[:10]:
                table.add_row(v[0], *(str(x) for x in v[1].values()))
            console.print(table)
                


    # Display average degree
    console.print(f"Average Degree: {stats['avg_degree']:.2f}")



        
def display_broken(broken_imports: dict[str, set[str]]) -> None:
    console.print("\n[bold red]Broken Imports:[/bold red]")
    for imp, file_paths in broken_imports.items():
        console.print(f"\nModule: {imp}")
        for path in file_paths:
            console.print(f" - Imported by: {path}")   

def generate(
    directory_file_or_module: str = ".",
    sigs: bool = False,
    docs: bool = False,
    code: bool = False,
    who_imports: bool = False,
    stats: bool = False,
    site_packages: bool = False,
):
    """Build dependency graph and adjacency list."""
    filter_to_module = lambda x: x
    path = Path(directory_file_or_module).resolve()
    if not path.exists():
        # Assume it's a module name
        path = Path.cwd()
        filter_to_module = lambda x: x.name == directory_file_or_module
        filter_includes_module = lambda x: x.name in who_imports(directory_file_or_module, path, site_packages)
    else:
        filter_includes_module = lambda _: True
        filter_to_module = lambda _: True

    result = build_dependency_graph(
        path,
        include_site_packages=site_packages,
        include_docs=docs,
        include_signatures=sigs,
        include_code=code,
    )
    
    
    root_node = result.root_node
    module_nodes = result.module_nodes
    adjacency_list = result.adjacency_list
    reverse_adjacency_list = result.reverse_adjacency_list
    broken_imports = result.broken_imports
    
    root_node = first_true(module_nodes.values(), pred=filter_to_module)

    module_nodes = filter(filter_includes_module, module_nodes.values())
    print_tree(
        root_node,
        include_docs=docs,
        include_signatures=sigs,
        include_code=code,
    )

    # Display statistics if requested
    if stats:
        stats = get_stats(module_nodes, adjacency_list, reverse_adjacency_list)
        display_stats(stats)
    # Display importers if requested
    if who_imports:
        who_imports: FunctionType = sys.modules[__name__].who_imports
        who_imports(directory_file_or_module, path, site_packages=site_packages, show=True)
    # Display broken imports with file paths
    if broken_imports:
        display_broken(broken_imports)
    return result, stats, broken_imports


def who_imports(module_name: str, path: Path | str,*, site_packages: bool, show: bool=False) -> set[str]:
    # Build dependency graph and adjacency list
    path = Path(str(path))
    result = build_dependency_graph(path, include_site_packages=site_packages)
    reverse_adjacency_list = result.reverse_adjacency_list

    # Get modules that import the given module
    importers = reverse_adjacency_list.get(module_name, set())
    if importers and show:
        console.print(f"\n[bold light_goldenrod2]Modules that import '{module_name}':[/bold light_goldenrod2]")
        for importer in importers:
            console.print(f" - {importer}")
    else:
        console.print(f"\n[bold red]No modules found that import '{module_name}'.[/bold red]")
    return importers

def validate_params(func, *args, **kwargs):
    from inspect import signature
    sig = signature(func)
    params = sig.parameters
    args = list(args)
    kwargs_args = {}
    for key, value in kwargs.items():
        if key not in params:
            raise TypeError(f"Unexpected keyword argument '{key}'")

    return args
if __name__ == "__main__":
    if sys.argv[1:]:
        validate_params(generate, *sys.argv[1:])
        generate(*sys.argv[1:])
    generate(stats=True)

