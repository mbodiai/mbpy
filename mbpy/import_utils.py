from __future__ import annotations
import builtins
import importlib
import os
import sys
from pydoc import ErrorDuringImport
from types import ModuleType, SimpleNamespace
from typing import Callable, Type, TypeVar, cast, overload



import contextlib
import dis
import marshal
import sys
from types import CodeType
from typing import Any, Literal, TypeVar



from typing_extensions import TYPE_CHECKING, Any, Literal, TypeAlias, Union
if TYPE_CHECKING:
    import plotext
    from matplotlib import pyplot as pyplt
    import matplotlib as mplt
    MplModule: TypeAlias = mplt
    PltModule: TypeAlias = pyplt
    PlotextModule: TypeAlias = plotext

else:
    try:
        import plotext
        from matplotlib import pyplot as mplt
        PltModule: TypeAlias = mplt
        PlotextModule: TypeAlias = plotext
    except (ImportError, ModuleNotFoundError, AttributeError, NameError):
        PltModule = Any
        PlotextModule = Any
    lazy = Any
    eager = Any
    reload = Any

plt = None



def requires(module: str, wrapped_function: Callable | None = None):
    def inner(func):
        def wrapper(*args, **kwargs):
            if module not in globals():
                msg = f"Module {module} is not installed. Please install with `pip install {module}`"
                raise ImportError(msg)
            return func(*args, **kwargs)

        return wrapper

    if wrapped_function:
        return inner(wrapped_function)
    return inner


PlotBackend = Literal[
    "matplotlib",  # Default matplotlib backend
    "agg",
    "cairo",
    "pdf",
    "pgf",
    "ps",
    "svg",
    "template",
    "widget",
    "qt5",
    "qt6",
    "tk",
    "gtk3",
    "wx",
    "qt4",
    "macosx",
    "nbagg",
    "notebook",
    "inline",
    "ipympl",
    "plotly",
    "tkagg",
    "tcl-tk",
    "tcl-tkagg",
]

PlotBackendT = TypeVar("PlotBackendT", bound=PlotBackend)
PlotTextT = TypeVar("PlotTextT", bound=PlotextModule)
MatplotlibT = TypeVar("MatplotlibT", bound=PltModule)


@overload
def import_plt(backend: Literal["plotext"] | PlotTextT) -> PlotTextT: ...

@overload
def import_plt(backend: Literal["matplotlib"] | MatplotlibT) -> MatplotlibT: ...

def import_plt(backend: PlotBackend | Literal["plotext"] | MatplotlibT | PlotTextT) -> Union[PlotTextT, MatplotlibT]: # type: ignore [no-untyped-def]
    try:
        global plt
        if isinstance(backend, Literal["plotext"]):
            return cast(PlotTextT, smart_import("plotext"))

        if isinstance(backend,PlotBackend):
            backend = "tkagg" if sys.platform == "darwin" else backend  # Use tkagg backend on macOS
        mpl = cast(MplModule, smart_import("matplotlib"))
        mpl.use(backend if isinstance(backend, str) else "tkagg")
        return cast(MatplotlibT, smart_import("matplotlib.pyplot"))

    except (ImportError, AttributeError, NameError) as e:
        if sys.platform == "darwin" and isinstance(backend, str):
            backend = "tcl-tk" if backend.lower() in ("tk", "tkagg") else backend
            msg = f"Failed to import {backend} backend. Hint: Install with `brew install {backend}`"

        msg = f"Failed to import {backend} backend. Hint: Install with `pip install {backend}`"
        raise ImportError(msg) from e



def reload(module: str):
    if module in globals():
        return importlib.reload(globals()[module])
    return cast(ModuleType, importlib.import_module(module))


T = TypeVar("T")
# Lazy import functionality
def import_lazy(module_name: str) -> ModuleType:
    def lazy_module(*args, **kwargs):
        return cast(ModuleType,importlib.import_module(module_name.split(".")[0]))

    return cast(ModuleType,lazy_module)


def importfile(path):
    """Import a Python source file or compiled file given its path."""
    magic = importlib.util.MAGIC_NUMBER
    with open(path, 'rb') as file:
        is_bytecode = magic == file.read(len(magic))
    filename = os.path.basename(path)
    name, ext = os.path.splitext(filename)
    if is_bytecode:
        loader = importlib._bootstrap_external.SourcelessFileLoader(name, path)
    else:
        loader = importlib._bootstrap_external.SourceFileLoader(name, path)
    # XXX We probably don't need to pass in the loader here.
    spec = importlib.util.spec_from_file_location(name, path, loader=loader)
    try:
        return importlib._bootstrap._load(spec)
    except BaseException as err:
        raise ImportError(path, err)


def safeimport(path, forceload=0, cache={}, debug=False):
    """Import a module; handle errors; return None if the module isn't found.

    If the module *is* found but an exception occurs, it's wrapped in an
    ErrorDuringImport exception and reraised.  Unlike __import__, if a
    package path is specified, the module at the end of the path is returned,
    not the package at the beginning.  If the optional 'forceload' argument
    is 1, we reload the module from disk (unless it's a dynamic extension).
    """
    try:
        # If forceload is 1 and the module has been previously loaded from
        # disk, we always have to reload the module.  Checking the file's
        # mtime isn't good enough (e.g. the module could contain a class
        # that inherits from another module that has changed).
        if forceload and path in sys.modules and path not in sys.builtin_module_names:
            # Remove the module from sys.modules and re-import to try
            # and avoid problems with partially loaded modules.
            # Also remove any submodules because they won't appear
            # in the newly loaded module's namespace if they're already
            # in sys.modules.
            subs = [m for m in sys.modules if m.startswith(path + '.')]
            for key in [path] + subs:
                # Prevent garbage collection.
                cache[key] = sys.modules[key]
                del sys.modules[key]
        module = importlib.import_module(path)
    except BaseException as err:
        # Did the error occur before or after the module was found?
        if path in sys.modules:
            # An error occurred while executing the imported module.
            raise ImportError(sys.modules[path].__file__, err)
        if type(err) is SyntaxError:
            # A SyntaxError occurred before we could execute the module.
            raise ImportError(err.filename, err)
        if isinstance(err, ImportError) and err.name == path:
            # No such module in the path.
            return None

        # Some other error occurred during the importing process.
        import warnings
        warnings.warn(f"Error importing {path}: {err}",stacklevel=5)
        if debug:
            import traceback
            traceback.print_exc()
            raise
        return None
    return module


def locate(path, forceload=0,debug=False):
    """Locate an object by name or dotted path, importing as necessary."""
    parts = [part for part in path.split('.') if part]
    module, n = None, 0
    while n < len(parts):
        nextmodule = safeimport('.'.join(parts[:n + 1]), forceload,debug=debug)
        if nextmodule: module, n = nextmodule, n + 1
        else: break
    obj = module if module else builtins
    for part in parts[n:]:
        try:
            obj = getattr(object, part)
        except AttributeError:
            return None
    return obj


def resolve(thing, forceload=0,debug=False) -> tuple[Any, str] | None:
    """Given an object or a path to an object, get the object and its name."""
    if isinstance(thing, str):
        obj = locate(thing, forceload,debug=debug)
        if obj is None:
            return None
        return obj, thing

    name = getattr(thing, '__name__')
    if name is None:
        return None
    return thing, name

_warned = {}

_cache = {}
def get_cached(name: str) -> Any:
    if name in _cache:
        return _cache[name]
    if name == "importlib.import_module":
        from importlib import import_module
        _cache[name] = import_module
        return import_module
    if name == "importlib.reload":
        from importlib import reload
        _cache[name] = reload
        return reload
    if name == "sys":
        import sys
        _cache[name] = sys
        return sys
    if name == "pathlib.Path":
        from pathlib import Path
        _cache[name] = Path
        return Path
    if name == "logging":
        from mbpy import log as logging
        _cache[name] = logging
        return logging
    return _cache[name]

def smart_import(name: str,
                 mode: Literal["lazy", "eager", "reload",
                               "type_safe_lazy"] = "eager",
                 suppress_warnings: bool = False,debug=False) -> Any:
    """Import a module and return the resolved object. Supports . and : delimeters for classes and functions."""
    if name in _cache:
        return _cache[name]
    if not TYPE_CHECKING:
        sys = get_cached("sys")
        import_module = get_cached("importlib.import_module")
        reload = get_cached("importlib.reload")
        logging = get_cached("logging")
    else:
        import sys
        from importlib import import_module, reload

        from mbpy import log as logging


    name = name.replace(":", ".")
    if name in _cache:
        return _cache[name]
    try:
        resolved_obj, _ = resolve(name,debug=debug) or (None, None)
        if resolved_obj is not None and mode != "reload":  
            _cache[name] = resolved_obj
            return resolved_obj
        
        # Extract module path and attribute
        parts = name.split('.')
        module_path = '.'.join(parts[:-1])  # Get everything except last part
        attr_name = parts[-1]  # Get last part
        
        try:
            module = import_module(module_path)
            if hasattr(module, attr_name):
                _cache[name] = getattr(module, attr_name)
                return _cache[name]
        except Exception:
            pass


        if mode == "lazy" and resolved_obj:
            _cache[name] = import_lazy(name)
            return _cache[name]
     

        # Import the module or reload if needed
        module_name = name.split(".")[0]
        module = import_module(module_name)
        resolved, _ = resolve(name) or (None, None)
        return reload(module) if mode == "reload" else resolved

    except (ImportError, AttributeError, NameError, ErrorDuringImport) as e:
        # Handle type_safe_lazy mod
        if not suppress_warnings and not _warned.get(name) and mode == "type_safe_lazy":
            _warned[name] = True
            logging.warning(f"'type_safe_lazy' mode will hide errors from attributes not found in [bold blue]{name}[/bold blue]")
        if mode == "type_safe_lazy":

            class Namespace:
                def __init__(self,*args, **kwargs):
                    for k, v in kwargs.items():
                        setattr(self, k, v)
                def __call__(self, *args, **kwargs):

                    return import_lazy(name)(*args, **kwargs)

            s = Namespace(**{name.split(".")[0]: import_lazy(name)})
            return s

        msg = f"Module {name} not found. Install with `pip install `{name}`"
        if debug:
            import traceback
            traceback.print_exc()
            raise ImportError(msg) from e
        raise ModuleNotFoundError(f"Module {name} not found. Install with `pip install `{name}`") from e


def default_export(
    obj: T,
    *,
    key: str | None = None,
) -> T:
    """Assign a function to a module's __call__ attr.

    Args:
        obj: function to be made callable
        key (str): module name as it would appear in sys.modules

    Returns:
        Callable[..., T]: the function passed in

    Raises:
        AttributeError: if key is None and exported obj no __module__ attr
        ValueError: if key is not in sys.modules

    """
    try:
        _module: str = key or obj.__module__
    except AttributeError as e:
        msg = f"Object {obj} has no __module__ attribute. Please provide module key"
        raise AttributeError(msg) from e

    class ModuleCls(ModuleType):
        def __call__(self, *args: Any, **kwargs: Any) -> T:
            return cast(T, obj(*args, **kwargs))  # type: ignore[operator]

    class ModuleClsStaticValue(ModuleCls):
        def __call__(self, *args: Any, **kwargs: Any) -> T:
            return obj

    mod_cls = ModuleCls if callable(obj) else ModuleClsStaticValue

    try:
        sys.modules[_module].__class__ = mod_cls
    except KeyError as e:
        msg = f"{_module} not found in sys.modules"
        raise ValueError(msg) from e
    return obj


@default_export
def make_callable(obj: Callable[..., T], *, key: str | None = None) -> Callable[..., T]:
    """Assign a function to a module's __call__ attr.

    Args:
        obj: function to be made callable
        key (str): module name as it would appear in sys.modules

    Returns:
        Callable[..., T]: the function passed in

    """
    return default_export(obj=obj, key=key)


def bootstrap_third_party(modname: str, location: str) -> ModuleType:
    """Bootstrap third-party libraries with debugging."""
    import sys
    from importlib import import_module
    from importlib.util import find_spec, module_from_spec

    try:
        # Find the module spec
        spec = find_spec(modname)
        if not spec:
            msg = f"Module {modname} not found"
            raise ImportError(msg)  # noqa: TRY301

        # Load the module
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Import the parent module at the given location
        new_parent = import_module(location)
        qualified_name = f"{location}.{modname.split('.')[-1]}"

        # Debugging: print information about module and parent
        print(f"Loading module {modname} into {qualified_name}")

        # Attach the module to the parent
        setattr(new_parent, modname.split(".")[-1], mod)
        sys.modules[qualified_name] = mod

        # Update the globals with the new module
        globals().update({qualified_name: mod})
        globals().update({modname: mod})

        # # Recursively bootstrap submodules if necessary, skipping non-modules
        # for k, v in mod.__dict__.items():
        #     if isinstance(v, ModuleType) and k not in sys.modules and v.__name__.startswith(modname):
        #         bootstrap_third_party(k, qualified_name)

        return mod
    except Exception as e:
        # Debugging: Catch any errors and print the module causing issues
        print(f"Error loading module {modname} into {location}: {str(e)}")
        raise


_T = TypeVar("_T")



def requires(module: str, wrapped_function: Callable | None = None):
    def inner(func):
        def wrapper(*args, **kwargs):
            if module not in globals():
                msg = f"Module {module} is not installed. Please install with `pip install {module}`"
                raise ImportError(msg)
            return func(*args, **kwargs)

        return wrapper

    if wrapped_function:
        return inner(wrapped_function)
    return inner

