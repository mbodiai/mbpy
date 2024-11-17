import importlib
import platform
import sys
import warnings
from contextlib import contextmanager, suppress
from types import ModuleType
from typing import Callable, Type, TypeVar, cast, overload

from typing_extensions import TYPE_CHECKING, Any, Literal, TypeAlias, Union

from mbpy.utils.collections import wraps

if TYPE_CHECKING:
    import plotext
    from matplotlib import pyplot as mplt
    PltModule: TypeAlias = mplt
    PlotextModule: TypeAlias = plotext

else:
    MatplotlibModule = Any
    PlotextModule = Any
    PltModule = Any
    lazy = Any
    eager = Any
    reload = Any

plt = None


def requires(module: str, wrapped_function: Callable | None = None):
    def inner(func):
        def wrapper(*args, **kwargs):
            if module not in globals():
                msg = f"Module {module} is not installed."
                raise ImportError(msg)
            return func(*args, **kwargs)

        return wrapper

    if wrapped_function:
        return inner(wrapped_function)
    return inner


@contextmanager
def _module_to_load(name):
    is_reload = name in sys.modules

    module = sys.modules.get(name)
    if not is_reload:
        # This must be done before open() is called as the 'io' module
        # implicitly imports 'locale' and would otherwise trigger an
        # infinite loop.
        module = type(sys)(name)
        # This must be done before putting the module in sys.modules
        # (otherwise an optimization shortcut in import.c becomes wrong)
        module.__initializing__ = True
        sys.modules[name] = module
    try:
        yield module
    except Exception:
        if not is_reload:
            with suppress(KeyError):
                del sys.modules[name]
    finally:
        module.__initializing__ = False


def set_package(fxn):
    """Set __package__ on the returned module.

    This function is deprecated.

    """

    @wraps(fxn)
    def set_package_wrapper(*args, **kwargs):
        warnings.warn(
            "The import system now takes care of this automatically; "
            "this decorator is slated for removal in Python 3.12",
            DeprecationWarning,
            stacklevel=2,
        )
        module = fxn(*args, **kwargs)
        if getattr(module, "__package__", None) is None:
            module.__package__ = module.__name__
            if not hasattr(module, "__path__"):
                module.__package__ = module.__package__.rpartition(".")[0]
        return module

    return set_package_wrapper


def set_loader(fxn):
    """Set __loader__ on the returned module.

    This function is deprecated.

    """
    @wraps(fxn)
    def set_loader_wrapper(self, *args, **kwargs):
        warnings.warn(
            "The import system now takes care of this automatically; "
            "this decorator is slated for removal in Python 3.12",
            DeprecationWarning,
            stacklevel=2,
        )
        module = fxn(self, *args, **kwargs)
        if getattr(module, "__loader__", None) is None:
            module.__loader__ = self
        return module

    return set_loader_wrapper


def module_for_loader(fxn):
    """Decorator to handle selecting the proper module for loaders.

    The decorated function is passed the module to use instead of the module
    name. The module passed in to the function is either from sys.modules if
    it already exists or is a new module. If the module is new, then __name__
    is set the first argument to the method, __loader__ is set to self, and
    __package__ is set accordingly (if self.is_package() is defined) will be set
    before it is passed to the decorated function (if self.is_package() does
    not work for the module it will be set post-load).

    If an exception is raised and the decorator created the module it is
    subsequently removed from sys.modules.

    The decorator assumes that the decorated function takes the module name as
    the second argument.

    """
    warnings.warn(
        "The import system now takes care of this automatically; "
        "this decorator is slated for removal in Python 3.12",
        DeprecationWarning,
        stacklevel=2,
    )

    @wraps(fxn)
    def module_for_loader_wrapper(self, fullname, *args, **kwargs):
        with _module_to_load(fullname) as module:
            module.__loader__ = self
            try:
                is_package = self.is_package(fullname)
            except (ImportError, AttributeError):
                pass
            else:
                if is_package:
                    module.__package__ = fullname
                else:
                    module.__package__ = fullname.rpartition(".")[0]
            # If __package__ was not set above, __import__() will do it later.
            return fxn(self, module, *args, **kwargs)

    return module_for_loader_wrapper


class _LazyModule(ModuleType):
    """A subclass of the module type which triggers loading upon attribute access."""

    def __getattribute__(self, attr):
        """Trigger the load of the module and return the attribute."""
        __spec__ = object.__getattribute__(self, "__spec__")
        loader_state = __spec__.loader_state
        with loader_state["lock"]:
            # Only the first thread to get the lock should trigger the load
            # and reset the module's class. The rest can now getattr().
            if object.__getattribute__(self, "__class__") is _LazyModule:
                # Reentrant calls from the same thread must be allowed to proceed without
                # triggering the load again.
                # exec_module() and self-referential imports are the primary ways this can
                # happen, but in any case we must return something to avoid deadlock.
                if loader_state["is_loading"]:
                    return object.__getattribute__(self, attr)
                loader_state["is_loading"] = True

                __dict__ = object.__getattribute__(self, "__dict__")

                # All module metadata must be gathered from __spec__ in order to avoid
                # using mutated values.
                # Get the original name to make sure no object substitution occurred
                # in sys.modules.
                original_name = __spec__.name
                # Figure out exactly what attributes were mutated between the creation
                # of the module and now.
                attrs_then = loader_state["__dict__"]
                attrs_now = __dict__
                attrs_updated = {}
                for key, value in attrs_now.items():
                    # Code that set an attribute may have kept a reference to the
                    # assigned object, making identity more important than equality.
                    if key not in attrs_then or id(attrs_now[key]) != id(attrs_then[key]):
                        attrs_updated[key] = value
                __spec__.loader.exec_module(self)
                # If exec_module() was used directly there is no guarantee the module
                # object was put into sys.modules.
                if original_name in sys.modules and id(self) != id(sys.modules[original_name]):
                    raise ValueError(
                        f"module object for {original_name!r} " "substituted in sys.modules during a lazy " "load"
                    )
                # Update after loading since that's what would happen in an eager
                # loading situation.
                __dict__.update(attrs_updated)
                # Finally, stop triggering this method.
                self.__class__ = ModuleType

        return getattr(self, attr)

    def __delattr__(self, attr):
        """Trigger the load and then perform the deletion."""
        # To trigger the load and raise an exception if the attribute
        # doesn't exist.
        self.__getattribute__(attr)
        delattr(self, attr)


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
            backend = "tkagg" if platform.system() == "Darwin" else backend  # Use tkagg backend on macOS
        mpl = cast(MatplotlibT, smart_import("matplotlib"))
        mpl.use(backend)
        return cast(MatplotlibT, smart_import("matplotlib.pyplot"))

    except (ImportError, AttributeError, NameError) as e:
        if platform.system() == "Darwin" and isinstance(backend, str):
            backend = "tcl-tk" if backend.lower() in ("tk", "tkagg") else backend
            msg = f"Failed to import {backend} backend. Hint: Install with `brew install {backend}`"
        msg = f"Failed to import {backend} backend. Hint: Install with `pip install {backend}`"
        raise ImportError(msg) from e



def reload(module: str):
    if module in globals():
        return importlib.reload(globals()[module])
    return cast(ModuleType, importlib.import_module(module))


T = TypeVar("T")
def smart_import(name: str, mode: Literal["lazy", "eager", "reload", "type_safe_lazy"] = "eager"):
    """Import a module and return the resolved object. Supports . and : delimeters for classes and functions."""
    import sys
    from importlib import import_module, reload
    from pydoc import resolve
    from typing import Any

    name = name.replace(":", ".")
    try:
        resolved_obj, _ = resolve(name)  or (None, None)
        # If object is resolved and not in reload mode
        if resolved_obj and mode != "reload":
            return resolved_obj

        # If module is already imported
        if name.split(".")[0] in sys.modules and mode != "reload":
            return resolved_obj

        if mode == "lazy":
            # Lazy import functionality
            import_lazy = LazyModule(name)

            return import_lazy(name)

        # Import the module or reload if needed
        module_name = name.split(".")[0]
        module = import_module(module_name)
        resolved, _ = resolve(name) or (None, None)
        return reload(module) if mode == "reload" else resolved

    except ImportError as e:
        # Handle type_safe_lazy mode
        if mode == "type_safe_lazy":
            return Any
        msg = f"Module {name} not found. Install with `pip install {name}`"
        raise NameError(msg) from e


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
