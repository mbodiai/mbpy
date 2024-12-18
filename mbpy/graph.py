
import ast
import importlib.util
import inspect
import logging
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generic,
    NamedTuple,
    Optional,
    ParamSpec,
    Set,
    TypedDict,
    TypeVar,
    Union,
    Unpack,
    cast,
    dataclass_transform,
    get_type_hints,
)
from weakref import ReferenceType, ref

import networkx as nx

# Import NetworkX for graph representation
from more_itertools import first_true, ilen
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from typing_extensions import (
    Literal,
    TypedDict,
)

from mbpy import SPINNER, DataModel, context
from mbpy.utils.collect import compose
from mbpy.utils.import_utils import smart_import

STYLES = {
    "module": "bold cyan",
    "function": "yellow",
    "class": "magenta",
    "method": "blue",
    "docs": "green italic",
    "imports": "dim yellow",
    "signature": "red",
}

pydantic = smart_import("pydantic", "type_safe_lazy")

if pydantic == Any:
    from dataclasses import field
    Field = field

    def model_validator(*args, **kwargs):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

else:
    Field = pydantic.Field
    model_validator = pydantic.model_validator
T = TypeVar("T")
console = Console()



class ContentT(TypedDict, total=False):
    functions: Dict[str, Dict[str, str | list[str]]]
    classes: Dict[str, Dict[str, str | list[str]]]
    imports: list[str]
    methods: Dict[str, Dict[str, str | list[str]]]
    docs: str
    signature: Dict[str, str] 
    code: str 





def extract_node_info(file_path: str,*, include_docs: bool = False, include_signatures: bool = False, include_code: bool = False) -> ContentT:
    """Extracts imports, function definitions, class definitions, docstrings, and signatures from a Python file."""
    with Path(file_path).open('r', encoding='utf-8') as f:
        source_code = f.read()
    try:
        tree = ast.parse(source_code)
    except (SyntaxError, UnicodeDecodeError, ValueError, TypeError, AttributeError):
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
        with context.suppress(Exception) as e:
            pass
        if e:
            logging.error(f"Error extracting signatures from '{file_path}': {e}")

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
            functions[func_name] = {'docs': func_doc if include_docs else None}
            if include_signatures:
                node_contents.setdefault('signature', {})[func_name] = f"{func_name}({', '.join(args)})"
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
                        node_contents.setdefault('signature', {})[method_name] = f"{method_name}({', '.join(args)})"
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
    if e:
        logging.debug(f"Error importing module '{module_name}': {e}")
    return False


if TYPE_CHECKING:
    from pydantic._internal._model_construction import ModelMetaclass
    _MetaT = ModelMetaclass
else:
    _MetaT = type
@dataclass_transform()
class MetaT(_MetaT):
    def __new__(cls, name, bases, dct, *args, **kwargs):
        cls = type.__new__(cls, name, bases, dct, *args, **kwargs)
        return dataclass(cls)


dec = dataclass
Field = field
if TYPE_CHECKING:
    ParentT = DataModel
else:
    ParentT = SimpleNamespace
_T = TypeVar("_T")


class TreeNode(ParentT, Generic[T], metaclass=MetaT):
    """A tree node with a name, parent, status, importance, and report."""
    name: str = Field(default_factory=compose(str, uuid.uuid4))
    parent: Optional["ReferenceType[TreeNode[T]]"] | None = None
    root: Optional["ReferenceType[TreeNode[T]]"] | None = None
    status: Literal["waiting", "running", "done"] | None = None
    importance: float = 1.0
    report: str | None = None
    """A report on the status of the subtree."""
    children: Dict[str, "TreeNode[T]"] = Field(default_factory=dict)
    adjacency_list: Dict[str, set[str]] = Field(default_factory=dict)
    reverse_adjacency_list: Dict[str, set[str]] = Field(default_factory=dict)
    nxgraph: nx.DiGraph | None = None
    value: T | None = None
    Type: type[T] | tuple[type[T], ...] | None = None
    
    @model_validator(mode="before")
    @classmethod
    def makerefs(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if "parent" in v:
            v["parent"] = ref(v["parent"])
        if "root" in v:
            v["root"] = ref(v["root"])
        return v

    @model_validator(mode="after")
    def setroot(self) :
        if self.parent is None:
            self.root = ref(self)
        elif (p:=self.parent()) is not None:
            self.root = p.root
        return self
    
    @classmethod
    def fromdict(cls, d: dict, name=None, parent=None) -> "TreeNode":
        return cls(name=name or d.pop("name",None), parent=parent or d.pop("parent",None), **d)
  
    @classmethod
    def __class_getitem__(cls, value_type: type[T] | tuple[type[T], ...]) -> type["TreeNode[T]"]:
        cls.Type = value_type
        return cls
    
    def graph(self, g: nx.DiGraph | None = None) -> nx.DiGraph:
        """Recursively adds nodes and edges to a NetworkX graph."""
        g = g or nx.DiGraph()
        g.add_node(self.name)
       
        for child in self.children.values():
            child.graph(g)
        return g

    class GraphDict(TypedDict):
        name: str
        parent: Optional["ref['TreeNode']"]
        status: Literal["waiting", "running", "done"] | None
        report: str | None
        children: dict[str, "TreeNode"]
        adjacency_list: dict[str, set[str]]
        reverse_adjacency_list: dict[str, set[str]]
        nxgraph: nx.DiGraph

    class GraphTuple(NamedTuple, Generic[_T]):
        name: str
        parent: "Union[ref['TreeNode[_T]'], None]" # noqa
        status: Literal["waiting", "running", "done"] | None
        report: str | None
        children: dict[str, "TreeNode[_T]"]
        adjacency_list: dict[str, set[str]]
        reverse_adjacency_list: dict[str, set[str]]
        nxgraph: nx.DiGraph
        value: _T
        Type: _T

    def todic(self) -> GraphDict:
        d = self.__dict__   
        return cast("TreeNode.GraphDict", {k: d[k] for k in d if not k.startswith("_")})
    def dict(self) -> GraphDict: # noqa
        return self.todic()
    def totup(self) -> GraphTuple[T]:
        return cast("TreeNode.GraphTuple[T]", tuple(self.todic().values()))
    def setdefault(self, key: str, default: Any) -> Any:
        return self.__dict__.setdefault(key, default)
    def __getitem__(self, key):
        if isinstance(key, int):
            return self.totup()[key]
        if not key.startswith("_"):
            return getattr(self, key)
        raise AttributeError(f"{key} is not a valid field")

    model_config = {"arbitrary_types_allowed": True}




ImportToBrokenDict = dict[str, set[str]]
NameToModuleDict = dict[str, "ModuleNode"]

class ModuleNode(TreeNode[ModuleType],metaclass=MetaT):
    imports: list[str] = Field(default_factory=list)
    contents: ContentT = Field(default_factory=lambda: {})
    filepath: Path | None = None
    broken_imports: ImportToBrokenDict = Field(default_factory=dict)
    module_nodes: NameToModuleDict = Field(default_factory=dict)


Graph = ModuleNode

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
    root_node = ModuleNode(name="root", filepath=directory_path)
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
                str(file_path),
                include_docs=include_docs,
                include_signatures=include_signatures,
                include_code=include_code,
            )
            if node_info is None:
                continue  # Skip files that couldn't be parsed

            # Create or get the module node
            module_node = ModuleNode(name=module_name, parent=ref(parent_node), filepath=file_path)
            module_node.imports = node_info.get('imports', [])
            module_node.contents['functions'] = node_info.get('functions', {})
            module_node.contents['classes'] = node_info.get('classes', {})
            # Include optional fields if they exist
            if include_docs and 'docs' in node_info:
                module_node.contents['docs'] = node_info['docs']
            if include_signatures and 'signature' in node_info:
                module_node.contents['signature'] = node_info['signature']
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
                    module_nodes[imp] = ModuleNode(name=imp)

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
        root=ref(root_node),
        module_nodes=module_nodes,
        adjacency_list=adjacency_list,
        reverse_adjacency_list=reverse_adjacency_list,
        broken_imports=broken_imports,
    )


def print_graph(
    node: ModuleNode,
    include_functions=False,
    include_classes=False,
    include_docs=False,
    include_signatures=False,
    include_code=False,
    include_imports=False,
) -> None:
    """Print formatted module dependency graph."""
    SPINNER.stop()
    console = Console()
    def create_tree(node: ModuleNode, parent: Tree | None = None) -> Tree:
        # Create root or branch
        tree = (
            Tree(Text(node.name, style=STYLES["module"]))
            if parent is None
            else parent.add(Text(node.name, style=STYLES["module"]))
        )

        # Add imports
        if include_imports and node.imports:
            imports = tree.add("[dim yellow]Imports")
            imports.add(Text(", ".join(node.imports), style=STYLES["imports"]))

        # Add functions
        if include_functions and node.contents.get("functions"):
            funcs = tree.add("[yellow]Functions")
            for fname, finfo in node.contents.setdefault("functions", {}).items():
                func = funcs.add(Text(fname, style=STYLES["function"]))
                if include_signatures and node.contents.get("signature", {}).get(fname):
                    func.add(Text(f"↪ {node.contents.setdefault('signature',{})[fname]}", style=STYLES["signature"]))
                if include_docs and (docs:=finfo.get("docs")):
                    func.add(Text(docs), style=STYLES["docs"])

        # Add classes
        if include_classes and node.contents.get("classes"):
            classes = tree.add("[magenta]Classes")
            for cname, cinfo in node.contents.setdefault("classes", {}).items():
                class_branch = classes.add(Text(cname, style=STYLES["class"]))

                if include_docs and (docs:=cinfo.get("docs","")):
                    class_branch.add(Text(docs, style=STYLES["docs"]))

                if cinfo.get("methods"):
                    methods = class_branch.add("[blue]Methods")
                    for mname, minfo in cinfo.setdefault("methods", {}).items():
                        method = methods.add(Text(mname, style=STYLES["method"]))
                        if include_signatures and node.contents.get("signature", {}).get(mname):
                            method.add(Text(f"↪ {node.setdefault('signature',{})[mname]}", style=STYLES["signature"]))
                        if include_docs and minfo.get("docs"):
                            method.add(Text(minfo["docs"], style=STYLES["docs"]))

        # Add source code
        if include_code and (code:=node.contents.get("code")):
            tree.add(
                Panel(
                    Syntax(code, "python", theme="monokai", line_numbers=True, word_wrap=True),
                    title="Source Code",
                    border_style="dim",
                ),
            )

        # Add children recursively
        for child in node.children.values():
            create_tree(child, tree)

        return tree

    # Print formatted tree
    tree = create_tree(node)
    console.print(Panel(tree, title="Module Dependency Graph", border_style=STYLES["module"]))




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
            "pagerank": pg.get(node, 0.0),
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



console = Console()


def display_stats(stats: GraphStats, exclude: Set[str] | None = None) -> None:
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
            for column in first_dict:
                table.add_column(column.replace("_", " ").capitalize())
            table.add_column("Node")

            # Add rows to the table
            for node, metrics in value[:10]:  # Display top 10 entries
                row = [
                    f"{metrics[col]:.2f}" if isinstance(metrics[col], float) else str(metrics[col])
                    for col in first_dict
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
    importedby: bool = False,
    stats: bool = False,
    site_packages: bool = False,
    show_broken: bool = False,
):
    """Build dependency graph and adjacency list."""
    path = Path(directory_file_or_module).resolve()
    if not path.exists():
        # Assume it's a module name
        path = Path.cwd()
    result = build_dependency_graph(
        path,
        include_site_packages=site_packages,
        include_docs=docs,
        include_signatures=sigs,
        include_code=code,
    )
    root_node = first_true(result.module_nodes.values(), pred=lambda x: x.name == "root", default=ModuleNode())
    module_nodes = result.module_nodes
    adjacency_list = result.adjacency_list
    reverse_adjacency_list = result.reverse_adjacency_list
    broken_imports = result.broken_imports
  


    print_graph(
        root_node,
        include_docs=docs,
        include_signatures=sigs,
        include_code=code,
    )

    # Display statistics if requested
    _stats: GraphStats | None = None
    if stats:
        _stats = get_stats(module_nodes, adjacency_list, reverse_adjacency_list)
        display_stats(_stats)
        _stats = get_stats2(root_node.module_nodes, adjacency_list, reverse_adjacency_list)
        display_stats(_stats)
    # Display importers if requested
    if importedby:
        who_imports: FunctionType = sys.modules[__name__].who_imports
        who_imports(directory_file_or_module, path, site_packages=site_packages, show=True)
    # Display broken imports with file paths
    if show_broken and broken_imports:
        display_broken(broken_imports)
    return result, _stats, broken_imports


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
    elif show:
        console.print(f"\n[bold red]No modules found that import '{module_name}'.[/bold red]")
    return importers


P = ParamSpec("P")
R = TypeVar("R")


def get_validated_params(func: Callable[P, R], *args: str, **kwargs: str):
    """Validates and converts string arguments to the appropriate types based on the callable's annotations."""
    sig = inspect.signature(func)
    params = sig.parameters
    converted_kwargs = {}
    converted_args = []
    arg_idx = 0

    # Convert positional arguments
    for p_name, p in params.items():
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
            if arg_idx < len(args):
                raw_value = args[arg_idx]
                if p.annotation != inspect.Parameter.empty and isinstance(p.annotation, type):
                    try:
                        converted_value = p.annotation(raw_value)
                    except (ValueError, TypeError) as e:
                        raise ValueError(f"Error converting argument '{p_name}': {e}") from e
                else:
                    converted_value = raw_value
                converted_args.append(converted_value)
                arg_idx += 1
            elif p_name in kwargs:
                raw_value = kwargs.pop(p_name)
                if p.annotation != inspect.Parameter.empty and isinstance(p.annotation, type):
                    try:
                        converted_value = p.annotation(raw_value)
                    except (ValueError, TypeError) as e:
                        raise ValueError(f"Error converting argument '{p_name}': {e}") from e
                else:
                    converted_value = raw_value
                converted_kwargs[p_name] = converted_value
            elif p.default != inspect.Parameter.empty:
                converted_kwargs[p_name] = p.default
            else:
                raise TypeError(f"Missing required argument '{p_name}'")

    # Convert remaining keyword arguments
    for key, raw_value in kwargs.items():
        if key in params:
            param = params[key]
            if param.annotation != inspect.Parameter.empty and isinstance(param.annotation, type):
                try:
                    converted_value = param.annotation(raw_value)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Error converting argument '{key}': {e}") from e
            else:
                converted_value = raw_value
            converted_kwargs[key] = converted_value
        else:
            raise TypeError(f"Unexpected keyword argument '{key}'")

    # Return validated arguments
    return converted_args, converted_kwargs


def validate_params(func: Callable[P, R]) -> Callable[P, R]:
    """A decorator to validate and convert inputs dynamically based on the type hints of the wrapped function."""

    def wrapper(*args, **kwargs):
        # Retrieve the function's signature and type hints
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        # Bind the provided arguments to the function's signature
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        # Validate and convert arguments
        for name, value in bound_args.arguments.items():
            expected_type = type_hints.get(name)

            # Skip validation if no type hint is provided
            if expected_type is None:
                continue

            # Convert the value to the expected type, if necessary
            if not isinstance(value, expected_type):
                try:
                    # Special handling for booleans
                    if expected_type is bool and isinstance(value, str):
                        bound_args.arguments[name] = value.lower() in ("true", "1", "yes")
                    else:
                        bound_args.arguments[name] = expected_type(value)
                except (ValueError, TypeError) as e:
                    raise ValueError(
                        f"Argument '{name}' must be of type {expected_type}, "
                        f"but got value '{value}' of type {type(value)}",
                    ) from e

        # Call the original function with validated arguments
        return func(*bound_args.args, **bound_args.kwargs)

    return wrapper


if __name__ == "__main__":

    class _TD(TypedDict,total=False):
        stats: bool
        sigs: bool
        docs: bool

    TD = TypeVar("TD", bound=_TD)

    @validate_params
    def gen(*args: str, **kwargs: Unpack[_TD]):
        args, kwargs = get_validated_params(generate, *args, **kwargs)
        return generate(*args, **kwargs)

    if sys.argv[1:]:
        gen(*sys.argv[1:])
    else:
        generate(stats=True)
