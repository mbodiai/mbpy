from __future__ import annotations
from typing import TYPE_CHECKING
from pathlib import Path

ENV_VARS = [
    "CONDA_PREFIX", "VIRTUAL_ENV", "MB_WS", "COLCON_PREFIX", "PYTHONPATH",

]
if TYPE_CHECKING:

    PYTHON_ENV_PATH = Path(sys.executable).parts[:-3]
    import logging
    import os
    import platform
    import sys
    from typing import Callable, List, Literal, Optional

    from rich.prompt import Prompt

    from collections import namedtuple
    from functools import singledispatch as simplegeneric
    import importlib
    import importlib.util
    import importlib.machinery
    import os
    import os.path
    import sys
    from types import ModuleType
    import warnings
    from mbpy.collect import PathLike as Path

else:
    pass

def getenv(env_str: str | None = None):
    import sys
    from pathlib import Path
    PYTHON_ENV_PATH = Path(sys.executable).parts[:-3]
    if env_str in (None, "default"):
        return ",".join(get_ordered_environs())
    if env_str == "system":
        return PYTHON_ENV_PATH
    return env_str


def get_ordered_environs() -> list[str]:
    """Get the ordered list of virtual environments active in the current session."""
    import sys
    from pathlib import Path
    PYTHON_ENV_PATH = Path(sys.executable).parts[:-3]
    import os
    envs: os._Environ[str] = os.environ
    env_keys = [key for key in envs if any(key == var for var in ENV_VARS)]
    # Prioritize Conda environments first
    env_keys.sort(key=lambda x: (x.startswith("CONDA_PREFIX"), envs[x]), reverse=True)

    return [envs[k].split(".")[-1] for k in env_keys]



def detect_active_interpreter() -> set[str]:
    """Attempt to detect a venv, virtualenv, poetry, or conda environment by looking for certain markers.

    If it fails to find any, it will fail with a message.
    """
    import sys
    import logging
    import os
    detection_funcs: list[Callable[[], str | None]] = [
        lambda: sys.executable,
        detect_conda_env_interpreter,
    ]
    active = set()
    for detect in detection_funcs:
        path = detect()

        if not path:
            continue
        if Path(path).exists():
            active.add(str(path))
    return active

def get_env_interpreter(env: str | None):
    if env == "conda":
        return detect_conda_env_interpreter()
    return sys.executable

def get_executable(env: str | None, multiple: Literal["auto", "ask","fail"] = "auto"):
    """Get the specified or detected python interpreter."""
    if env:
        return get_env_interpreter(env) or "python3"

    pythons = detect_active_interpreter()
    if len(pythons) == 0:
        logging.warning("No active python environment detected. Using the default python interpreter.")
        return sys.executable
    if len(pythons) > 1:
        if multiple == "fail":
            logging.error(f"Multiple active python environments detected: {pythons} and multiple is set to fail. You can change the behavior by setting multiple to 'auto' or 'ask'. See mbpy env --help for more information.")
            sys.exit(1)
        if multiple == "ask":
            return Prompt.ask(" Multiple python versions detected please Select the python interpreter to use", choices=pythons)

    return pythons.pop()





def determine_bin_dir() -> str:
    return "Scripts" if os.name == "nt" else "bin"


def in_virtual_environment() -> bool:
    """Return True if a venv/virtualenv is activated."""
    return hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )

def get_virtual_env() -> str | None:
    """Return the path to the virtual environment."""
    if in_virtual_environment():
        return sys.prefix
    return None

def in_conda_env() -> bool:
    return "CONDA_DEFAULT_ENV" in os.environ

def get_conda_env() -> str | None:
    """Return the path to the conda environment."""
    if in_conda_env():
        return os.environ["CONDA_PREFIX"]
    return None


def is_dockerized() -> bool:
    return Path("/.dockerenv").exists()


def is_python_isolated() -> bool:
    """Return True if not using system Python."""
    return in_virtual_environment() or in_conda_env() or is_dockerized()


def append_version(pkg_name: str, version: Optional[str]) -> str:
    """Qualify a version string with a leading '==' if it doesn't have one"""
    if version is None:
        return pkg_name
    if version == "":
        return pkg_name
    if version == "latest":
        return pkg_name
    return f"{pkg_name}=={version}"


def detect_conda_env_interpreter() -> str | None:
    import os
    # Env var mentioned in https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#saving-environment-variables.
    env_var = os.environ.get("CONDA_PREFIX")
    if not env_var:
        return None


    path = Path(env_var)

    # On POSIX systems, conda adds the python executable to the /bin directory. On Windows, it resides in the parent
    # directory of /bin (i.e. the root directory).
    # See https://docs.anaconda.com/free/working-with-conda/configurations/python-path/#examples.
    if os.name == "posix":  # pragma: posix cover
        path /= "bin"

    file_name = determine_interpreter_file_name()

    return str(path / file_name) if file_name else None



def determine_interpreter_file_name() -> str | None:
    impl_name_to_file_name_dict = {"CPython": "python", "PyPy": "pypy"}
    name = impl_name_to_file_name_dict.get(platform.python_implementation())
    if not name:
        return None
    if os.name == "nt":  # pragma: nt cover
        return name + ".exe"
    return sys.executable



# ModuleInfo = namedtuple('ModuleInfo', 'module_finder name ispkg')
# ModuleInfo.__doc__ = 'A namedtuple with minimal info about a module.'


# def read_code(stream):
#     # This helper is needed in order for the PEP 302 emulation to
#     # correctly handle compiled files
#     import marshal

#     magic = stream.read(4)
#     if magic != importlib.util.MAGIC_NUMBER:
#         return None

#     stream.read(12) # Skip rest of the header
#     return marshal.load(stream)


# def walk_packages(path=None, prefix='', onerror=None):
#     """Yields ModuleInfo for all modules recursively
#     on path, or, if path is None, all accessible modules.

#     'path' should be either None or a list of paths to look for
#     modules in.

#     'prefix' is a string to output on the front of every module name
#     on output.

#     Note that this function must import all *packages* (NOT all
#     modules!) on the given path, in order to access the __path__
#     attribute to find submodules.

#     'onerror' is a function which gets called with one argument (the
#     name of the package which was being imported) if any exception
#     occurs while trying to import a package.  If no onerror function is
#     supplied, ImportErrors are caught and ignored, while all other
#     exceptions are propagated, terminating the search.

#     Examples:

#     # list all modules python can access
#     walk_packages()

#     # list all submodules of ctypes
#     walk_packages(ctypes.__path__, ctypes.__name__+'.')
#     """

#     def seen(p, m={}):
#         if p in m:
#             return True
#         m[p] = True

#     for info in iter_modules(path, prefix):
#         yield info

#         if info.ispkg:
#             try:
#                 __import__(info.name)
#             except ImportError:
#                 if onerror is not None:
#                     onerror(info.name)
#             except Exception:
#                 if onerror is not None:
#                     onerror(info.name)
#                 else:
#                     raise
#             else:
#                 path = getattr(sys.modules[info.name], '__path__', None) or []

#                 # don't traverse path items we've seen before
#                 path = [p for p in path if not seen(p)]

#                 yield from walk_packages(path, info.name+'.', onerror)


# def iter_modules(path=None, prefix=''):
#     """Yields ModuleInfo for all submodules on path,
#     or, if path is None, all top-level modules on sys.path.

#     'path' should be either None or a list of paths to look for
#     modules in.

#     'prefix' is a string to output on the front of every module name
#     on output.
#     """
#     if path is None:
#         importers = iter_importers()
#     elif isinstance(path, str):
#         raise ValueError("path must be None or list of paths to look for "
#                         "modules in")
#     else:
#         importers = map(get_importer, path)

#     yielded = {}
#     for i in importers:
#         for name, ispkg in iter_importer_modules(i, prefix):
#             if name not in yielded:
#                 yielded[name] = 1
#                 yield ModuleInfo(i, name, ispkg)


# @simplegeneric
# def iter_importer_modules(importer, prefix=''):
#     if not hasattr(importer, 'iter_modules'):
#         return []
#     return importer.iter_modules(prefix)


# # Implement a file walker for the normal importlib path hook
# def _iter_file_finder_modules(importer, prefix=''):
#     if importer.path is None or not os.path.isdir(importer.path):
#         return

#     yielded = {}
#     import inspect
#     try:
#         filenames = os.listdir(importer.path)
#     except OSError:
#         # ignore unreadable directories like import does
#         filenames = []
#     filenames.sort()  # handle packages before same-named modules

#     for fn in filenames:
#         modname = inspect.getmodulename(fn)
#         if modname=='__init__' or modname in yielded:
#             continue

#         path = os.path.join(importer.path, fn)
#         ispkg = False

#         if not modname and os.path.isdir(path) and '.' not in fn:
#             modname = fn
#             try:
#                 dircontents = os.listdir(path)
#             except OSError:
#                 # ignore unreadable directories like import does
#                 dircontents = []
#             for fn in dircontents:
#                 subname = inspect.getmodulename(fn)
#                 if subname=='__init__':
#                     ispkg = True
#                     break
#             else:
#                 continue    # not a package

#         if modname and '.' not in modname:
#             yielded[modname] = 1
#             yield prefix + modname, ispkg

# iter_importer_modules.register(
#     importlib.machinery.FileFinder, _iter_file_finder_modules)


# try:
#     import zipimport
#     from zipimport import zipimporter

#     def iter_zipimport_modules(importer, prefix=''):
#         dirlist = sorted(zipimport._zip_directory_cache[importer.archive])
#         _prefix = importer.prefix
#         plen = len(_prefix)
#         yielded = {}
#         import inspect
#         for fn in dirlist:
#             if not fn.startswith(_prefix):
#                 continue

#             fn = fn[plen:].split(os.sep)

#             if len(fn)==2 and fn[1].startswith('__init__.py'):
#                 if fn[0] not in yielded:
#                     yielded[fn[0]] = 1
#                     yield prefix + fn[0], True

#             if len(fn)!=1:
#                 continue

#             modname = inspect.getmodulename(fn[0])
#             if modname=='__init__':
#                 continue

#             if modname and '.' not in modname and modname not in yielded:
#                 yielded[modname] = 1
#                 yield prefix + modname, False

#     iter_importer_modules.register(zipimporter, iter_zipimport_modules)

# except ImportError:
#     pass


# def get_importer(path_item):
#     """Retrieve a finder for the given path item

#     The returned finder is cached in sys.path_importer_cache
#     if it was newly created by a path hook.

#     The cache (or part of it) can be cleared manually if a
#     rescan of sys.path_hooks is necessary.
#     """
#     path_item = os.fsdecode(path_item)
#     try:
#         importer = sys.path_importer_cache[path_item]
#     except KeyError:
#         for path_hook in sys.path_hooks:
#             try:
#                 importer = path_hook(path_item)
#                 sys.path_importer_cache.setdefault(path_item, importer)
#                 break
#             except ImportError:
#                 pass
#         else:
#             importer = None
#     return importer


# def iter_importers(fullname=""):
#     """Yield finders for the given module name

#     If fullname contains a '.', the finders will be for the package
#     containing fullname, otherwise they will be all registered top level
#     finders (i.e. those on both sys.meta_path and sys.path_hooks).

#     If the named module is in a package, that package is imported as a side
#     effect of invoking this function.

#     If no module name is specified, all top level finders are produced.
#     """
#     if fullname.startswith('.'):
#         msg = "Relative module name {!r} not supported".format(fullname)
#         raise ImportError(msg)
#     if '.' in fullname:
#         # Get the containing package's __path__
#         pkg_name = fullname.rpartition(".")[0]
#         pkg = importlib.import_module(pkg_name)
#         path = getattr(pkg, '__path__', None)
#         if path is None:
#             return
#     else:
#         yield from sys.meta_path
#         path = sys.path
#     for item in path:
#         yield get_importer(item)


# def get_loader(module_or_name):
#     """Get a "loader" object for module_or_name

#     Returns None if the module cannot be found or imported.
#     If the named module is not already imported, its containing package
#     (if any) is imported, in order to establish the package __path__.
#     """
#     warnings._deprecated("pkgutil.get_loader",
#                          f"{warnings._DEPRECATED_MSG}; "
#                          "use importlib.util.find_spec() instead",
#                          remove=(3, 14))
#     if module_or_name in sys.modules:
#         module_or_name = sys.modules[module_or_name]
#         if module_or_name is None:
#             return None
#     if isinstance(module_or_name, ModuleType):
#         module = module_or_name
#         loader = getattr(module, '__loader__', None)
#         if loader is not None:
#             return loader
#         if getattr(module, '__spec__', None) is None:
#             return None
#         fullname = module.__name__
#     else:
#         fullname = module_or_name
#     return find_loader(fullname)


# def find_loader(fullname):
#     """Find a "loader" object for fullname

#     This is a backwards compatibility wrapper around
#     importlib.util.find_spec that converts most failures to ImportError
#     and only returns the loader rather than the full spec
#     """
#     warnings._deprecated("pkgutil.find_loader",
#                          f"{warnings._DEPRECATED_MSG}; "
#                          "use importlib.util.find_spec() instead",
#                          remove=(3, 14))
#     if fullname.startswith('.'):
#         msg = "Relative module name {!r} not supported".format(fullname)
#         raise ImportError(msg)
#     try:
#         spec = importlib.util.find_spec(fullname)
#     except (ImportError, AttributeError, TypeError, ValueError) as ex:
#         # This hack fixes an impedance mismatch between pkgutil and
#         # importlib, where the latter raises other errors for cases where
#         # pkgutil previously raised ImportError
#         msg = "Error while finding loader for {!r} ({}: {})"
#         raise ImportError(msg.format(fullname, type(ex), ex)) from ex
#     return spec.loader if spec is not None else None


# def extend_path(path, name):
#     """Extend a package's path.

#     Intended use is to place the following code in a package's __init__.py:

#         from pkgutil import extend_path
#         __path__ = extend_path(__path__, __name__)

#     For each directory on sys.path that has a subdirectory that
#     matches the package name, add the subdirectory to the package's
#     __path__.  This is useful if one wants to distribute different
#     parts of a single logical package as multiple directories.

#     It also looks for *.pkg files beginning where * matches the name
#     argument.  This feature is similar to *.pth files (see site.py),
#     except that it doesn't special-case lines starting with 'import'.
#     A *.pkg file is trusted at face value: apart from checking for
#     duplicates, all entries found in a *.pkg file are added to the
#     path, regardless of whether they are exist the filesystem.  (This
#     is a feature.)

#     If the input path is not a list (as is the case for frozen
#     packages) it is returned unchanged.  The input path is not
#     modified; an extended copy is returned.  Items are only appended
#     to the copy at the end.

#     It is assumed that sys.path is a sequence.  Items of sys.path that
#     are not (unicode or 8-bit) strings referring to existing
#     directories are ignored.  Unicode items of sys.path that cause
#     errors when used as filenames may cause this function to raise an
#     exception (in line with os.path.isdir() behavior).
#     """

#     if not isinstance(path, list):
#         # This could happen e.g. when this is called from inside a
#         # frozen package.  Return the path unchanged in that case.
#         return path

#     sname_pkg = name + ".pkg"

#     path = path[:] # Start with a copy of the existing path

#     parent_package, _, final_name = name.rpartition('.')
#     if parent_package:
#         try:
#             search_path = sys.modules[parent_package].__path__
#         except (KeyError, AttributeError):
#             # We can't do anything: find_loader() returns None when
#             # passed a dotted name.
#             return path
#     else:
#         search_path = sys.path

#     for dir in search_path:
#         if not isinstance(dir, str):
#             continue

#         finder = get_importer(dir)
#         if finder is not None:
#             portions = []
#             if hasattr(finder, 'find_spec'):
#                 spec = finder.find_spec(final_name)
#                 if spec is not None:
#                     portions = spec.submodule_search_locations or []
#             # Is this finder PEP 420 compliant?
#             elif hasattr(finder, 'find_loader'):
#                 _, portions = finder.find_loader(final_name)

#             for portion in portions:
#                 # XXX This may still add duplicate entries to path on
#                 # case-insensitive filesystems
#                 if portion not in path:
#                     path.append(portion)

#         # XXX Is this the right thing for subpackages like zope.app?
#         # It looks for a file named "zope.app.pkg"
#         pkgfile = os.path.join(dir, sname_pkg)
#         if os.path.isfile(pkgfile):
#             try:
#                 f = open(pkgfile)
#             except OSError as msg:
#                 sys.stderr.write("Can't open %s: %s\n" %
#                                  (pkgfile, msg))
#             else:
#                 with f:
#                     for line in f:
#                         line = line.rstrip('\n')
#                         if not line or line.startswith('#'):
#                             continue
#                         path.append(line) # Don't check for existence!

#     return path


# def get_data(package, resource):
#     """Get a resource from a package.

#     This is a wrapper round the PEP 302 loader get_data API. The package
#     argument should be the name of a package, in standard module format
#     (foo.bar). The resource argument should be in the form of a relative
#     filename, using '/' as the path separator. The parent directory name '..'
#     is not allowed, and nor is a rooted name (starting with a '/').

#     The function returns a binary string, which is the contents of the
#     specified resource.

#     For packages located in the filesystem, which have already been imported,
#     this is the rough equivalent of

#         d = os.path.dirname(sys.modules[package].__file__)
#         data = open(os.path.join(d, resource), 'rb').read()

#     If the package cannot be located or loaded, or it uses a PEP 302 loader
#     which does not support get_data(), then None is returned.
#     """

#     spec = importlib.util.find_spec(package)
#     if spec is None:
#         return None
#     loader = spec.loader
#     if loader is None or not hasattr(loader, 'get_data'):
#         return None
#     # XXX needs test
#     mod = (sys.modules.get(package) or
#            importlib._bootstrap._load(spec))
#     if mod is None or not hasattr(mod, '__file__'):
#         return None

#     # Modify the resource name to be compatible with the loader.get_data
#     # signature - an os.path format "filename" starting with the dirname of
#     # the package's __file__
#     parts = resource.split('/')
#     parts.insert(0, os.path.dirname(mod.__file__))
#     resource_name = os.path.join(*parts)
#     return loader.get_data(resource_name)


# _NAME_PATTERN = None

# def resolve_name(name):
#     """
#     Resolve a name to an object.

#     It is expected that `name` will be a string in one of the following
#     formats, where W is shorthand for a valid Python identifier and dot stands
#     for a literal period in these pseudo-regexes:

#     W(.W)*
#     W(.W)*:(W(.W)*)?

#     The first form is intended for backward compatibility only. It assumes that
#     some part of the dotted name is a package, and the rest is an object
#     somewhere within that package, possibly nested inside other objects.
#     Because the place where the package stops and the object hierarchy starts
#     can't be inferred by inspection, repeated attempts to import must be done
#     with this form.

#     In the second form, the caller makes the division point clear through the
#     provision of a single colon: the dotted name to the left of the colon is a
#     package to be imported, and the dotted name to the right is the object
#     hierarchy within that package. Only one import is needed in this form. If
#     it ends with the colon, then a module object is returned.

#     The function will return an object (which might be a module), or raise one
#     of the following exceptions:

#     ValueError - if `name` isn't in a recognised format
#     ImportError - if an import failed when it shouldn't have
#     AttributeError - if a failure occurred when traversing the object hierarchy
#                      within the imported package to get to the desired object.
#     """
#     global _NAME_PATTERN
#     if _NAME_PATTERN is None:
#         # Lazy import to speedup Python startup time
#         import re
#         dotted_words = r'(?!\d)(\w+)(\.(?!\d)(\w+))*'
#         _NAME_PATTERN = re.compile(f'^(?P<pkg>{dotted_words})'
#                                    f'(?P<cln>:(?P<obj>{dotted_words})?)?$',
#                                    re.UNICODE)

#     m = _NAME_PATTERN.match(name)
#     if not m:
#         raise ValueError(f'invalid format: {name!r}')
#     gd = m.groupdict()
#     if gd.get('cln'):
#         # there is a colon - a one-step import is all that's needed
#         mod = importlib.import_module(gd['pkg'])
#         parts = gd.get('obj')
#         parts = parts.split('.') if parts else []
#     else:
#         # no colon - have to iterate to find the package boundary
#         parts = name.split('.')
#         modname = parts.pop(0)
#         # first part *must* be a module/package.
#         mod = importlib.import_module(modname)
#         while parts:
#             p = parts[0]
#             s = f'{modname}.{p}'
#             try:
#                 mod = importlib.import_module(s)
#                 parts.pop(0)
#                 modname = s
#             except ImportError:
#                 break
#     # if we reach this point, mod is the module, already imported, and
#     # parts is the list of parts in the object hierarchy to be traversed, or
#     # an empty list if just the module is wanted.
#     result = mod
#     for p in parts:
#         result = getattr(result, p)
#     return result



# _ver_stages = {
#     # any string not found in this dict, will get 0 assigned
#     'dev': 10,
#     'alpha': 20, 'a': 20,
#     'beta': 30, 'b': 30,
#     'c': 40,
#     'RC': 50, 'rc': 50,
#     # number, will get 100 assigned
#     'pl': 200, 'p': 200,
# }


# def _comparable_version(version):
#     component_re = re.compile(r'([0-9]+|[._+-])')
#     result = []
#     for v in component_re.split(version):
#         if v not in '._+-':
#             try:
#                 v = int(v, 10)
#                 t = 100
#             except ValueError:
#                 t = _ver_stages.get(v, 0)
#             result.extend((t, v))
#     return result

# ### Platform specific APIs


# def libc_ver(executable=None, lib='', version='', chunksize=16384):

#     """ Tries to determine the libc version that the file executable
#         (which defaults to the Python interpreter) is linked against.

#         Returns a tuple of strings (lib,version) which default to the
#         given parameters in case the lookup fails.

#         Note that the function has intimate knowledge of how different
#         libc versions add symbols to the executable and thus is probably
#         only usable for executables compiled using gcc.

#         The file is read and scanned in chunks of chunksize bytes.

#     """
#     if not executable:
#         try:
#             ver = os.confstr('CS_GNU_LIBC_VERSION')
#             # parse 'glibc 2.28' as ('glibc', '2.28')
#             parts = ver.split(maxsplit=1)
#             if len(parts) == 2:
#                 return tuple(parts)
#         except (AttributeError, ValueError, OSError):
#             # os.confstr() or CS_GNU_LIBC_VERSION value not available
#             pass

#         executable = sys.executable

#         if not executable:
#             # sys.executable is not set.
#             return lib, version

#     libc_search = re.compile(b'(__libc_init)'
#                           b'|'
#                           b'(GLIBC_([0-9.]+))'
#                           b'|'
#                           br'(libc(_\w+)?\.so(?:\.(\d[0-9.]*))?)', re.ASCII)

#     V = _comparable_version
#     # We use os.path.realpath()
#     # here to work around problems with Cygwin not being
#     # able to open symlinks for reading
#     executable = os.path.realpath(executable)
#     with open(executable, 'rb') as f:
#         binary = f.read(chunksize)
#         pos = 0
#         while pos < len(binary):
#             if b'libc' in binary or b'GLIBC' in binary:
#                 m = libc_search.search(binary, pos)
#             else:
#                 m = None
#             if not m or m.end() == len(binary):
#                 chunk = f.read(chunksize)
#                 if chunk:
#                     binary = binary[max(pos, len(binary) - 1000):] + chunk
#                     pos = 0
#                     continue
#                 if not m:
#                     break
#             libcinit, glibc, glibcversion, so, threads, soversion = [
#                 s.decode('latin1') if s is not None else s
#                 for s in m.groups()]
#             if libcinit and not lib:
#                 lib = 'libc'
#             elif glibc:
#                 if lib != 'glibc':
#                     lib = 'glibc'
#                     version = glibcversion
#                 elif V(glibcversion) > V(version):
#                     version = glibcversion
#             elif so:
#                 if lib != 'glibc':
#                     lib = 'libc'
#                     if soversion and (not version or V(soversion) > V(version)):
#                         version = soversion
#                     if threads and version[-len(threads):] != threads:
#                         version = version + threads
#             pos = m.end()
#     return lib, version

# def _norm_version(version, build=''):

#     """ Normalize the version and build strings and return a single
#         version string using the format major.minor.build (or patchlevel).
#     """
#     l = version.split('.')
#     if build:
#         l.append(build)
#     try:
#         strings = list(map(str, map(int, l)))
#     except ValueError:
#         strings = l
#     version = '.'.join(strings[:3])
#     return version


# # Examples of VER command output:
# #
# #   Windows 2000:  Microsoft Windows 2000 [Version 5.00.2195]
# #   Windows XP:    Microsoft Windows XP [Version 5.1.2600]
# #   Windows Vista: Microsoft Windows [Version 6.0.6002]
# #
# # Note that the "Version" string gets localized on different
# # Windows versions.

# def _syscmd_ver(system='', release='', version='',

#                supported_platforms=('win32', 'win16', 'dos')):

#     """ Tries to figure out the OS version used and returns
#         a tuple (system, release, version).

#         It uses the "ver" shell command for this which is known
#         to exists on Windows, DOS. XXX Others too ?

#         In case this fails, the given parameters are used as
#         defaults.

#     """
#     if sys.platform not in supported_platforms:
#         return system, release, version

#     # Try some common cmd strings
#     import subprocess
#     for cmd in ('ver', 'command /c ver', 'cmd /c ver'):
#         try:
#             info = subprocess.check_output(cmd,
#                                            stdin=subprocess.DEVNULL,
#                                            stderr=subprocess.DEVNULL,
#                                            text=True,
#                                            encoding="locale",
#                                            shell=True)
#         except (OSError, subprocess.CalledProcessError) as why:
#             #print('Command %s failed: %s' % (cmd, why))
#             continue
#         else:
#             break
#     else:
#         return system, release, version

#     ver_output = re.compile(r'(?:([\w ]+) ([\w.]+) '
#                          r'.*'
#                          r'\[.* ([\d.]+)\])')

#     # Parse the output
#     info = info.strip()
#     m = ver_output.match(info)
#     if m is not None:
#         system, release, version = m.groups()
#         # Strip trailing dots from version and release
#         if release[-1] == '.':
#             release = release[:-1]
#         if version[-1] == '.':
#             version = version[:-1]
#         # Normalize the version and build strings (eliminating additional
#         # zeros)
#         version = _norm_version(version)
#     return system, release, version

# try:
#     import _wmi
# except ImportError:
#     def _wmi_query(*keys):
#         raise OSError("not supported")
# else:
#     def _wmi_query(table, *keys):
#         table = {
#             "OS": "Win32_OperatingSystem",
#             "CPU": "Win32_Processor",
#         }[table]
#         data = _wmi.exec_query("SELECT {} FROM {}".format(
#             ",".join(keys),
#             table,
#         )).split("\0")
#         split_data = (i.partition("=") for i in data)
#         dict_data = {i[0]: i[2] for i in split_data}
#         return (dict_data[k] for k in keys)


# _WIN32_CLIENT_RELEASES = [
#     ((10, 1, 0), "post11"),
#     ((10, 0, 22000), "11"),
#     ((6, 4, 0), "10"),
#     ((6, 3, 0), "8.1"),
#     ((6, 2, 0), "8"),
#     ((6, 1, 0), "7"),
#     ((6, 0, 0), "Vista"),
#     ((5, 2, 3790), "XP64"),
#     ((5, 2, 0), "XPMedia"),
#     ((5, 1, 0), "XP"),
#     ((5, 0, 0), "2000"),
# ]

# _WIN32_SERVER_RELEASES = [
#     ((10, 1, 0), "post2022Server"),
#     ((10, 0, 20348), "2022Server"),
#     ((10, 0, 17763), "2019Server"),
#     ((6, 4, 0), "2016Server"),
#     ((6, 3, 0), "2012ServerR2"),
#     ((6, 2, 0), "2012Server"),
#     ((6, 1, 0), "2008ServerR2"),
#     ((6, 0, 0), "2008Server"),
#     ((5, 2, 0), "2003Server"),
#     ((5, 0, 0), "2000Server"),
# ]

# def win32_is_iot():
#     return win32_edition() in ('IoTUAP', 'NanoServer', 'WindowsCoreHeadless', 'IoTEdgeOS')

# def win32_edition():
#     try:
#         try:
#             import winreg
#         except ImportError:
#             import _winreg as winreg
#     except ImportError:
#         pass
#     else:
#         try:
#             cvkey = r'SOFTWARE\Microsoft\Windows NT\CurrentVersion'
#             with winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, cvkey) as key:
#                 return winreg.QueryValueEx(key, 'EditionId')[0]
#         except OSError:
#             pass

#     return None

# def _win32_ver(version, csd, ptype):
#     # Try using WMI first, as this is the canonical source of data
#     try:
#         (version, product_type, ptype, spmajor, spminor)  = _wmi_query(
#             'OS',
#             'Version',
#             'ProductType',
#             'BuildType',
#             'ServicePackMajorVersion',
#             'ServicePackMinorVersion',
#         )
#         is_client = (int(product_type) == 1)
#         if spminor and spminor != '0':
#             csd = f'SP{spmajor}.{spminor}'
#         else:
#             csd = f'SP{spmajor}'
#         return version, csd, ptype, is_client
#     except OSError:
#         pass

#     # Fall back to a combination of sys.getwindowsversion and "ver"
#     try:
#         from sys import getwindowsversion
#     except ImportError:
#         return version, csd, ptype, True

#     winver = getwindowsversion()
#     is_client = (getattr(winver, 'product_type', 1) == 1)
#     try:
#         version = _syscmd_ver()[2]
#         major, minor, build = map(int, version.split('.'))
#     except ValueError:
#         major, minor, build = winver.platform_version or winver[:3]
#         version = '{0}.{1}.{2}'.format(major, minor, build)

#     # getwindowsversion() reflect the compatibility mode Python is
#     # running under, and so the service pack value is only going to be
#     # valid if the versions match.
#     if winver[:2] == (major, minor):
#         try:
#             csd = 'SP{}'.format(winver.service_pack_major)
#         except AttributeError:
#             if csd[:13] == 'Service Pack ':
#                 csd = 'SP' + csd[13:]

#     try:
#         try:
#             import winreg
#         except ImportError:
#             import _winreg as winreg
#     except ImportError:
#         pass
#     else:
#         try:
#             cvkey = r'SOFTWARE\Microsoft\Windows NT\CurrentVersion'
#             with winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, cvkey) as key:
#                 ptype = winreg.QueryValueEx(key, 'CurrentType')[0]
#         except OSError:
#             pass

#     return version, csd, ptype, is_client

# def win32_ver(release='', version='', csd='', ptype=''):
#     is_client = False

#     version, csd, ptype, is_client = _win32_ver(version, csd, ptype)

#     if version:
#         intversion = tuple(map(int, version.split('.')))
#         releases = _WIN32_CLIENT_RELEASES if is_client else _WIN32_SERVER_RELEASES
#         release = next((r for v, r in releases if v <= intversion), release)

#     return release, version, csd, ptype


# def _mac_ver_xml():
#     fn = '/System/Library/CoreServices/SystemVersion.plist'
#     if not os.path.exists(fn):
#         return None

#     try:
#         import plistlib
#     except ImportError:
#         return None

#     with open(fn, 'rb') as f:
#         pl = plistlib.load(f)
#     release = pl['ProductVersion']
#     versioninfo = ('', '', '')
#     machine = os.uname().machine
#     if machine in ('ppc', 'Power Macintosh'):
#         # Canonical name
#         machine = 'PowerPC'

#     return release, versioninfo, machine


# def mac_ver(release='', versioninfo=('', '', ''), machine=''):

#     """ Get macOS version information and return it as tuple (release,
#         versioninfo, machine) with versioninfo being a tuple (version,
#         dev_stage, non_release_version).

#         Entries which cannot be determined are set to the parameter values
#         which default to ''. All tuple entries are strings.
#     """

#     # First try reading the information from an XML file which should
#     # always be present
#     info = _mac_ver_xml()
#     if info is not None:
#         return info

#     # If that also doesn't work return the default values
#     return release, versioninfo, machine

# def _java_getprop(name, default):

#     from java.lang import System
#     try:
#         value = System.getProperty(name)
#         if value is None:
#             return default
#         return value
#     except AttributeError:
#         return default

# def java_ver(release='', vendor='', vminfo=('', '', ''), osinfo=('', '', '')):

#     """ Version interface for Jython.

#         Returns a tuple (release, vendor, vminfo, osinfo) with vminfo being
#         a tuple (vm_name, vm_release, vm_vendor) and osinfo being a
#         tuple (os_name, os_version, os_arch).

#         Values which cannot be determined are set to the defaults
#         given as parameters (which all default to '').

#     """
#     # Import the needed APIs
#     try:
#         import java.lang
#     except ImportError:
#         return release, vendor, vminfo, osinfo

#     vendor = _java_getprop('java.vendor', vendor)
#     release = _java_getprop('java.version', release)
#     vm_name, vm_release, vm_vendor = vminfo
#     vm_name = _java_getprop('java.vm.name', vm_name)
#     vm_vendor = _java_getprop('java.vm.vendor', vm_vendor)
#     vm_release = _java_getprop('java.vm.version', vm_release)
#     vminfo = vm_name, vm_release, vm_vendor
#     os_name, os_version, os_arch = osinfo
#     os_arch = _java_getprop('java.os.arch', os_arch)
#     os_name = _java_getprop('java.os.name', os_name)
#     os_version = _java_getprop('java.os.version', os_version)
#     osinfo = os_name, os_version, os_arch

#     return release, vendor, vminfo, osinfo

# ### System name aliasing

# def system_alias(system, release, version):

#     """ Returns (system, release, version) aliased to common
#         marketing names used for some systems.

#         It also does some reordering of the information in some cases
#         where it would otherwise cause confusion.

#     """
#     if system == 'SunOS':
#         # Sun's OS
#         if release < '5':
#             # These releases use the old name SunOS
#             return system, release, version
#         # Modify release (marketing release = SunOS release - 3)
#         l = release.split('.')
#         if l:
#             try:
#                 major = int(l[0])
#             except ValueError:
#                 pass
#             else:
#                 major = major - 3
#                 l[0] = str(major)
#                 release = '.'.join(l)
#         if release < '6':
#             system = 'Solaris'
#         else:
#             # XXX Whatever the new SunOS marketing name is...
#             system = 'Solaris'

#     elif system in ('win32', 'win16'):
#         # In case one of the other tricks
#         system = 'Windows'

#     # bpo-35516: Don't replace Darwin with macOS since input release and
#     # version arguments can be different than the currently running version.

#     return system, release, version

# ### Various internal helpers

# def _platform(*args):

#     """ Helper to format the platform string in a filename
#         compatible format e.g. "system-version-machine".
#     """
#     # Format the platform string
#     platform = '-'.join(x.strip() for x in filter(len, args))

#     # Cleanup some possible filename obstacles...
#     platform = platform.replace(' ', '_')
#     platform = platform.replace('/', '-')
#     platform = platform.replace('\\', '-')
#     platform = platform.replace(':', '-')
#     platform = platform.replace(';', '-')
#     platform = platform.replace('"', '-')
#     platform = platform.replace('(', '-')
#     platform = platform.replace(')', '-')

#     # No need to report 'unknown' information...
#     platform = platform.replace('unknown', '')

#     # Fold '--'s and remove trailing '-'
#     while True:
#         cleaned = platform.replace('--', '-')
#         if cleaned == platform:
#             break
#         platform = cleaned
#     while platform[-1] == '-':
#         platform = platform[:-1]

#     return platform

# def _node(default=''):

#     """ Helper to determine the node name of this machine.
#     """
#     try:
#         import socket
#     except ImportError:
#         # No sockets...
#         return default
#     try:
#         return socket.gethostname()
#     except OSError:
#         # Still not working...
#         return default

# def _follow_symlinks(filepath):

#     """ In case filepath is a symlink, follow it until a
#         real file is reached.
#     """
#     filepath = os.path.abspath(filepath)
#     while os.path.islink(filepath):
#         filepath = os.path.normpath(
#             os.path.join(os.path.dirname(filepath), os.readlink(filepath)))
#     return filepath


# def _syscmd_file(target, default=''):

#     """ Interface to the system's file command.

#         The function uses the -b option of the file command to have it
#         omit the filename in its output. Follow the symlinks. It returns
#         default in case the command should fail.

#     """
#     if sys.platform in ('dos', 'win32', 'win16'):
#         # XXX Others too ?
#         return default

#     try:
#         import subprocess
#     except ImportError:
#         return default
#     target = _follow_symlinks(target)
#     # "file" output is locale dependent: force the usage of the C locale
#     # to get deterministic behavior.
#     env = dict(os.environ, LC_ALL='C')
#     try:
#         # -b: do not prepend filenames to output lines (brief mode)
#         output = subprocess.check_output(['file', '-b', target],
#                                          stderr=subprocess.DEVNULL,
#                                          env=env)
#     except (OSError, subprocess.CalledProcessError):
#         return default
#     if not output:
#         return default
#     # With the C locale, the output should be mostly ASCII-compatible.
#     # Decode from Latin-1 to prevent Unicode decode error.
#     return output.decode('latin-1')

# ### Information about the used architecture

# # Default values for architecture; non-empty strings override the
# # defaults given as parameters
# _default_architecture = {
#     'win32': ('', 'WindowsPE'),
#     'win16': ('', 'Windows'),
#     'dos': ('', 'MSDOS'),
# }

# def architecture(executable=sys.executable, bits='', linkage=''):

#     """ Queries the given executable (defaults to the Python interpreter
#         binary) for various architecture information.

#         Returns a tuple (bits, linkage) which contains information about
#         the bit architecture and the linkage format used for the
#         executable. Both values are returned as strings.

#         Values that cannot be determined are returned as given by the
#         parameter presets. If bits is given as '', the sizeof(pointer)
#         (or sizeof(long) on Python version < 1.5.2) is used as
#         indicator for the supported pointer size.

#         The function relies on the system's "file" command to do the
#         actual work. This is available on most if not all Unix
#         platforms. On some non-Unix platforms where the "file" command
#         does not exist and the executable is set to the Python interpreter
#         binary defaults from _default_architecture are used.

#     """
#     # Use the sizeof(pointer) as default number of bits if nothing
#     # else is given as default.
#     if not bits:
#         import struct
#         size = struct.calcsize('P')
#         bits = str(size * 8) + 'bit'

#     # Get data from the 'file' system command
#     if executable:
#         fileout = _syscmd_file(executable, '')
#     else:
#         fileout = ''

#     if not fileout and \
#        executable == sys.executable:
#         # "file" command did not return anything; we'll try to provide
#         # some sensible defaults then...
#         if sys.platform in _default_architecture:
#             b, l = _default_architecture[sys.platform]
#             if b:
#                 bits = b
#             if l:
#                 linkage = l
#         return bits, linkage

#     if 'executable' not in fileout and 'shared object' not in fileout:
#         # Format not supported
#         return bits, linkage

#     # Bits
#     if '32-bit' in fileout:
#         bits = '32bit'
#     elif '64-bit' in fileout:
#         bits = '64bit'

#     # Linkage
#     if 'ELF' in fileout:
#         linkage = 'ELF'
#     elif 'PE' in fileout:
#         # E.g. Windows uses this format
#         if 'Windows' in fileout:
#             linkage = 'WindowsPE'
#         else:
#             linkage = 'PE'
#     elif 'COFF' in fileout:
#         linkage = 'COFF'
#     elif 'MS-DOS' in fileout:
#         linkage = 'MSDOS'
#     else:
#         # XXX the A.OUT format also falls under this class...
#         pass

#     return bits, linkage


# def _get_machine_win32():
#     # Try to use the PROCESSOR_* environment variables
#     # available on Win XP and later; see
#     # http://support.microsoft.com/kb/888731 and
#     # http://www.geocities.com/rick_lively/MANUALS/ENV/MSWIN/PROCESSI.HTM

#     # WOW64 processes mask the native architecture
#     try:
#         [arch, *_] = _wmi_query('CPU', 'Architecture')
#     except OSError:
#         pass
#     else:
#         try:
#             arch = ['x86', 'MIPS', 'Alpha', 'PowerPC', None,
#                     'ARM', 'ia64', None, None,
#                     'AMD64', None, None, 'ARM64',
#             ][int(arch)]
#         except (ValueError, IndexError):
#             pass
#         else:
#             if arch:
#                 return arch
#     return (
#         os.environ.get('PROCESSOR_ARCHITEW6432', '') or
#         os.environ.get('PROCESSOR_ARCHITECTURE', '')
#     )


# class _Processor:
#     @classmethod
#     def get(cls):
#         func = getattr(cls, f'get_{sys.platform}', cls.from_subprocess)
#         return func() or ''

#     def get_win32():
#         try:
#             manufacturer, caption = _wmi_query('CPU', 'Manufacturer', 'Caption')
#         except OSError:
#             return os.environ.get('PROCESSOR_IDENTIFIER', _get_machine_win32())
#         else:
#             return f'{caption}, {manufacturer}'

#     def get_OpenVMS():
#         try:
#             import vms_lib
#         except ImportError:
#             pass
#         else:
#             csid, cpu_number = vms_lib.getsyi('SYI$_CPU', 0)
#             return 'Alpha' if cpu_number >= 128 else 'VAX'

#     def from_subprocess():
#         """
#         Fall back to `uname -p`
#         """
#         try:
#             import subprocess
#         except ImportError:
#             return None
#         try:
#             return subprocess.check_output(
#                 ['uname', '-p'],
#                 stderr=subprocess.DEVNULL,
#                 text=True,
#                 encoding="utf8",
#             ).strip()
#         except (OSError, subprocess.CalledProcessError):
#             pass


# def _unknown_as_blank(val):
#     return '' if val == 'unknown' else val


# ### Portable uname() interface

# class uname_result(
#     namedtuple(
#         "uname_result_base",
#         "system node release version machine")
#         ):
#     """
#     A uname_result that's largely compatible with a
#     simple namedtuple except that 'processor' is
#     resolved late and cached to avoid calling "uname"
#     except when needed.
#     """

#     _fields = ('system', 'node', 'release', 'version', 'machine', 'processor')

#     @cached_property
#     def processor(self):
#         return _unknown_as_blank(_Processor.get())

#     def __iter__(self):
#         return itertools.chain(
#             super().__iter__(),
#             (self.processor,)
#         )

#     @classmethod
#     def _make(cls, iterable):
#         # override factory to affect length check
#         num_fields = len(cls._fields) - 1
#         result = cls.__new__(cls, *iterable)
#         if len(result) != num_fields + 1:
#             msg = f'Expected {num_fields} arguments, got {len(result)}'
#             raise TypeError(msg)
#         return result

#     def __getitem__(self, key):
#         return tuple(self)[key]

#     def __len__(self):
#         return len(tuple(iter(self)))

#     def __reduce__(self):
#         return uname_result, tuple(self)[:len(self._fields) - 1]


# _uname_cache = None


# def uname():

#     """ Fairly portable uname interface. Returns a tuple
#         of strings (system, node, release, version, machine, processor)
#         identifying the underlying platform.

#         Note that unlike the os.uname function this also returns
#         possible processor information as an additional tuple entry.

#         Entries which cannot be determined are set to ''.

#     """
#     global _uname_cache

#     if _uname_cache is not None:
#         return _uname_cache

#     # Get some infos from the builtin os.uname API...
#     try:
#         system, node, release, version, machine = infos = os.uname()
#     except AttributeError:
#         system = sys.platform
#         node = _node()
#         release = version = machine = ''
#         infos = ()

#     if not any(infos):
#         # uname is not available

#         # Try win32_ver() on win32 platforms
#         if system == 'win32':
#             release, version, csd, ptype = win32_ver()
#             machine = machine or _get_machine_win32()

#         # Try the 'ver' system command available on some
#         # platforms
#         if not (release and version):
#             system, release, version = _syscmd_ver(system)
#             # Normalize system to what win32_ver() normally returns
#             # (_syscmd_ver() tends to return the vendor name as well)
#             if system == 'Microsoft Windows':
#                 system = 'Windows'
#             elif system == 'Microsoft' and release == 'Windows':
#                 # Under Windows Vista and Windows Server 2008,
#                 # Microsoft changed the output of the ver command. The
#                 # release is no longer printed.  This causes the
#                 # system and release to be misidentified.
#                 system = 'Windows'
#                 if '6.0' == version[:3]:
#                     release = 'Vista'
#                 else:
#                     release = ''

#         # In case we still don't know anything useful, we'll try to
#         # help ourselves
#         if system in ('win32', 'win16'):
#             if not version:
#                 if system == 'win32':
#                     version = '32bit'
#                 else:
#                     version = '16bit'
#             system = 'Windows'

#         elif system[:4] == 'java':
#             release, vendor, vminfo, osinfo = java_ver()
#             system = 'Java'
#             version = ', '.join(vminfo)
#             if not version:
#                 version = vendor

#     # System specific extensions
#     if system == 'OpenVMS':
#         # OpenVMS seems to have release and version mixed up
#         if not release or release == '0':
#             release = version
#             version = ''

#     #  normalize name
#     if system == 'Microsoft' and release == 'Windows':
#         system = 'Windows'
#         release = 'Vista'

#     vals = system, node, release, version, machine
#     # Replace 'unknown' values with the more portable ''
#     _uname_cache = uname_result(*map(_unknown_as_blank, vals))
#     return _uname_cache

# ### Direct interfaces to some of the uname() return values

# def system():

#     """ Returns the system/OS name, e.g. 'Linux', 'Windows' or 'Java'.

#         An empty string is returned if the value cannot be determined.

#     """
#     return uname().system

# def node():

#     """ Returns the computer's network name (which may not be fully
#         qualified)

#         An empty string is returned if the value cannot be determined.

#     """
#     return uname().node

# def release():

#     """ Returns the system's release, e.g. '2.2.0' or 'NT'

#         An empty string is returned if the value cannot be determined.

#     """
#     return uname().release

# def version():

#     """ Returns the system's release version, e.g. '#3 on degas'

#         An empty string is returned if the value cannot be determined.

#     """
#     return uname().version

# def machine():

#     """ Returns the machine type, e.g. 'i386'

#         An empty string is returned if the value cannot be determined.

#     """
#     return uname().machine

# def processor():

#     """ Returns the (true) processor name, e.g. 'amdk6'

#         An empty string is returned if the value cannot be
#         determined. Note that many platforms do not provide this
#         information or simply return the same value as for machine(),
#         e.g.  NetBSD does this.

#     """
#     return uname().processor

# ### Various APIs for extracting information from sys.version

# _sys_version_cache = {}

# def _sys_version(sys_version=None):

#     """ Returns a parsed version of Python's sys.version as tuple
#         (name, version, branch, revision, buildno, builddate, compiler)
#         referring to the Python implementation name, version, branch,
#         revision, build number, build date/time as string and the compiler
#         identification string.

#         Note that unlike the Python sys.version, the returned value
#         for the Python version will always include the patchlevel (it
#         defaults to '.0').

#         The function returns empty strings for tuple entries that
#         cannot be determined.

#         sys_version may be given to parse an alternative version
#         string, e.g. if the version was read from a different Python
#         interpreter.

#     """
#     # Get the Python version
#     if sys_version is None:
#         sys_version = sys.version

#     # Try the cache first
#     result = _sys_version_cache.get(sys_version, None)
#     if result is not None:
#         return result

#     sys_version_parser = re.compile(
#         r'([\w.+]+)\s*'  # "version<space>"
#         r'\(#?([^,]+)'  # "(#buildno"
#         r'(?:,\s*([\w ]*)'  # ", builddate"
#         r'(?:,\s*([\w :]*))?)?\)\s*'  # ", buildtime)<space>"
#         r'\[([^\]]+)\]?', re.ASCII)  # "[compiler]"

#     if sys.platform.startswith('java'):
#         # Jython
#         name = 'Jython'
#         match = sys_version_parser.match(sys_version)
#         if match is None:
#             raise ValueError(
#                 'failed to parse Jython sys.version: %s' %
#                 repr(sys_version))
#         version, buildno, builddate, buildtime, _ = match.groups()
#         if builddate is None:
#             builddate = ''
#         compiler = sys.platform

#     elif "PyPy" in sys_version:
#         # PyPy
#         pypy_sys_version_parser = re.compile(
#             r'([\w.+]+)\s*'
#             r'\(#?([^,]+),\s*([\w ]+),\s*([\w :]+)\)\s*'
#             r'\[PyPy [^\]]+\]?')

#         name = "PyPy"
#         match = pypy_sys_version_parser.match(sys_version)
#         if match is None:
#             raise ValueError("failed to parse PyPy sys.version: %s" %
#                              repr(sys_version))
#         version, buildno, builddate, buildtime = match.groups()
#         compiler = ""

#     else:
#         # CPython
#         match = sys_version_parser.match(sys_version)
#         if match is None:
#             raise ValueError(
#                 'failed to parse CPython sys.version: %s' %
#                 repr(sys_version))
#         version, buildno, builddate, buildtime, compiler = \
#               match.groups()
#         name = 'CPython'
#         if builddate is None:
#             builddate = ''
#         elif buildtime:
#             builddate = builddate + ' ' + buildtime

#     if hasattr(sys, '_git'):
#         _, branch, revision = sys._git
#     elif hasattr(sys, '_mercurial'):
#         _, branch, revision = sys._mercurial
#     else:
#         branch = ''
#         revision = ''

#     # Add the patchlevel version if missing
#     l = version.split('.')
#     if len(l) == 2:
#         l.append('0')
#         version = '.'.join(l)

#     # Build and cache the result
#     result = (name, version, branch, revision, buildno, builddate, compiler)
#     _sys_version_cache[sys_version] = result
#     return result

# def python_implementation():

#     """ Returns a string identifying the Python implementation.

#         Currently, the following implementations are identified:
#           'CPython' (C implementation of Python),
#           'Jython' (Java implementation of Python),
#           'PyPy' (Python implementation of Python).

#     """
#     return _sys_version()[0]

# def python_version():

#     """ Returns the Python version as string 'major.minor.patchlevel'

#         Note that unlike the Python sys.version, the returned value
#         will always include the patchlevel (it defaults to 0).

#     """
#     return _sys_version()[1]

# def python_version_tuple():

#     """ Returns the Python version as tuple (major, minor, patchlevel)
#         of strings.

#         Note that unlike the Python sys.version, the returned value
#         will always include the patchlevel (it defaults to 0).

#     """
#     return tuple(_sys_version()[1].split('.'))

# def python_branch():

#     """ Returns a string identifying the Python implementation
#         branch.

#         For CPython this is the SCM branch from which the
#         Python binary was built.

#         If not available, an empty string is returned.

#     """

#     return _sys_version()[2]

# def python_revision():

#     """ Returns a string identifying the Python implementation
#         revision.

#         For CPython this is the SCM revision from which the
#         Python binary was built.

#         If not available, an empty string is returned.

#     """
#     return _sys_version()[3]

# def python_build():

#     """ Returns a tuple (buildno, builddate) stating the Python
#         build number and date as strings.

#     """
#     return _sys_version()[4:6]

# def python_compiler():

#     """ Returns a string identifying the compiler used for compiling
#         Python.

#     """
#     return _sys_version()[6]

# ### The Opus Magnum of platform strings :-)

# _platform_cache = {}

# def platform(aliased=False, terse=False):

#     """ Returns a single string identifying the underlying platform
#         with as much useful information as possible (but no more :).

#         The output is intended to be human readable rather than
#         machine parseable. It may look different on different
#         platforms and this is intended.

#         If "aliased" is true, the function will use aliases for
#         various platforms that report system names which differ from
#         their common names, e.g. SunOS will be reported as
#         Solaris. The system_alias() function is used to implement
#         this.

#         Setting terse to true causes the function to return only the
#         absolute minimum information needed to identify the platform.

#     """
#     result = _platform_cache.get((aliased, terse), None)
#     if result is not None:
#         return result

#     # Get uname information and then apply platform specific cosmetics
#     # to it...
#     system, node, release, version, machine, processor = uname()
#     if machine == processor:
#         processor = ''
#     if aliased:
#         system, release, version = system_alias(system, release, version)

#     if system == 'Darwin':
#         # macOS (darwin kernel)
#         macos_release = mac_ver()[0]
#         if macos_release:
#             system = 'macOS'
#             release = macos_release

#     if system == 'Windows':
#         # MS platforms
#         rel, vers, csd, ptype = win32_ver(version)
#         if terse:
#             platform = _platform(system, release)
#         else:
#             platform = _platform(system, release, version, csd)

#     elif system == 'Linux':
#         # check for libc vs. glibc
#         libcname, libcversion = libc_ver()
#         platform = _platform(system, release, machine, processor,
#                              'with',
#                              libcname+libcversion)
#     elif system == 'Java':
#         # Java platforms
#         r, v, vminfo, (os_name, os_version, os_arch) = java_ver()
#         if terse or not os_name:
#             platform = _platform(system, release, version)
#         else:
#             platform = _platform(system, release, version,
#                                  'on',
#                                  os_name, os_version, os_arch)

#     else:
#         # Generic handler
#         if terse:
#             platform = _platform(system, release)
#         else:
#             bits, linkage = architecture(sys.executable)
#             platform = _platform(system, release, machine,
#                                  processor, bits, linkage)

#     _platform_cache[(aliased, terse)] = platform
#     return platform

# ### freedesktop.org os-release standard
# # https://www.freedesktop.org/software/systemd/man/os-release.html

# # /etc takes precedence over /usr/lib
# _os_release_candidates = ("/etc/os-release", "/usr/lib/os-release")
# _os_release_cache = None


# def _parse_os_release(lines):
#     # These fields are mandatory fields with well-known defaults
#     # in practice all Linux distributions override NAME, ID, and PRETTY_NAME.
#     info = {
#         "NAME": "Linux",
#         "ID": "linux",
#         "PRETTY_NAME": "Linux",
#     }

#     # NAME=value with optional quotes (' or "). The regular expression is less
#     # strict than shell lexer, but that's ok.
#     os_release_line = re.compile(
#         "^(?P<name>[a-zA-Z0-9_]+)=(?P<quote>[\"\']?)(?P<value>.*)(?P=quote)$"
#     )
#     # unescape five special characters mentioned in the standard
#     os_release_unescape = re.compile(r"\\([\\\$\"\'`])")

#     for line in lines:
#         mo = os_release_line.match(line)
#         if mo is not None:
#             info[mo.group('name')] = os_release_unescape.sub(
#                 r"\1", mo.group('value')
#             )

#     return info


# def freedesktop_os_release():
#     """Return operation system identification from freedesktop.org os-release
#     """
#     global _os_release_cache

#     if _os_release_cache is None:
#         errno = None
#         for candidate in _os_release_candidates:
#             try:
#                 with open(candidate, encoding="utf-8") as f:
#                     _os_release_cache = _parse_os_release(f)
#                 break
#             except OSError as e:
#                 errno = e.errno
#         else:
#             raise OSError(
#                 errno,
#                 f"Unable to read files {', '.join(_os_release_candidates)}"
#             )

#     return _os_release_cache.copy()


# ### Command line interface

# if __name__ == '__main__':
#     # Default is to print the aliased verbose platform string
#     terse = ('terse' in sys.argv or '--terse' in sys.argv)
#     aliased = (not 'nonaliased' in sys.argv and not '--nonaliased' in sys.argv)
#     print(platform(aliased, terse))
#     sys.exit(0)
