





from mbpy.import_utils import smart_import
from typing_extensions import Literal, TypedDict
from dataclasses import asdict, dataclass, field
from contextvars import Context
from mbpy.import_utils import smart_import
from mbpy.helpers._cache import acache, cache
from pathlib import Path

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Any, Dict,  Optional, TypedDict, TypeVar, Union, Callable, Iterable, Tuple, Generic, TypedDict,ParamSpec
    import asyncio
    import importlib.util
    import os
    import re
    import signal
    import sys
    from asyncio.taskgroups import TaskGroup
    from collections.abc import Callable
    from dataclasses import dataclass, field
    from pathlib import Path
    from urllib.parse import unquote, urlparse

    import tomlkit

    from mbpy.collect import PathLike, PathType




class UploadInfo(TypedDict, total=False):
    version: str | None
    upload_time: str

class PyPackageInfo(TypedDict, total=False):
    name: str
    version: str
    author: str
    summary: str
    description: str
    latest_release: "UploadInfo"
    earliest_release: "UploadInfo"
    urls: dict[str, str]
    github_url: str
    requires_python: str
    releases: list[dict[str, UploadInfo]] | None
    source: str | None

class CPackageInfo(TypedDict, total=False):
    name: str
    version: str
    spec: str
    conditions: str | None
    path: str | None
    repo: str | None
    manager: Literal["apt","brew","yum","conan"]


class uname_result:
    sys = smart_import("sys")
    Final = smart_import("typing.Final")
    if sys.version_info >= (3, 10):
        __match_args__: Final = ("sysname", "nodename", "release", "version", "machine")

    @property
    def sysname(self) -> str: ...
    @property
    def nodename(self) -> str: ...
    @property
    def release(self) -> str: ...
    @property
    def version(self) -> str: ...
    @property
    def machine(self) -> str: ...

@dataclass
class SystemSettings:
    ccompiler: str
    cxxcompiler: str
    cppflags: str
    ld_flags: str
    ldc_flags: str
    ldcxx_flags: str
    arch: str
    build_parallel: int | None
    uname: str | None | uname_result
    machine: str
    abi_flag: str
    sizes: dict[str, int] | None = field(default_factory=dict)

    @classmethod
    def detect(cls) -> "SystemSettings":
        if TYPE_CHECKING:
            from sysconfig import get_config_vars
            import shutil
            import os
        else:
            get_config_vars = smart_import("sysconfig.get_config_vars")
            shutil = smart_import("shutil")
            os = smart_import("os")
        config_vars = get_config_vars()
        sizes = {k: int(v) for k, v in config_vars.items() if k.startswith("SIZEOF_")}
        return cls(
            ccompiler=shutil.which(config_vars.get("CC", "")),
            cxxcompiler=shutil.which(config_vars.get("CXX", "")),
            cppflags=config_vars.get("CPPFLAGS", ""),
            ld_flags=config_vars.get("LDFLAGS", ""),
            ldc_flags=config_vars.get("LDCFLAGS", ""),
            ldcxx_flags=config_vars.get("LDCXXSHARED", ""),
            arch=config_vars.get("MULTIARCH", ""),
            build_parallel=os.cpu_count(),
            uname=os.uname(),
            machine=os.uname().machine,
            sizes=sizes,
            abi_flag=sys.abiflags,

        )

@dataclass
class CDependency:
    source_paths: list[str] | None = field(default=None)
    abi_version: int | None = field(default=None)
    c_standard: int | None = field(default=None)
    cxx_standard: int | None = field(default=None)
    shared_libs: list[str] | None = field(default=None)
    git: bool = False

    def __post_init__(self):
        self.source_paths = self.source_paths or []
        self.abi_version = self.abi_version or 0
        self.c_standard = self.c_standard or 11
        self.shared_libs = self.shared_libs or []
        self.git = any("git+" in path for path in self.source_paths)

    @classmethod
    async def afrom_toml(cls, name: str, toml_path: "PathType" = "pyproject.toml") -> "CDependency":
        if TYPE_CHECKING:
            from mbpy.pkg.toml import aget_toml_config
        else:
            aget_toml_config = smart_import("mbpy.pkg.toml.aget_toml_config")

        deps = await aget_toml_config(pyproject_path=toml_path)
        content = deps.tools.get("mb", {}).get("system", {}).get(name, {})
        if not content:
            raise ValueError(f"Dependency {name} not found in pyproject.toml")

        specs = cls()
        for key, value in content.items():
            if key == "source_paths":
                specs.source_paths = value
            elif key == "abi_version":
                specs.abi_version = value
            elif key == "c_standard":
                specs.c_standard = value
            elif key == "shared_libs":
                specs.shared_libs = value

        return specs

    @classmethod
    def from_cmake(cls, cmake_path: "PathType") -> "CDependency":
        Path = smart_import("pathlib.Path")
        from mbpy.helpers.traverse import search_parents_for_file, search_children_for_file
        try:
            cmake_path = search_parents_for_file("CMakeLists.txt", cwd=Path.cwd())
            content = cmake_path.read_text()
        except FileNotFoundError:
            try:
                cmake_path = search_children_for_file("CMakeLists.txt", cwd=Path.cwd())
            except FileNotFoundError:
                logging.warning("CMakeLists.txt not found in current or parent directories.")
                raise

        specs = cls()
        for line in content.splitlines():
            if "TREE_SITTER_ABI_VERSION" in line and "set(" in line.lower():
                try:
                    specs.abi_version = int(line.split()[-1].rstrip(")"))
                except ValueError:
                    pass

        return specs

    @classmethod
    async def afrom_cmake(cls, cmake_path: "Path") -> "CDependency":
        from mbpy.helpers.traverse import search_parents_for_file, search_children_for_file
        try:
            cmake_path = await asearch_parents_for_file("CMakeLists.txt", cwd=Path.cwd())
            content = cmake_path.read_text()
        except FileNotFoundError:
            try:
                cmake_path = await asearch_children_for_file("CMakeLists.txt", cwd=Path.cwd())
            except FileNotFoundError:
                logging.warning("CMakeLists.txt not found in current or parent directories.")
                raise

        specs = cls()
        for line in content.splitlines():
            if "TREE_SITTER_ABI_VERSION" in line and "set(" in line.lower():
                try:
                    specs.abi_version = int(line.split()[-1].rstrip(")"))
                except ValueError:
                    pass

        return specs

@dataclass
class Project:

    system: SystemSettings = field(default_factory=SystemSettings.detect)
    c: list[CDependency] | None = field(default_factory=list)
    python: "list[Dependency] | None" = field(default_factory=list)

    def getcflags(self) -> str:
        return f"{self.system.cppflags} {self.system.arch}"

    def getenv(self) -> dict[str, str]:
        return asdict(self.system)
    
    @classmethod
    def fromlist(cls, deps: "list[str]") -> "Project":
        try:
            c = [CDependency.from_cmake(cmake) for cmake in deps]
        except Exception as e:
            console = smart_import("rich.console.Console")()
            console.print(f"Failed to parse C dependencies: {e}")
            c = []
        
        try:
            python = [Dependency(dep) for dep in deps if not dep.endswith(".cmake")]
        except Exception as e:

            python = []
        return cls(c=c, python=python)
    @classmethod
    def fromtoml(cls, toml_path: "PathType" = "pyproject.toml") -> "Project":
        if TYPE_CHECKING:
            from mbpy.pkg.toml import get_toml_config
        else:
            get_toml_config = smart_import("mbpy.pkg.toml.get_toml_config")
        return get_toml_config(pyproject_path=toml_path)
       
    def __post_init__(self):
        from mbpy.pkg.toml import get_toml_config
        self.system = self.system or SystemSettings.detect()    
        self.python = self.python if self.python == [] else get_toml_config().python
        self.c = self.c if self.c == [] else [CDependency.from_cmake(cmake) for cmake in Path.cwd().rglob("CMakeLists.txt")]


def normalize_path(path_str: "PathLike") -> Path:
    """Normalize a path string to a Path object."""
    Path = smart_import("pathlib.Path")
    os = smart_import("os")
    re = smart_import("re")
    urlparse = smart_import("urllib.parse.urlparse")
    unquote = smart_import("urllib.parse.unquote")

    if path_str.startswith("file://"):
        # Parse the URI
        url = urlparse(path_str)
        # Handle Windows drive letters
        path = url.path.lstrip("/") if os.name == "nt" and re.match("^/[a-zA-Z]:", url.path) else url.path
        return Path(unquote(path))
    return Path(path_str)

def _version_check(
    pkg: str,
    v: str,
    min_v: str | None = None,
    max_v: str | None = None,
    raise_error: bool = False,
) -> bool:
    from importlib.metadata import version, PackageNotFoundError
    
    parsed_v = version(v)
    parsed_min_version = version(min_v) if min_v else None
    parsed_max_version = version(max_v) if max_v else None

    if parsed_min_version is not None and parsed_v < parsed_min_version:
        msg = f"Mismatched version of {pkg}: expected >={min_v}, got {v}"
        if raise_error:
            raise RuntimeError(msg)
        logging.warning(f"{msg}. Some features may not work correctly.")
        return False

    if parsed_max_version is not None and parsed_v >= parsed_max_version:
        msg = f"Mismatched version of {pkg}: expected <{max_v}, got {v}"
        if raise_error:
            raise RuntimeError(msg)
        logging.warning(f"{msg}. Some features may not work correctly.")
        return False

    return True

@dataclass
class Condition:
    """Class for parsing and evaluating dependency conditions.
    
    Attributes:
        if_values: List of values to check against
        platforms: List of supported platforms 
        env_vars: Environment variable requirements
    """
    if_values: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    env_vars: dict[str, str] = field(default_factory=dict)

    @classmethod
    def parse(cls, condition_str: str) -> "Condition":
        """Parse a condition string into a Condition object.
        
        Args:
            condition_str: String containing condition requirements
            
        Returns:
            Condition object with parsed values
        """
        if_values: List[str] = []
        platforms: List[str] = []
        env_vars: Dict[str, str] = {}

        parts = [p.strip() for p in condition_str.split(";") if p.strip()]
        for part in parts:
            if part.startswith("if "):
                if_values = [v.strip() for v in part[3:].split(",")]
            elif part.startswith("platform "):
                platforms = [p.strip() for p in part[9:].split(",")]
            elif "=" in part:
                key, value = part.split("=", 1)
                env_vars[key.strip()] = value.strip()

        return cls(if_values, platforms, env_vars)

    def evaluate(self, platform: str, env: dict[str, str], value: str) -> bool:
        """Evaluate if conditions are met.
        
        Args:
            platform: Current platform string
            env: Environment variable dict
            value: Value to check against if_values
            
        Returns:
            True if all conditions are met, False otherwise
        """
        if self.if_values and value not in self.if_values:
            return False

        if self.platforms and platform not in self.platforms:
            return False

        return all(env.get(env_key) == env_val for env_key, env_val in self.env_vars.items())
@cache
def isgit(source: "PathType") -> bool:
    Path = smart_import("pathlib.Path")
    source = str(source)
    isg = (
        source.startswith(("git+", "hg+", "svn+", "bzr+")) or
        (source.startswith("http") and "github.com" in source) or
        ("/" in source and not Path(source[:100]).exists()) and\
        not source.startswith("file://") and not "@" in source 
    )
    return isg


def iseditable(source: str) -> bool:
    source = source if isinstance(source, str) else source.install_cmd
    return source.startswith("-e") or "/" in source or "-e" in source

@cache
def exists(source: str) -> bool:
    return Path(source[:250]).exists()

@cache
def isatformat(source: "str| Dependency") -> bool:
    """Check if string is in package @ location format."""
    if not TYPE_CHECKING:
        re = smart_import("re")
    source = source if isinstance(source, str) else source.install_cmd
    if isinstance(source, (str, bytes)):
        return re.match(r"^[a-zA-Z0-9_\-]+ @ [a-zA-Z0-9_\-:/\.]+$", source) is not None
    return False

# @cache
# def extract_name_source_from_editable(source: str) -> tuple[str, str]:
#     """Extracts the name and source from an editable package string in the format '-e <source>'.

#     Args:
#         source (str): The input string in the format '-e <source>'.

#     Returns:
#         Tuple[str, str]: A tuple containing the name and source.
#     """
#     if isgit(source):
#         return extract_name_and_source_from_git(source)
#     name = source[3:].strip()
#     return name, source

def get_url(source: str) -> str:
    """Get the URL from a source string."""
    if not TYPE_CHECKING:
        urlparse = smart_import("urllib.parse.urlparse")
    if source.startswith("git+"):
        return source.split("git+")[1]
    if source.startswith("http"):
        return source
    if "@" in source:
        return source.split("@")[1]
    return source

def get_vcs(source: str) -> str:
    """Get the VCS type from a source string."""
    if source.startswith("git+"):
        return "git+" + source.split("git+")[1].split("@")[0]
    if source.startswith("http") and "github.com" in source:
        return "git+https://github.com" + source.split("https://github.com")[1].split("@")[0]
    raise ValueError(f"VCS type not supported in source: {source}")

def org_and_repo(source: str) -> tuple[str, str]:
    """Get the organization and repository from a source string."""
    if not TYPE_CHECKING:
        urlparse = smart_import("urllib.parse.urlparse")
    if source.startswith("git+"):
        source = source.split("git+")[1]
    if source.startswith("http") and "github.com" in source:
        source = source.split("https://github.com")[1]
    if source.startswith("http"):
        source = source.split("http://")[1]
    if source.startswith("https://"):
        source = source.split("https://")[1]
    if source.startswith("github.com"):
        source = source.split("github.com")[1]
    if source.startswith("/"):
        source = source[1:]
    if source.endswith(".git"):
        source = source[:-4]
    
    src = source.split("/")
    if len(src) != 2:
        raise ValueError(f"Invalid source format: {src}")
    return src[0], src[1]
# @cache
# def extract_name_and_source_from_git(source: str) -> tuple[str, str]:
#     """Modified to consistently return name, org, source"""
#     org,name  = org_and_repo(source)
#     return name, get_vcs(source)


# @cache
# def extract_name_and_source_from_at(source: str) -> "tuple[str, str]":
#     """Extracts the name and source from a string in the format 'name @ source'."""
#     # Don't process paths containing potentially dangerous commands
#     if any(cmd in source.lower() for cmd in ['rm ', 'rmdir', 'del ']):
#         logging.warning(f"Potentially dangerous command detected in path: {source}")
#         msg = f"Potentially dangerous command detected in path: {source}"
#         raise ValueError(msg)
        
#     match = re.match(r"^([a-zA-Z0-9_\-]+) @ ([a-zA-Z0-9_\-:/\.]+)$", source)
#     if match:
#         path = match.group(2)
#         # Validate it's a real path/URL
#         if path.startswith(('http://', 'https://', 'git://', 'file://')):
#             return match.group(1), path
#         if Path(path).exists():
#             return match.group(1), path
#     return source, source

# @cache
# def extract_name_and_source(source: str) -> "tuple[str, str]":
#     """Extracts the name and source from a package string.

#     Args:
#         source (str): The input string in one of the following formats:
#             - '-e <source>'
#             - 'git+<source>'
#             - 'name @ source'

#     Returns:
#         Optional[Tuple[str, str]]: A tuple containing the name and source if the pattern matches, otherwise None.
#     """
#     dangerous_commands = ['rm ', 'rmdir', 'del ', ';', '&&', '||']
#     cmd_lower = source.lower()
    
#     # Check for dangerous commands using word boundaries
#     if any(
#         cmd in cmd_lower.split() or  # Check for whole words
#         f" {cmd} " in f" {cmd_lower} "  # Check with spaces
#         for cmd in dangerous_commands
#     ):
#         raise ValueError("Potentially dangerous command detected")

#     if iseditable(source):
#         return extract_name_source_from_editable(source)
#     if isgit(source):
#         return extract_name_and_source_from_git(source)
#     if isatformat(source):
#         return extract_name_and_source_from_at(source)
#     return source, source



def validate_editable(command: "PathType", name: str | None = None, requirements=False) -> str:
    """Modified to handle Dependency objects properly."""
    if requirements and not isgit(command):
        return f"-e {str(Path(command).resolve())}"
    if isgit(command) and not requirements and "file/" not in command and "@" not in command:
        repo, org = org_and_repo(command)
        return f"{name} @ file://{Path.cwd() / 'tmp' / org / repo}"
    if requirements:
        return f"-e {str(Path(command).resolve())}"

    if "file:/" not in command and "@" not in command:
        return f"{name} @ file://{Path(command).resolve()}"
    return command
class RepoNotFoundError(Exception):
    """Raised when a repository is not found."""
    ...
@acache
async def _clone_git(url: str, clone_path: Path):
    """Clone and install a git repository.

    Args:
        install_cmd (str): The installation command
        package_name (str): Name of the package
        clone_path (Path): Path where to clone the repository

    Returns:
        tuple[str, str]: Base name and pip install command
    """
    if TYPE_CHECKING:
        from mbpy.pkg.git import clone_repo, repo_exists
        from mbpy.helpers._display import isverbose
        from mbpy import log as logging
    else:
        clone_repo = smart_import("mbpy.pkg.git").clone_repo
        repo_exists = smart_import("mbpy.pkg.git.repo_exists")
        isverbose = smart_import("mbpy.helpers._display.isverbose")
        logging = smart_import("mbpy.log")
        Text = smart_import("rich.text.Text")
        console = smart_import("rich.console.Console")()
    try:
        # Create clone directory
        Path(str(clone_path)).resolve().mkdir(parents=True, exist_ok=True)

        # Check if repository exists
        if not await repo_exists(url):
            raise RepoNotFoundError(f"Repository not found: {url}")



        async for line in await clone_repo(url, clone_path):

            console.print(Text.from_ansi(line))
            if "fatal:" in line or "error:" in line:
                logging.error(line)
                raise RuntimeError(f"Git clone failed: {line}")

        base = clone_path.stem
        return base,  f"file://{clone_path.resolve()}".removeprefix("-e ")

    except Exception as e:
        logging.error(f"Failed to clone/install {url}: {str(e)}")
        raise

cache.clear_all()

def _to_string(install_cmd: str, name: str, extras: str, version: str, conditions: str, requirements=False, editable=None) -> str:
    Path = smart_import("pathlib.Path")

    # For Git/VCS URLs or editable installs
    editable = editable or False
   
    if isgit(install_cmd) or iseditable(install_cmd):
        install_cmd = validate_editable(install_cmd, name=name, requirements=requirements)
        # print(f"_to_str:{install_cmd=}, {name=}, {extras=}, {version=}, {conditions=}, {requirements=}, {editable=}")
        return install_cmd
    # Handle version
    version_str = f"=={version}" if version else ""
    conditions_str = f"; {conditions}" if conditions else ""
    install_cmd = f"{name}{version_str}{extras}{conditions_str}"
    # print(f"_to_str:{install_cmd=}, {name=}, {extras=}, {version=}, {conditions=}, {requirements=}, {editable=}")
    return install_cmd

@dataclass
class Workspace:
    name: str
    packages: list[str] = field(default_factory=list)
    package_info: dict[str, Project] = field(default_factory=dict)
    subpackages: dict[str, list[str]] = field(default_factory=dict)
if TYPE_CHECKING:
    T = TypeVar("T")
    ParentT = Generic[T]
else:
    Generic = smart_import("typing.Generic")
    TypeVar = smart_import("typing.TypeVar")
    T = TypeVar("T")
    ParentT = Generic[T]

class Task(TypedDict, ParentT):
    name: str
    context: Context | None
    subtasks: "list[Task[T]] | None"
    parent_task: "Task[T] | None"
    depends_on: "list[str] | None"
    status: Literal["pending", "running", "completed"]
    result: T | None


class AsyncTreeNode(TypedDict, Generic[T]):
    name: str
    value: T
    children: "dict[str, AsyncTreeNode[T]] | None"
    context: Context | None

def with_async_init(async_init: "Callable") -> "Callable":
    def decorator(func: "Callable") -> "Callable":
        if func is None:
            raise ValueError(f"Function is None: {func}")
        async def wrapper(self, *args, **kwargs):
            cond: asyncio.Condition = self._async_init_condition
            if self._async_init_done:
                return await func(self, *args, **kwargs)
            if not cond.locked() or await cond.acquire():
                    async with cond:
                        out = await async_init(self)

                        self._async_init_done = True
                        cond.notify_all()
            
            if await self.done():
                out = await func(self, *args, **kwargs)
                return out
            else:
                raise RuntimeError(f"Failed to initialize {self} with {async_init}")
        return wrapper
    return decorator


SOURCE_KEYS = ["install_cmd","source","pip_install_cmd","project_install_cmd"]


@dataclass
class Dependency:
    """Handles dependency operations to ensure consistent formatting."""
    import asyncio
    install_cmd: str
    version_str: str = ""
    extras: list[str] | str = ""
    conditions: list[Condition] | str = ""
    min_version: str = ""
    max_version: str = ""
    pypi_info: PyPackageInfo = field(default_factory=lambda: PyPackageInfo())
    editable: bool = False
    upgrade: bool = False
    source: str | None = None
    dependencies: "list[Dependency]" = field(default_factory=list)
    group: str | None = None
    git: bool = False
    at: bool = False
    env: str | None = None
    author: str | None = None

    _base: str | None = field(repr=False,init=False,default=None)
    _groups: "dict[str, TaskGroup | dict[str, TaskGroup]]" = field(default_factory=dict, init=False, repr=False)
    _async_init_done: bool = field(default=False, init=False, repr=False)
    _to_string: str | None = field(default=None, init=False, repr=False)
    _tasks: "dict[str, Iterable[asyncio.Task] | asyncio.Task]" = field(default_factory=dict, init=False, repr=False)
    _async_init_condition: "asyncio.Condition" = field(default_factory=asyncio.Condition,repr=False,init=False)
    _requirements_name: str | None = field(default=None, init=False, repr=False)

    def __getstate__(self):
        """Return state for pickling."""
        state = self.__dict__.copy()
        # Remove unpicklable entries
        state.pop('_groups', None)
        state.pop('dependencies', None)
        state.pop('_async_init_done', None)
        state.pop('pypi_info', None)
        return state

    def __setstate__(self, state):
        """Set state when unpickling."""
        self.__dict__.update(state)
        # Reinitialize unpicklable attributes
        self._groups = {}
        self.dependencies = []
        self._async_init_done = False
        self.pypi_info = PyPackageInfo()

    def __deepcopy__(self, memo):
        """Support deep copying."""
        copy = smart_import("copy")
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k not in ('_groups', 'dependencies', '_async_init_done', 'pypi_info'):
                setattr(result, k, copy.deepcopy(v, memo))
        # Reinitialize special attributes
        result._groups = {}
        result.dependencies = []
        result._async_init_done = False
        result.pypi_info = PyPackageInfo()
        return result

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Dependency):
            return False
        return self.base == value.base and self.version == value.version

    def __hash__(self) -> int:
        return hash((self.install_cmd, self.version))

    @property
    async def requirements_name(self) -> str:
        if self._requirements_name is None:
            self._requirements_name = await self.to_string(requirements=True, editable=self.editable)
        return self._requirements_name

    @property
    async def pyproject_name(self) -> str:
        if self._pyproject_name is None:
            self._pyproject_name = await self.to_string(editable=self.editable, requirements=False)
        return self._pyproject_name

    @property
    async def project_dir(self) -> str:
        """Find the project directory in a string."""
        if TYPE_CHECKING:
            from pathlib import Path
            from mbpy.pkg.toml import afind_toml_file
        else:
            Path = smart_import("pathlib.Path")
            afind_toml_file = smart_import("mbpy.pkg.toml.afind_toml_file")

        toml_file = await afind_toml_file(cwd=Path.cwd())
        if toml_file:
            return str(toml_file.parent)
        return str(Path.cwd())

    async def find_toml(self) -> str:
        """Find the package name in a string."""
        if TYPE_CHECKING:
            from pathlib import Path
            from tomlkit import parse
            from mbpy.pkg.toml import aget_toml_config

        else:
            Path = smart_import("pathlib.Path")
            tomlkit = smart_import("tomlkit")
            aget_toml_config = smart_import("mbpy.pkg.toml.aget_toml_config")

        toml = await aget_toml_config(env=self.env,pyproject_path=self.project_dir)
        if toml:
            pyproject = tomlkit.parse(toml.read_text())
            if "project" in pyproject and "name" in pyproject["project"]:
                return pyproject["project"]["name"]
        return Path(self.project_dir).resolve().stem

    # def normalize(self) -> str:
    #     package_name = self.install_cmd
    #     return str(normalize_path(package_name.strip().lower().replace("-", "_")))

    @property
    def base(self) -> str:
        """Get the base name from a package name."""
        if self._base is not None:
            return self._base

        package_name = str(self.install_cmd)

        if package_name.startswith("git+"):
            parts = package_name.split("@")
            if len(parts) > 1:
                base = parts[-1].split("#")[0].split("/")[-1].split(".git")[0]
                self._base = base
                return base

        # Handle path-based dependencies
        if "/" in package_name:
            base = package_name.split("/")[-1]
            self._base = base
            return base

        # Remove editable flag
        if package_name.startswith("-e "):
            package_name = package_name[3:]

        # Handle @ notation
        if "@" in package_name:
            base = package_name.split("@")[0].strip()
            self._base = base
            return base

        # Extract base before version specifiers
        for operator in ["==", ">=", "<=", ">", "<", "~=", "!="]:
            if operator in package_name:
                base = package_name.split(operator)[0].strip()
                self._base = base
                return base

        self._base = package_name
        return package_name

    def getconditions(self) -> list[str]:
        """Get the package conditions from a package name."""
        package_name = self.install_cmd
        if ";" not in package_name:
            return []
        return package_name.split(";")[1:]

    @property
    def version(self) -> str:
        """Get the version string from a package name."""
        if self.version_str:
            return self.version_str
        self.version_str = self.getversion(self.install_cmd)
        return self.version_str
    
    @staticmethod
    def getversion(package_name:str,default=None) -> str:
        """Get the version string from a package name."""
        package_name = package_name.strip()
        package_name = package_name.split(";")[0]
        if "[" in package_name:
            package_name = package_name.split("[")[0]
        if default is not None:
            return default
        if package_name.startswith("git+"):
            # Extract version from URL if present
            parts = package_name.split("@")
            if len(parts) > 1:
                version_part = parts[-1].split("#")[0]
                return version_part if version_part else ""
            return ""
        for operator in ["==", ">=", "<=", ">", "<", "~=", "!="]:
            if operator in package_name:
                return package_name.split(operator)[1].strip()
        return ""

    def __post_init__(self):
        if not TYPE_CHECKING:
            re = smart_import("re")
        if isinstance(self.install_cmd, Dependency):
            dep = self.install_cmd
            self.install_cmd = dep.install_cmd
            self.version_str = dep.version_str
            self.extras = dep.extras
            self.conditions = dep.conditions
            self.min_version = dep.min_version
            self.max_version = dep.max_version
            self.pypi_info = dep.pypi_info
            self.editable = dep.editable
            self.upgrade = dep.upgrade
            self.source = dep.source
            self._base = dep._base
            self.dependencies = dep.dependencies
            self._async_init_done = dep._async_init_done
            self._to_string = dep._to_string
            self._tasks = dep._tasks
            self._async_init_condition = dep._async_init_condition
            self.group = dep.group
            self.git = dep.git
            self.at = dep.at
            self.env = dep.env
            self.author = dep.author
            return

        self.editable = iseditable(self.install_cmd)
        self.git = isgit(self.install_cmd)
        self.at = isatformat(self.install_cmd)


        if self.git:
            org,repo = org_and_repo(self.install_cmd)
            self._base = repo
            self.author = org
        


        self.extras = self.extras or self.getextras(self.install_cmd)
        self.conditions = self.conditions or  ";".join(self.getconditions())

        self.min_version = self.getversion(self.min_version)
        self.max_version = self.getversion(self.max_version)

        if self.git:
            pass
        else:
            match = re.search(r"\[([^\]]+)\]", self.install_cmd)
            self.extras = self.extras or (match.group(1) if match else "")

    async def _async_post_init(self):
        """Handles asynchronous tasks post-initialization."""
        if TYPE_CHECKING:
            from asyncio.taskgroups import TaskGroup
            from itertools import chain
        else:
            TaskGroup = smart_import("asyncio.taskgroups.TaskGroup")
            chain = smart_import("itertools.chain")

        if self.git:
            async with TaskGroup() as group:
                group.create_task(self.clone())
                self._tasks.setdefault("clone", group._tasks)
        return self
    
    async def done(self):
        chain = smart_import("itertools.chain")
        return all(chain.from_iterable(self._tasks.values()))
        


    @with_async_init(_async_post_init)
    async def install(self, executable: str | None = None, editable: bool | None = None, upgrade: bool | None = None, group: str | None = None):
        if TYPE_CHECKING:
            from mbpy.cmd import arun
            from mbpy.pkg.mpip import modify_dependencies
            import sys
            from mbpy import log as logging
            from mbpy.helpers._display import getconsole
            console = getconsole()
        else:
            arun = smart_import("mbpy.cmd.arun")
            sys = smart_import("sys")
            modify_dependencies = smart_import("mbpy.pkg.mpip.modify_dependencies")
            logging = smart_import("mbpy.log")
            console = smart_import("mbpy.helpers._display.getconsole")()
        editable = editable if editable is not None else self.editable
        upgrade = upgrade if upgrade is not None else self.upgrade
        executable = executable or sys.executable

        tostr = await self.to_string(editable=editable,requirements=True)
        if "@" in tostr:
            tostr = f"\'{tostr}\'"
        cmd = f"{executable} -m pip install {'--upgrade' if upgrade else ''} {tostr}".strip().replace("-e -e", "-e")
        logging.info(f"Running install command: {cmd}")
        result = await arun(cmd,show=True)
        self.version_str = await self.installed_version()
  
        if "error" in result.lower():
            console.print(result,style="bold red")
            logging.debug(result)
        else:
            await modify_dependencies(incoming=[self],action="install")


    
    async def  installed_version(self) -> str:
        arun = smart_import("mbpy.cmd.arun")
        sys = smart_import("sys")
        cmd = f"{sys.executable} -m pip show {await self.to_string()}"
        result = (await arun(cmd)).splitlines()
        for line in result:
            if "version" in line.lower():
                return line.split(":")[1].strip()
        return ""

    async def uninstall(self, executable: str | None = None):
        if TYPE_CHECKING:
            from mbpy.cmd import arun
            from mbpy.pkg.mpip import modify_dependencies
            import sys
        else:
            arun = smart_import("mbpy.cmd.arun")
            sys = smart_import("sys")
            modify_dependencies = smart_import("mbpy.pkg.mpip.modify_dependencies")
            logging = smart_import("mbpy.log")
            console = smart_import("mbpy.helpers._display.getconsole")()
        executable = executable or sys.executable

        cmd = f"{executable} -m pip uninstall -y {await self.to_string()}"
        logging.info(f"Running uninstall command: {cmd}")
        result = await arun(cmd,show=True)
     
        if "error" in result.lower():
            console.print(result,style="bold red")
        else:
            await modify_dependencies(incoming=[self],action="uninstall")
        return self

    @property
    async def project_install_cmd(self) -> str:
        """Get the project install command."""
        return (await self.to_string(requirements=False)).replace("-e ", "").replace("==", ">=")

    @with_async_init(_async_post_init)
    async def to_string(self, requirements: bool = False, editable: bool | None = None) -> str:
        """Construct the package string for dependencies."""
        if self._to_string is not None and "==" in self._to_string:
            return self._to_string

        editable = editable if editable is not None else self.editable
        requirements = requirements if requirements is not None else False
        # Use pip_install_cmd instead of install_cmd for git repos that have been cloned
        install_cmd = self.install_cmd
        name = self.base
        extras = self.extras
        version = self.version
        conditions = self.conditions
        min_version = self.min_version
        max_version = self.max_version

        self._to_string = _to_string(
            install_cmd,
            name,
            extras=extras,
            version=version,
            conditions=conditions,
            requirements=requirements,
            editable=editable,
        )
        return self._to_string

    async def clone(self):
        """Clone and install a git repository."""
        clone_path = Path(await self.project_dir) / "tmp" / self.author / self.base
        self.url = f"https://github.com/{self.author}/{self.base}.git"
        self._base, self._to_string = await _clone_git(
            self.url,
            clone_path,
        )


    @staticmethod
    def getextras(package_name) -> list[str] | str:
        """Get the package extras from a package name."""

        l = package_name.find("[")
        r = package_name.find("]")
        if l == -1 or r == -1:
            return ""
        extras = package_name[l + 1 : r].split(",")
        return [extra.strip() for extra in extras] if extras != [""] else ""

    def has(self) -> bool:
        """Return True if the dependency is installed."""
        importlib = smart_import("importlib")
        sys = smart_import("sys")

        try:
            has_dep = importlib.util.find_spec(self.install_cmd) is not None
            if not has_dep:
                return False
        except ModuleNotFoundError:
            return False

        min_version = self.min_version
        max_version = self.max_version
        if not self.has():
            return False
        return _version_check(
            pkg=self.install_cmd,
            v=self.version,
            min_v=min_version,
            max_v=max_version,
        )

    def imported(self) -> bool:
        return self.base in sys.modules

    def require(self, why: str) -> None:
        """Raise an ModuleNotFoundError if the package is not installed.

        Args:
            why (str): The reason why the package is required.

        Raises:
            ModuleNotFoundError: If the package is not installed.
        """
        if not self.has():
            raise ModuleNotFoundError(f"{self.install_cmd} is required {why}.") from None

    def require_at_version(
        self,
        why: str,
        min_version: str | None = None,
        max_version: str | None = None,
    ) -> None:
        self.require(why)

        _version_check(
            pkg=self.install_cmd,
            v=self.version,
            min_v=min_version,
            max_v=max_version,
            raise_error=True,
        )

    def warn_if_mismatch_version(
        self,
        min_version: str | None = None,
        max_version: str | None = None,
    ) -> bool:
        return _version_check(
            pkg=self.install_cmd,
            v=self.version,
            min_v=min_version,
            max_v=max_version,
        )

    def require_version(
        self,
        min_version: str | None = None,
        max_version: str | None = None,
    ) -> None:
        _version_check(
            pkg=self.install_cmd,
            v=self.version,
            min_v=min_version,
            max_v=max_version,
            raise_error=True,
        )

    @base.setter
    def base(self, value: str):
        self._base = value

    @property
    def extras_str(self) -> str:
        """Get the extras string from a package name."""
        if isinstance(self.extras, list):
            return f"[{', '.join(self.extras)}]" if self.extras else ""
        if isinstance(self.extras, str):
            return f"[{self.extras}]" if self.extras else ""
        return ""

def register_signal_handlers(loop: "asyncio.AbstractEventLoop"):
    """Register signal handlers for graceful shutdown."""
    if not TYPE_CHECKING:
        signal = smart_import("signal")
        asyncio = smart_import("asyncio")


    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s: asyncio.create_task(handle_signal(s)))
        except NotImplementedError:
            # Signal handlers are not implemented on some platforms (e.g., Windows)
            logging.warning(f"Signal {sig} not supported on this platform.")

async def handle_signal(sig: "signal.Signals"):
    """Handle received signals."""
    if not TYPE_CHECKING:
        asyncio = smart_import("asyncio")
        logging = smart_import("logging")


    logging.info(f"Received exit signal {sig.name}...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    logging.info("Cancelling outstanding tasks")
    await asyncio.gather(*tasks, return_exceptions=True)
    logging.info("Shutdown complete.")
    asyncio.get_event_loop().stop()


async def test():
    import asyncio
    import sys
    import traceback
    from rich.console import Console

    # cache.clear_cache()
    console = Console()
    try:
        dep = Dependency("mbodiai/mrender")
        await dep.install()
        result = await dep.to_string()
        console.print(f"String representation: {result}")
        console.print(f"Pip install command: {dep.pip_install_cmd}")
        console.print(f"Pyproject name: {await dep.pyproject_name}")
        console.print(f"Base name: {dep.base}")
        console.print(f"Version: {dep.version}")
        console.print(f"Extras: {dep.extras}")
        console.print(f"Conditions: {dep.conditions}")
        console.print(f"path: {await dep.project_dir}")
        console.print(f"has: {dep.has()}")
        console.print(f"imported: {dep.imported()}")
        console.print(f"pyproject install: {dep.project_install_cmd}")
        console.print(f"requirements: {await dep.requirements_name}")
        console.print(f"editable: {dep.editable}")
        console.print(f"git: {dep.git}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        traceback.print_exc()
        if isinstance(e, ExceptionGroup):
            for exc in e.exceptions:

                traceback.print_exc()
                console.print(f"[red]Caused by:[/red] {exc}")

            for t in asyncio.all_tasks():
                t.print_stack()
        sys.exit(1)






if __name__ == "__main__":
    import asyncio
    import signal
    import sys
    import mbpy
    import logging
    logging.basicConfig(level=logging.DEBUG,force=True)
    loop = asyncio.get_event_loop()
    # Graceful shutdown handler
    def shutdown(signal, loop):
        print(f"Received exit signal {signal.name}...")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    # Register shutdown signals
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: shutdown(s, loop))

    try:
        loop.run_until_complete(test())
    except asyncio.CancelledError:
        pass
    finally:
        loop.close()
        print("Shutdown complete.")
