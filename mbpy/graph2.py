from __future__ import annotations

import ast
import contextlib
import importlib.util
import inspect
import logging
import sys
import uuid
from collections import defaultdict, deque
from fnmatch import fnmatch
from pathlib import Path
from types import FunctionType, MappingProxyType, ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generic,
    Iterator,
    List,
    Mapping,
    Optional,
    Self,
    Set,
    Tuple,
    TypeVar,
    TypeVarTuple,
)
from weakref import ref

import networkx as nx
import rich_click as click
from packaging.utils import canonicalize_name
from pydantic import BaseModel, Field, model_validator
from rich.console import Console
from rich.table import Table
from typing_extensions import (
    Literal,
    TypedDict,
)

from mbpy.pkg import DistPackage, InvalidRequirementError, ReqPackage
from mbpy.utils.collections import cat

if TYPE_CHECKING:
    from importlib.metadata import Distribution


Ts = TypeVarTuple("Ts")



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Initialize Rich Console
console = Console()
U = TypeVar("U")
# Type Definitions
T = TypeVar("T")



# Warning Printer Utility
class WarningPrinter:
    def __init__(self):
        self.warnings: Dict[str, List[str]] = defaultdict(list)

    def should_warn(self) -> bool:
        return bool(self.warnings)

    def add_warning(self, key: str, message: str) -> None:
        self.warnings[key].append(message)

    def print_warnings(self, title: str) -> None:
        if not self.should_warn():
            return
        console.print(f"\n[bold yellow]{title}[/bold yellow]", style="bold yellow")
        for key, messages in self.warnings.items():
            console.print(f"{key}:", style="bold")
            for msg in messages:
                console.print(f"  - {msg}", style="dim")

# TreeNode Class
class TreeNode(BaseModel, Generic[*Ts]):
    """A tree node with a name, parent, status, importance, and report."""
    name: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent: ref[TreeNode[*Ts]] | Any | None = None
    root: ref[TreeNode[*Ts]] | None = None
    status: Literal["waiting", "running", "done"] | None = None
    importance: float = 1.0
    report: str | None = None
    """A report on the status of the subtree."""
    children: Dict[str, TreeNode[*Ts]] = Field(default_factory=dict)
    adjacency_list: Dict[str, Set[str]] = Field(default_factory=dict)
    reverse_adjacency_list: Dict[str, Set[str]] = Field(default_factory=dict)
    content: U | None = None
    subcontentT: TreeNode[T] | None = None  # noqa: N815

    @model_validator(mode="before")
    @classmethod
    def makerefs(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if "parent" in v and isinstance(v["parent"], str):
            v["parent"] = ref(v["parent"])  # Adjust as needed
        if "root" in v and isinstance(v["root"], str):
            v["root"] = ref(v["root"])  # Adjust as needed
        return v

    @classmethod
    def fromdict(cls, d: dict, name: str | None = None, parent: ref[TreeNode[T]] | None = None)  -> Self:
        return cls(name=name or d.pop("name", ""), parent=parent or d.pop("parent", None), **d)

    def graph(self, g: nx.DiGraph | None = None) -> nx.DiGraph:
        """Recursively adds nodes and edges to a NetworkX graph."""
        g = g or nx.DiGraph()
        g.add_node(self.name)
       
        for child in self.children.values():
            g.add_edge(self.name, child.name)
            child.graph(g)
        return g

    class Config:
        arbitrary_types_allowed = True

    def __iter__(self) -> Iterator[Any]:
        return iter(self.model_dump().values())

class CodeType(TypedDict):
    functions: Dict[str, Dict[str, str | List[str]]] | None
    classes: Dict[str, Dict[str, str | List[str]]] | None
    docs: str | None
    signature: str | MappingProxyType[str, type] | None
    code: str | None


ImportToBrokenDict = Dict[str, Set[str]]
NameToModuleDict = Dict[str, "ModuleNode"]
# ModuleNode Class
class ModuleNode(TreeNode[ModuleType]):
    imports: List[str] = Field(default_factory=list)
    contents: CodeType = Field(default_factory=dict)
    filepath: Path | None = None
    broken_imports: ImportToBrokenDict = Field(default_factory=dict)
    module_nodes: NameToModuleDict = Field(default_factory=dict)

    def add_import(self, imported_module: str) -> None:
        self.imports.append(imported_module)

    def add_child(self, child: ModuleNode) -> None:
        self.children[child.name] = child


def render_broken_imports_text(broken_imports: Dict[str, Set[str]]) -> None:
    for module_name, file_paths in broken_imports.items():
        console.print(f"[bold red]Module: {module_name}[/bold red]", style="bold red")
        for path in file_paths:
            console.print(f"  Imported by: {path}", style="dim")

def attempt_import(module_name: str) -> bool:
    """Attempts to import a module by name. Returns True if successful, False otherwise."""
    try:
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            raise ImportError(f"Module '{module_name}' not found.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore
        return True
    except ImportError as e:
        logging.debug(f"ImportError for module '{module_name}': {e}")
    except Exception as e:
        logging.error(f"Unexpected error importing module '{module_name}': {e}")
    return False







def render_invalid_reqs_text(dist_name_to_invalid_reqs_dict: dict[str, list[str]]) -> None:
    for dist_name, invalid_reqs in dist_name_to_invalid_reqs_dict.items():
        print(dist_name, file=sys.stderr)  # noqa: T201

        for invalid_req in invalid_reqs:
            print(f'  Skipping "{invalid_req}"', file=sys.stderr)  # noqa: T201


class PackageDAG(Mapping[DistPackage, List[ReqPackage]]):
    """Representation of Package dependencies as directed acyclic graph using a dict as the underlying datastructure.

    The nodes and their relationships (edges) are internally stored using a map as follows,

    {a: [b, c],
     b: [d],
     c: [d, e],
     d: [e],
     e: [],
     f: [b],
     g: [e, f]}

    Here, node `a` has 2 children nodes `b` and `c`. Consider edge direction from `a` -> `b` and `a` -> `c`
    respectively.

    A node is expected to be an instance of a subclass of `Package`. The keys are must be of class `DistPackage` and
    each item in values must be of class `ReqPackage`. (See also ReversedPackageDAG where the key and value types are
    interchanged).

    """

    @classmethod
    def from_pkgs(cls, pkgs: list[Distribution]) -> PackageDAG:
        dist_pkgs = [DistPackage(p) for p in pkgs]
        idx = {p.key: p for p in dist_pkgs}
        m: dict[DistPackage, list[ReqPackage]] = {}
        dist_name_to_invalid_reqs_dict: dict[str, list[str]] = {}
        for p in dist_pkgs:
            reqs = []
            requires_iterator = p.requires()
            while True:
                try:
                    req = next(requires_iterator)
                except InvalidRequirementError as err:
                    # We can't work with invalid requirement strings. Let's warn the user about them.
                    dist_name_to_invalid_reqs_dict.setdefault(p.project_name, []).append(str(err))
                    continue
                except StopIteration:
                    break
                d = idx.get(canonicalize_name(req.name))
                # Distribution.requires only returns the name of requirements in the metadata file, which may not be the
                # same as the name in PyPI. We should try to retain the original package names for requirements.
                # See https://github.com/tox-dev/pipdeptree/issues/242
                req.name = d.project_name if d is not None else req.name
                pkg = ReqPackage(req, d)
                reqs.append(pkg)
            m[p] = reqs

        should_print_warning = warning_printer.should_warn() and dist_name_to_invalid_reqs_dict
        if should_print_warning:
            warning_printer.print_multi_line(
                "Invalid requirement strings found for the following distributions",
                lambda: render_invalid_reqs_text(dist_name_to_invalid_reqs_dict),
            )

        return cls(m)

    def __init__(self, m: dict[DistPackage, list[ReqPackage]]) -> None:
        """Initialize the PackageDAG object.

        :param dict m: dict of node objects (refer class docstring)
        :returns: None
        :rtype: NoneType

        """
        self._obj: dict[DistPackage, list[ReqPackage]] = m
        self._index: dict[str, DistPackage] = {p.key: p for p in list(self._obj)}

    def get_node_as_parent(self, node_key: str) -> DistPackage | None:
        """Get the node from the keys of the dict representing the DAG.

        This method is useful if the dict representing the DAG contains different kind of objects in keys and values.
        Use this method to look up a node obj as a parent (from the keys of the dict) given a node key.

        :param node_key: identifier corresponding to key attr of node obj
        :returns: node obj (as present in the keys of the dict)

        """
        try:
            return self._index[node_key]
        except KeyError:
            return None

    def get_children(self, node_key: str) -> list[ReqPackage]:
        """Get child nodes for a node by its key.

        :param node_key: key of the node to get children of
        :returns: child nodes

        """
        node = self.get_node_as_parent(node_key)
        return self._obj[node] if node else []

    def filter_nodes(self, include: list[str] | None, exclude: set[str] | None) -> PackageDAG:  # noqa: C901, PLR0912
        """Filter nodes in a graph by given parameters.

        If a node is included, then all it's children are also included.

        :param include: list of node keys to include (or None)
        :param exclude: set of node keys to exclude (or None)
        :raises ValueError: If include has node keys that do not exist in the graph
        :returns: filtered version of the graph

        """
        # If neither of the filters are specified, short circuit
        if include is None and exclude is None:
            return self

        include_with_casing_preserved: list[str] = []
        if include:
            include_with_casing_preserved = include
            include = [canonicalize_name(i) for i in include]
        exclude = {canonicalize_name(s) for s in exclude} if exclude else set()

        # Check for mutual exclusion of show_only and exclude sets
        # after normalizing the values to lowercase
        if include and exclude:
            assert not (set(include) & exclude)

        # Traverse the graph in a depth first manner and filter the
        # nodes according to `show_only` and `exclude` sets
        stack: deque[DistPackage] = deque()
        m: dict[DistPackage, list[ReqPackage]] = {}
        seen = set()
        matched_includes: set[str] = set()
        for node in self._obj:
            if any(fnmatch(node.key, e) for e in exclude):
                continue
            if include is None:
                stack.append(node)
            else:
                should_append = False
                for i in include:
                    if fnmatch(node.key, i):
                        # Add all patterns that match with the node key. Otherwise if we break, patterns like py* or
                        # pytest* (which both should match "pytest") may cause one pattern to be missed and will
                        # raise an error
                        matched_includes.add(i)
                        should_append = True
                if should_append:
                    stack.append(node)

            while stack:
                n = stack.pop()
                cldn = [c for c in self._obj[n] if not any(fnmatch(c.key, e) for e in exclude)]
                m[n] = cldn
                seen.add(n.key)
                for c in cldn:
                    if c.key not in seen:
                        cld_node = self.get_node_as_parent(c.key)
                        if cld_node:
                            stack.append(cld_node)
                        else:
                            # It means there's no root node corresponding to the child node i.e.
                            # a dependency is missing
                            continue

        non_existent_includes = [
            i for i in include_with_casing_preserved if canonicalize_name(i) not in matched_includes
        ]
        if non_existent_includes:
            raise ValueError("No packages matched using the following patterns: " + ", ".join(non_existent_includes))

        return self.__class__(m)

    def reverse(self) -> ReversedPackageDAG:
        """Reverse the DAG, or turn it upside-down.

        In other words, the directions of edges of the nodes in the DAG will be reversed.

        Note that this function purely works on the nodes in the graph. This implies that to perform a combination of
        filtering and reversing, the order in which `filter` and `reverse` methods should be applied is important. For
        e.g., if reverse is called on a filtered graph, then only the filtered nodes and it's children will be
        considered when reversing. On the other hand, if filter is called on reversed DAG, then the definition of
        "child" nodes is as per the reversed DAG.

        :returns: DAG in the reversed form

        """
        m: defaultdict[ReqPackage, list[DistPackage]] = defaultdict(list)
        child_keys = {r.key for r in cat(self._obj.values())}
        for k, vs in self._obj.items():
            for v in vs:
                # if v is already added to the dict, then ensure that
                # we are using the same object. This check is required
                # as we're using array mutation
                node: ReqPackage = next((p for p in m if p.key == v.key), v)
                m[node].append(k.as_parent_of(v))
            if k.key not in child_keys:
                m[k.as_requirement()] = []
        return ReversedPackageDAG(dict(m))  # type: ignore[arg-type]

    def sort(self) -> PackageDAG:
        """Return sorted tree in which the underlying _obj dict is an dict, sorted alphabetically by the keys.

        :returns: Instance of same class with dict

        """
        return self.__class__({k: sorted(v) for k, v in sorted(self._obj.items())})

    # Methods required by the abstract base class Mapping
    def __getitem__(self, arg: DistPackage) -> list[ReqPackage] | None:  # type: ignore[override]
        return self._obj.get(arg)

    def __iter__(self) -> Iterator[DistPackage]:
        return self._obj.__iter__()

    def __len__(self) -> int:
        return len(self._obj)


class ReversedPackageDAG(PackageDAG):
    """Representation of Package dependencies in the reverse order.

    Similar to it's super class `PackageDAG`, the underlying datastructure is a dict, but here the keys are expected to
    be of type `ReqPackage` and each item in the values of type `DistPackage`.

    Typically, this object will be obtained by calling `PackageDAG.reverse`.

    """

    def reverse(self) -> PackageDAG:  # type: ignore[override]
        """Reverse the already reversed DAG to get the PackageDAG again.

        :returns: reverse of the reversed DAG

        """
        m: defaultdict[DistPackage, list[ReqPackage]] = defaultdict(list)
        child_keys = {r.key for r in cat(self.values())}
        for k, vs in self._obj.items():
            for v in vs:
                assert isinstance(v, DistPackage)
                node = next((p for p in m if p.key == v.key), v.as_parent_of(None))
                m[node].append(k)
            if k.key not in child_keys:
                assert isinstance(k, ReqPackage)
                assert k.dist is not None
                m[k.dist] = []
        return PackageDAG(dict(m))


def extract_node_info(
    file_path: Path,
    include_docs: bool = False,
    include_signatures: bool = False,
    include_code: bool = False,
) -> Optional[ContentT]:
    """Extracts imports, function definitions, class definitions, docstrings, and signatures from a Python file."""
    try:
        with file_path.open('r', encoding='utf-8') as f:
            source_code = f.read()
    except (UnicodeDecodeError, FileNotFoundError) as e:
        logging.error(f"Error reading file '{file_path}': {e}")
        return None

    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        logging.error(f"SyntaxError parsing file '{file_path}': {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error parsing file '{file_path}': {e}")
        return None

    imports = []
    functions = {}
    classes = {}
    node_contents: ContentT = {
        'functions': {},
        'classes': {},
    }

    if include_docs:
        module_doc = ast.get_docstring(tree)
        if module_doc:
            node_contents['docs'] = module_doc
    if include_signatures:
        signature = None
        with contextlib.suppress(Exception):
            signature = inspect.signature(eval(compile(ast.Expression(tree), filename=str(file_path), mode='eval')))
        if signature:
            node_contents['signature'] = str(signature)

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
                'docs': func_doc,
                'args': args,
            }
            if include_signatures:
                with contextlib.suppress.logignore():
                    func_signature = str(inspect.signature(FunctionType(node, globals())))
                    functions[func_name]['signature'] = func_signature

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
                        'docs': method_doc,
                        'args': args,
                    }
                    if include_signatures:
                        with supress.logignore():
                            method_signature = str(inspect.signature(FunctionType(body_item, globals())))
                            methods[method_name]['signature'] = method_signature
                    if include_code:
                        start = body_item.lineno - 1
                        end = body_item.end_lineno
                        method_code = source_code.split('\n')[start:end]
                        methods[method_name]['code'] = '\n'.join(method_code)
            classes[class_name] = {
                'docs': class_doc,
                'methods': methods,
            }
            if include_code:
                start = node.lineno - 1
                end = node.end_lineno
                class_code = source_code.split('\n')[start:end]
                classes[class_name]['code'] = '\n'.join(class_code)

    node_contents['imports'] = imports
    return node_contents

def isexcluded(path: Path, allow_site_packages=False) -> bool:
    EXCLUDED_DIRS = {'site-packages', 'vendor', 'venv', '.venv', 'env', '.env'}
    if allow_site_packages and "site-packages" in path.parts:
        return False
    return any(excluded in path.parts for excluded in EXCLUDED_DIRS)

def build_dependency_graph(
    directory_or_file: Path | str,
    include_site_packages: bool = False,
    include_docs: bool = False,
    include_signatures: bool = False,
    include_code: bool = False,
) -> Graph:
    directory_path = Path(directory_or_file).resolve()
    if directory_path.is_file():
        directory_path = directory_path.parent

    paths = [directory_path] if directory_path.is_file() else list(directory_path.rglob('*.py'))
    root_node = ModuleNode(name="root", filepath=directory_path)
    module_nodes: Dict[str, ModuleNode] = {'root': root_node}
    idx: Dict[str, ModuleNode] = {'root': root_node}  # Index for quick lookup
    adjacency_list: Dict[str, Set[str]] = defaultdict(set)
    reverse_adjacency_list: Dict[str, Set[str]] = defaultdict(set)
    broken_imports: ImportToBrokenDict = defaultdict(set)
    warning_printer = WarningPrinter()

    for file_path in paths:
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
            module_node = ModuleNode(
                name=module_name,
                parent=ref(parent_node),
                filepath=file_path,
                imports=node_info.get('imports', []),
                contents={
                    'functions': node_info.get('functions', {}),
                    'classes': node_info.get('classes', {}),
                },
                broken_imports={},
                module_nodes={}
            )

            # Include optional fields if they exist
            if include_docs and 'docs' in node_info:
                module_node.contents['docs'] = node_info['docs']
            if include_signatures and 'signature' in node_info:
                module_node.contents['signature'] = node_info['signature']
            if include_code and 'code' in node_info:
                module_node.contents['code'] = node_info['code']

            module_nodes[module_name] = module_node
            idx[module_name] = module_node  # Update index

            # Add to parent's children
            parent_node.children[module_name] = module_node
            adjacency_list[parent_module_name].add(module_name)
            adjacency_list[module_name] = set()

            # Update adjacency list for dependencies
            for imp in module_node.imports:
                adjacency_list[module_name].add(imp)
                reverse_adjacency_list[imp].add(module_name)

                # Attempt to import the module
                if not attempt_import(imp):
                    modname = imp.split(".")[0] if '.' in imp else imp
                    broken_imports[modname].add(file_path.as_posix())
                    warning_printer.add_warning(modname, f"Imported by {file_path}")

                # Use index to check if module already exists
                if imp not in idx:
                    # Create a placeholder ModuleNode for missing imports
                    placeholder_node = ModuleNode(
                        name=imp,
                        parent=None,
                        filepath=None,
                        imports=[],
                        contents={},
                        broken_imports={},
                        module_nodes={}
                    )
                    module_nodes[imp] = placeholder_node
                    idx[imp] = placeholder_node

        except (SyntaxError, UnicodeDecodeError, ValueError) as e:
            logging.error(f"Error processing file '{file_path}': {e}")
            continue

    # Assign aggregated data to root node
    root_node.module_nodes = module_nodes
    root_node.adjacency_list = adjacency_list
    root_node.reverse_adjacency_list = reverse_adjacency_list
    root_node.broken_imports = broken_imports

    # Print warnings if any
    if warning_printer.should_warn():
        warning_printer.print_warnings("Broken Imports Found")

    return Graph(
        root=root_node,
        module_nodes=module_nodes,
        adjacency_list=adjacency_list,
        reverse_adjacency_list=reverse_adjacency_list,
        broken_imports=broken_imports,
    )

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

def display_broken(broken_imports: Dict[str, Set[str]]) -> None:
    """Displays broken imports along with the file paths that import them."""
    console.print("\n[bold red]Broken Imports:[/bold red]")
    for imp, file_paths in broken_imports.items():
        console.print(f"\nModule: {imp}")
        for path in file_paths:
            console.print(f" - Imported by: {path}")

class GraphStats(TypedDict):
    num_modules: int
    num_imports: int
    num_functions: int
    num_classes: int
    avg_degree: float
    scc: List[Set[str]]
    size_importance: List[Tuple[str, Dict[str, float]]]

def get_stats(
    module_nodes: Dict[str, ModuleNode],
    adjacency_list: Dict[str, Set[str]],
    reverse_adjacency_list: Dict[str, Set[str]],
) -> GraphStats:
    """Computes statistics for the dependency graph."""
    num_modules = len(module_nodes)
    num_imports = sum(len(node.imports) for node in module_nodes.values())
    num_functions = sum(len(node.contents.get("functions", {})) for node in module_nodes.values())
    num_classes = sum(len(node.contents.get("classes", {})) for node in module_nodes.values())

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

def who_imports(
    module_name: str,
    path: Path | str,
    *,
    site_packages: bool,
    show: bool = False
) -> Set[str]:
    """Finds and optionally displays modules that import the given module."""
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

def validate_params(func, *args, **kwargs):
    """Validates parameters against the function's signature."""
    from inspect import signature
    sig = signature(func)
    params = sig.parameters
    args = list(args)
    for key in kwargs.keys():
        if key not in params:
            raise TypeError(f"Unexpected keyword argument '{key}'")
    return args

def display_dependency_tree(node: ModuleNode, level=0, include_docs=False, include_signatures=False, include_code=False):
    """Recursively displays the dependency tree."""
    indent = '  ' * level
    console.print(f"{indent}[bold light_goldenrod2]{node.name}[/bold light_goldenrod2]:")
    if node.imports:
        console.print(f"{indent}  Imports: {node.imports}")
    if node.contents.get('functions') or node.contents.get('classes'):
        console.print(f"{indent}  Contents:")
        for func_name, func_info in node.contents.get('functions', {}).items():
            console.print(f"{indent}    Function: {func_name}")
            if include_signatures and 'signature' in func_info:
                signature = func_info.get('signature', '')
                if signature:
                    console.print(f"{indent}      Signature: {signature}")
            if include_docs and func_info.get('docs'):
                console.print(f"{indent}      Docstring: {func_info['docs']}")
            if include_code and func_info.get('code'):
                console.print(f"{indent}      ""Code:\n"+f"{indent}      {func_info['code'].replace('\n', "\n"+f"{indent}      ")}")
        for class_name, class_info in node.contents.get('classes', {}).items():
            console.print(f"{indent}    Class: {class_name}")
            if include_docs and class_info.get('docs'):
                console.print(f"{indent}      Docstring: {class_info['docs']}")
            if include_code and class_info.get('code'):
                console.print(f"{indent}      Code:\n{indent}      {class_info['code'].replace('\n', f'\n{indent}      ')}")
            for method_name, method_info in class_info.get('methods', {}).items():
                console.print(f"{indent}      Method: {method_name}")
                if include_signatures and 'signature' in method_info:
                    signature = method_info.get('signature', '')
                    if signature:
                        console.print(f"{indent}        Signature: {signature}")
                if include_docs and method_info.get('docs'):
                    console.print(f"{indent}        Docstring: {method_info['docs']}")
                if include_code and method_info.get('code'):
                    console.print(f"{indent}        Code:\n{indent}        {method_info['code'].replace('\n', f'\n{indent}        ')}")
    if include_code and node.contents.get('code'):
        console.print(f"{indent}  Code:\n{indent}  {node.contents['code'].replace('\n', f'\n{indent}  ')}")
    for child_node in node.children.values():
        display_dependency_tree(
            child_node,
            level=level+1,
            include_docs=include_docs,
            include_signatures=include_signatures,
            include_code=include_code,
        )

def generate(
    directory_file_or_module: str = ".",
    sigs: bool = False,
    docs: bool = False,
    code: bool = False,
    who_imports_flag: bool = False,
    stats_flag: bool = False,
    site_packages: bool = False,
    show_broken: bool = True,
):
    """Build dependency graph and adjacency list."""
    path = Path(directory_file_or_module).resolve()
    if not path.exists():
        # Assume it's a module name
        path = Path.cwd()
        # No specific module filtering implemented in this context
    result = build_dependency_graph(
        path,
        include_site_packages=site_packages,
        include_docs=docs,
        include_signatures=sigs,
        include_code=code,
    )
    module_nodes = result.module_nodes
    adjacency_list = result.adjacency_list
    reverse_adjacency_list = result.reverse_adjacency_list
    broken_imports = result.broken_imports

    # Optionally print the dependency tree
    # Uncomment the following line to display the tree
    display_dependency_tree(result.root, include_docs=docs, include_signatures=sigs, include_code=code)

    # Display statistics if requested
    if stats_flag:
        stats = get_stats(module_nodes, adjacency_list, reverse_adjacency_list)
        display_stats(stats)

    # Display importers if requested
    if who_imports_flag:
        if len(sys.argv) > 1:
            target_module = sys.argv[1]
            who_imports(target_module, path, site_packages=site_packages, show=True)
        else:
            console.print("[bold red]Please specify a module name to find who imports it.[/bold red]")

    # Display broken imports with file paths
    if show_broken and broken_imports:
        render_broken_imports_text(broken_imports)

    return result

@click.command()
@click.argument("path", default=".", type=click.Path(exists=True, path_type=Path), required=False)
@click.option("--sigs", is_flag=True, help="Include function and method signatures.")
@click.option("--docs", is_flag=True, help="Include documentation strings.")
@click.option("--code", is_flag=True, help="Include source code snippets.")
@click.option("--who-imports", is_flag=True, help="Show who imports a specified module.")
@click.option("--stats", is_flag=True, help="Display dependency graph statistics.")
@click.option("--site-packages", is_flag=True, help="Include site-packages in the analysis.")
@click.option("--no-broken", "show_broken", is_flag=True, default=True, help="Do not show broken imports.")
def cli(
    path: Path,
    sigs: bool,
    docs: bool,
    code: bool,
    who_imports: bool,
    stats: bool,
    site_packages: bool,
    show_broken: bool,
):
    """Build and analyze a Python module dependency graph.

    PATH is the directory or file to analyze. Defaults to the current directory.
    """
    generate(
        directory_file_or_module=str(path),
        sigs=sigs,
        docs=docs,
        code=code,
        who_imports_flag=who_imports,
        stats_flag=stats,
        site_packages=site_packages,
        show_broken=show_broken,
    )

if __name__ == "__main__":
    cli()