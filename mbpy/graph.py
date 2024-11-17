
import ast
import contextlib
import functools
import importlib.util
import inspect
import logging
import sys
import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from types import FunctionType, MappingProxyType, ModuleType, NoneType, SimpleNamespace, new_class
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generic,
    NamedTuple,
    Optional,
    Self,
    Set,
    Tuple,
    TypeAlias,
    TypeVar,
    Union,
)
from weakref import ref

import networkx as nx

# Import NetworkX for graph representation
from more_itertools import first_true, ilen
from pydantic import BaseModel, Field, model_validator
from rich.console import Console
from rich.table import Table
from typing_extensions import (
    Literal,
    TypedDict,
)

from mbpy import context
from mbpy.utils.collections import compose
T = TypeVar("T")
console = Console()
class ContentT(TypedDict):
    functions: Dict[str, Dict[str, str | list[str]]] | None
    classes: Dict[str, Dict[str, str | list[str]]] | None
    docs: str | None
    signature: str | MappingProxyType[str, type] | None
    code: str | None



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
        with context.suppress(Exception) as e:
            signature = inspect.signature(ast.parse(source_code)).parameters
        if e.exc:
            logging.error(f"Error extracting signatures from '{file_path}': {e.exc}")
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

def attempt_import(module_name) -> bool:
    """Attempts to import a module by name. Returns True if successful, False otherwise."""
    with  context.suppress(Exception) as e:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    if e.exc:
        logging.debug(f"Error importing module '{module_name}': {e.exc}")
    return False







if TYPE_CHECKING:
    dec = dataclass
    ParentT = BaseModel
else:
    dec = lambda x: x
    ParentT = BaseModel



class TreeNode(ParentT, Generic[T]):
    """A tree node with a name, parent, status, importance, and report."""
    name: str = Field(default_factory=compose(str, uuid.uuid4))
    parent: Optional["ref[TreeNode[T]]"] | None = None
    root: Optional["ref[TreeNode[T]]"] | None = None
    status: Literal["waiting", "running", "done"] | None = None
    importance: float = 1.0
    report: str | None = None
    """A report on the status of the subtree."""
    children: Dict[str, "TreeNode[T]"] = Field(default_factory=dict)
    adjacency_list: Dict[str, set[str]] = Field(default_factory=dict)
    reverse_adjacency_list: Dict[str, set[str]] = Field(default_factory=dict)
    nxgraph: nx.DiGraph | None = None
    value: T | None = None
    Type: type[T] | None = None
    
    @model_validator(mode="before")
    @classmethod
    def makerefs(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if "parent" in v:
            v["parent"] = ref(v["parent"])
        if "root" in v:
            v["root"] = ref(v["root"])
        return v

    
    @classmethod
    def from_dict(cls, d: dict, name=None, parent=None) -> "TreeNode":
        return cls(name=name or d.pop("name",None), parent=parent or d.pop("parent",None), **d)
  
    @classmethod
    def __class_getitem__(cls, value_type: type[T]):
        cls.Type = value_type
        return cls
    
    def __setitem__(self, key, value):
        return self.__setattr__(key, value)
 
    def graph(self,g: nx.DiGraph=None) -> nx.DiGraph:
        """Recursively adds nodes and edges to a NetworkX graph."""
        g = g or nx.DiGraph()
        g.add_node(self.name)
       
        for child in self.children.values():
            child.graph(g)
        return g

    class GraphDict(TypedDict):
            name: str
            parent: Optional["ref[TreeNode[T]]"]
            status: Literal["waiting", "running", "done"] | None
            report: str | None
            children: dict[str, "TreeNode[T]"]
            adjacency_list: dict[str, set[str]]
            reverse_adjacency_list: dict[str, set[str]]
            nxgraph: nx.DiGraph
            value: T
            Type: T

    def dict(self) -> GraphDict:
        return self.model_dump()
    if TYPE_CHECKING:
        

        def __iter__(self):
            NT = TypeVar("NT")
            class GraphTuple(NamedTuple, Generic[NT]):
                name: str | None = None
                parent: Union["ref[TreeNode[NT]]",None] | None = None
                status: Literal["waiting", "running", "done"] | None = None
                report: str | None = None
                children: dict[str, "TreeNode[NT]"] | None = None
                adjacency_list: dict[str, set[str]] | None = None
                reverse_adjacency_list: dict[str, set[str]] | None = None
                nxgraph: nx.DiGraph | None = None
                value: NT | None = None
                Type: NT | None = None
            return GraphTuple( ).__iter__()
        

        
        
        # def __getattribute__(self, name):
        #     # class GraphTuple(NamedTuple):
        #     #     name: str
        #     #     parent: "ref[TreeNode[T]]" | None
        #     #     status: Literal["waiting", "running", "done"] | None
        #     #     report: str | None
        #     #     children: dict[str, "TreeNode[T]"]
        #     #     adjacency_list: dict[str, set[str]]
        #     #     reverse_adjacency_list: dict[str, set[str]]
        #     #     nxgraph: nx.DiGraph
        #     #     value: T
        #     #     Type: T
        
        #     # g = GraphTuple()
        #     return g.__getattribute__(name)

     
            
    else:
        model_config = {"arbitrary_types_allowed": True}

    if not TYPE_CHECKING:

        def __init__(self, *args, **kwargs):
            kwargs.update(dict(zip(list(self.model_fields.keys())[: len(args)], args)))

            super().__init__(**kwargs)

        def __iter__(self):
            return iter(self.model_dump().values())


ImportToBrokenDict = dict[str, set[str]]
NameToModuleDict = dict[str, "ModuleNode"]

class ModuleNode(TreeNode[ModuleType]):
    imports: list[str] = Field(default_factory=list)
    contents: ContentT = Field(default_factory=dict)
    filepath: Path | None = None

    if not TYPE_CHECKING:
        def __init__(self, *args, **kwargs):
            kwargs.update(dict(zip(list(self.model_fields.keys())[:len(args)], args)))

            super().__init__(**kwargs)
    
    broken_imports: ImportToBrokenDict = Field(default_factory=dict)
    module_nodes: NameToModuleDict = Field(default_factory=dict)

Graph = ModuleNode
# g = Graph("root", broken_imports={}, module_nodes={})
# b = TreeNode("root",adjacency_list={}, reverse_adjacency_list={}, name="root", nxgraph=nx.DiGraph(), value=Path.cwd().stem)
# c, d,e,f,*h = g.__iter__()
# a = b




# Define excluded directories
EXCLUDED_DIRS = {'site-packages', 'vendor', 'venv', '.venv', 'env', '.env'}

def isexcluded(path: Path, allow_site_packages=False) -> bool:
    if allow_site_packages and "site-packages" in path.parts:
        return False
    return any(excluded in path.parts for excluded in EXCLUDED_DIRS)

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
    root_node = ModuleNode("root", filepath=directory_path)
    module_nodes = {'root': root_node}
    adjacency_list = defaultdict(set)
    adjacency_list['root'] = set()
    reverse_adjacency_list = defaultdict(set)  # For getting modules that import a given module
    reverse_adjacency_list['root'] = set()
    broken_imports = defaultdict(set)  # Map broken imports to sets of file paths

    for file_path in paths:
        # Skip site-packages and vendor directories if not included
        
        if isexcluded(file_path, allow_site_packages=include_site_packages):
            logging.debug(f"Skipping {file_path}")
            continue
        try:
            # Compute module's import path
            relative_path = file_path.relative_to(directory_path)
            parts = relative_path.with_suffix('').parts  # Remove '.py' suffix
            if relative_path.name == '__init__.py':
                module_name = ".".join(parts[:-1]) if len(parts) > 1 else "root"
            else:
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
            module_node = ModuleNode(module_name, parent=parent_node, filepath=file_path)
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
            adjacency_list[parent_module_name].add(module_name)
            adjacency_list[module_name] = set()
            reverse_adjacency_list[module_name].add(parent_module_name)
            # Update adjacency list for PageRank
            for imp in module_node.imports:
                adjacency_list[module_name].add(imp)
                reverse_adjacency_list[imp].add(module_name)
                # Initialize the importance of imported modules if not already
                if imp not in module_nodes:
                    module_nodes[imp] = ModuleNode(imp)

                # Update importance
                module_nodes[imp].importance += module_node.importance / max(len(module_node.imports), 1)

                # Attempt to import the module
                if not attempt_import(imp):
                    modname = imp.split(".")[0] if len(imp.split(".")) > 1 else imp
                    # Add the file path to the broken import's set
                    broken_imports.setdefault(modname, set()).add(file_path.as_posix())

        except (SyntaxError, UnicodeDecodeError, ValueError):
            continue
    root_node.module_nodes = module_nodes
    root_node.adjacency_list = adjacency_list
    root_node.reverse_adjacency_list = reverse_adjacency_list
    root_node.broken_imports = broken_imports
    return Graph(
        root=root_node,
        module_nodes=module_nodes,
        adjacency_list=adjacency_list,
        reverse_adjacency_list=reverse_adjacency_list,
        broken_imports=broken_imports,
    )

def print_tree(node: ModuleNode, level=0, include_docs=False, include_signatures=False, include_code=False):
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
    size_importance: list[tuple[str, Dict[str, float]]]


# FILE: structuralholes.py



def get_stats(
    module_nodes: Dict[str, ModuleNode],
    adjacency_list: Dict[str, Set[str]],
    reverse_adjacency_list: Dict[str, Set[str]],
) -> GraphStats:
    """Computes statistics for the dependency graph."""
    num_modules = ilen(module_nodes)
    num_imports = sum(ilen(node.imports) for node in module_nodes.values())
    num_functions = sum(ilen(node.contents.get("functions", {})) for node in module_nodes.values())
    num_classes = sum(ilen(node.contents.get("classes", {})) for node in module_nodes.values())

    num_modules = len(module_nodes)

    num_imports = sum(len(node.imports) for node in module_nodes.values())
    logging.debug(f"Number of imports: {num_imports}")

    num_functions = sum(len(node.contents.get('functions', {})) for node in module_nodes.values())
    logging.debug(f"Number of functions: {num_functions}")

    num_classes = sum(len(node.contents.get('classes', {})) for node in module_nodes.values())
    logging.debug(f"Number of classes: {num_classes}")# Build the graph
    G = nx.DiGraph()
    for node, neighbors in adjacency_list.items():
        for neighbor in neighbors:
            G.add_edge(node, neighbor)

    # Add standalone nodes
    for node in module_nodes:
        if node not in G:
            G.add_node(node)

    # Compute PageRank
    try:
        pg = nx.pagerank(G)
        pg = {k: round(v, 4) for k, v in pg.items()}
    except Exception as e:
        logging.error(f"PageRank computation failed: {e}")
        pg = {node: 0.0 for node in G.nodes()}

    # Compute average degree
    avg_degree = sum(dict(G.degree()).values()) / float(len(G)) if len(G) > 0 else 0
    avg_degree = round(avg_degree, 2)

    # Strongly Connected Components
    scc = list(nx.strongly_connected_components(G))
    scc = sorted(scc, key=lambda x: len(x), reverse=True)

    # Compute Effective Size
    effective_sizes = nx.effective_size(G)

    sizes_with_neighbors = {
        node: {
            "effective_size": effective_sizes.get(node, 0.0),
            "neighbors": len(adjacency_list.get(node, [])) + len(reverse_adjacency_list.get(node, [])),
            "pagerank": pg.get(node, 0.0)
        }
        for node in adjacency_list
    }

    size_importance = sorted(sizes_with_neighbors.items(), key=lambda x: x[1]["pagerank"], reverse=True)



    return {
        'num_modules': num_modules,
        'num_imports': num_imports,
        'num_functions': num_functions,
        'num_classes': num_classes,
        'avg_degree': avg_degree,
        'scc': scc,
        "size_importance": size_importance,
    }


def get_stats2(
    module_nodes: Dict[str, ModuleNode],
    adjacency_list: Dict[str, Set[str]],
    reverse_adjacency_list: Dict[str, Set[str]],
) -> GraphStats:
    """Computes statistics for the dependency graph."""
    num_modules = ilen(module_nodes)
    num_imports = sum(ilen(node.imports) for node in module_nodes.values())
    num_functions = sum(ilen(node.contents.get("functions", {})) for node in module_nodes.values())
    num_classes = sum(ilen(node.contents.get("classes", {})) for node in module_nodes.values())

    # Build the graph
    G = nx.DiGraph()
    for node, neighbors in adjacency_list.items():
        for neighbor in neighbors:
            G.add_edge(node, neighbor)

    # Add standalone nodes
    for node in module_nodes:
        if node not in G:
            G.add_node(node)

    # Compute PageRank
    try:
        pg = nx.pagerank(G)
        pg = {k: round(v, 4) for k, v in pg.items()}
    except Exception as e:
        logging.error(f"PageRank computation failed: {e}")
        pg = {node: 0.0 for node in G.nodes()}

    # Compute average degree
    avg_degree = sum(dict(G.degree()).values()) / float(len(G)) if len(G) > 0 else 0
    avg_degree = round(avg_degree, 2)

    # Strongly Connected Components
    scc = list(nx.strongly_connected_components(G))
    scc = sorted(scc, key=lambda x: len(x), reverse=True)

    # Compute Effective Size
    effective_sizes = nx.effective_size(G)

    sizes_with_neighbors = {
        node: {
            "effective_size": effective_sizes.get(node, 0.0),
            "neighbors": len(adjacency_list.get(node, [])) + len(reverse_adjacency_list.get(node, [])),
            "pagerank": pg.get(node, 0.0),
        }
        for node in G.nodes()
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


from typing import Dict, Set
from rich.table import Table
from rich.console import Console

console = Console()


def display_stats(stats: GraphStats, exclude: Set[str] = None) -> None:
    """Displays statistics for the dependency graph."""
    exclude = exclude or set()
    title = "Dependency Graph Statistics"
    console.print(f"\n[bold light_goldenrod2]{title}[/bold light_goldenrod2]\n")

    for key, value in stats.items():
        if key in exclude or key in {"pagerank", "scc", "sizes"}:
            continue

        if isinstance(value, list):
            # Assuming this is the 'size_importance' list of tuples
            if not value:
                console.print(f"{key}: No data available.\n")
                continue

            # Create a table for list-type statistics
            console.print(f"[bold]{key}[/bold]")
            table = Table(title=key, style="light_goldenrod2")

            # Extract column headers from the first item's dictionary
            _, first_dict = value[0]
            for column in first_dict.keys():
                table.add_column(column.replace("_", " ").capitalize())
            table.add_column("Node")

            # Add rows to the table
            for node, metrics in value[:10]:  # Display top 10 entries
                row = [
                    f"{metrics[col]:.2f}" if isinstance(metrics[col], float) else str(metrics[col])
                    for col in first_dict.keys()
                ]
                row.append(node)
                table.add_row(*row)

            console.print(table)
            console.print("")  # Add an empty line for better readability
        else:
            # Display scalar statistics
            if isinstance(value, float):
                console.print(f"[bold]{key.capitalize()}[/bold]: {value:.2f}\n")
            else:
                console.print(f"[bold]{key.capitalize()}[/bold]: {value}\n")

    # Specifically display average degree if it's not already included
    if "avg_degree" not in exclude and "avg_degree" in stats:
        avg_degree = stats["avg_degree"]
        console.print(f"[bold]Average Degree[/bold]: {avg_degree:.2f}\n")


        
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
    show_broken: bool = True,
):
    """Build dependency graph and adjacency list."""
    filter_to_module = lambda x: x
    path = Path(directory_file_or_module).resolve()
    if not path.exists():
        # Assume it's a module name
        path = Path.cwd()
        filter_to_module = lambda x: x.name == directory_file_or_module
        filter_includes_module = lambda x: x.name in _who_imports(directory_file_or_module, path, site_packages)
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
    print(result.dict())
    root_node = first_true(result.module_nodes.values(), pred=filter_to_module)
    module_nodes = root_node.module_nodes
    adjacency_list = result.adjacency_list
    reverse_adjacency_list = result.reverse_adjacency_list
    broken_imports = result.broken_imports
  


    # print_tree(
    #     root_node,
    #     include_docs=docs,
    #     include_signatures=sigs,
    #     include_code=code,
    # )

    # Display statistics if requested
    if stats:
        stats = get_stats(module_nodes, adjacency_list, reverse_adjacency_list)
        display_stats(stats)
        stats = get_stats2(root_node.module_nodes, adjacency_list, reverse_adjacency_list)
        display_stats(stats)
    # Display importers if requested
    if who_imports:
        who_imports: FunctionType = sys.modules[__name__].who_imports
        who_imports(directory_file_or_module, path, site_packages=site_packages, show=True)
    # Display broken imports with file paths
    if show_broken and broken_imports:
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

_who_imports = who_imports
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

