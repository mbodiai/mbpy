<details><summary><h3>module importlib</h3></summary>
  <details><summary><h4>module importlib.abc</h4></summary>
    <details><summary><h5>class ExecutionLoader(InspectLoader)</h5></summary>
    <details><summary><b>def create_module(self, spec)</b></summary>
    <p>Return a module to initialize and into which to load.

This method should raise ImportError if anything prevents it
from creating a new module.  It may return None to indicate
that the spec should create the new module.</p>
    </details>
    <details><summary><b>def exec_module(self, module)</b></summary>
    <p>Execute the module.</p>
    </details>
    <details><summary><b>def get_code(self, fullname)</b></summary>
    <p>Method to return the code object for fullname.

Should return None if not applicable (e.g. built-in module).
Raise ImportError if the module cannot be found.</p>
    </details>
    <details><summary><b>def get_filename(self, fullname)</b></summary>
    <p>Abstract method which should return the value that __file__ is to be
set to.

Raises ImportError if the module cannot be found.</p>
    </details>
    <details><summary><b>def get_source(self, fullname)</b></summary>
    <p>Abstract method which should return the source code for the
module.  The fullname is a str.  Returns a str.

Raises ImportError if the module cannot be found.</p>
    </details>
    <details><summary><b>def is_package(self, fullname)</b></summary>
    <p>Optional method which when implemented should return whether the
module is a package.  The fullname is a str.  Returns a bool.

Raises ImportError if the module cannot be found.</p>
    </details>
    <details><summary><b>def load_module(self, fullname)</b></summary>
    <p>This method is deprecated.</p>
    </details>
    <details><summary><b>def module_repr(self, module)</b></summary>
    <p>Return a module's repr.

Used by the module type when the method does not raise
NotImplementedError.

This method is deprecated.</p>
    </details>
    <details><summary><b>def source_to_code(data, path='<string>')</b></summary>
    <p>Compile 'data' into a code object.

The 'data' argument can be anything that compile() can handle. The'path'
argument should be where the data was retrieved (when applicable).</p>
    </details>
    </details>
    <details><summary><h5>class FileLoader(FileLoader, ResourceLoader, ExecutionLoader)</h5></summary>
    <details><summary><b>def __eq__(self, other)</b></summary>
    <p>Return self==value.</p>
    </details>
    <details><summary><b>def __hash__(self)</b></summary>
    <p>Return hash(self).</p>
    </details>
    <details><summary><b>def __init__(self, fullname, path)</b></summary>
    <p>Cache the module name and the path to the file found by the
finder.</p>
    </details>
    <details><summary><b>def create_module(self, spec)</b></summary>
    <p>Return a module to initialize and into which to load.

This method should raise ImportError if anything prevents it
from creating a new module.  It may return None to indicate
that the spec should create the new module.</p>
    </details>
    <details><summary><b>def exec_module(self, module)</b></summary>
    <p>Execute the module.</p>
    </details>
    <details><summary><b>def get_code(self, fullname)</b></summary>
    <p>Method to return the code object for fullname.

Should return None if not applicable (e.g. built-in module).
Raise ImportError if the module cannot be found.</p>
    </details>
    <details><summary><b>def get_data(self, path)</b></summary>
    <p>Return the data from path as raw bytes.</p>
    </details>
    <details><summary><b>def get_filename(self, name=None, *args, **kwargs)</b></summary>
    <p>Return the path to the source file as found by the finder.</p>
    </details>
    <details><summary><b>def get_resource_reader(self, name=None, *args, **kwargs)</b></summary>
    </details>
    <details><summary><b>def get_source(self, fullname)</b></summary>
    <p>Abstract method which should return the source code for the
module.  The fullname is a str.  Returns a str.

Raises ImportError if the module cannot be found.</p>
    </details>
    <details><summary><b>def is_package(self, fullname)</b></summary>
    <p>Optional method which when implemented should return whether the
module is a package.  The fullname is a str.  Returns a bool.

Raises ImportError if the module cannot be found.</p>
    </details>
    <details><summary><b>def load_module(self, name=None, *args, **kwargs)</b></summary>
    <p>Load a module from a file.

This method is deprecated.  Use exec_module() instead.</p>
    </details>
    <details><summary><b>def module_repr(self, module)</b></summary>
    <p>Return a module's repr.

Used by the module type when the method does not raise
NotImplementedError.

This method is deprecated.</p>
    </details>
    <details><summary><b>def source_to_code(data, path='<string>')</b></summary>
    <p>Compile 'data' into a code object.

The 'data' argument can be anything that compile() can handle. The'path'
argument should be where the data was retrieved (when applicable).</p>
    </details>
    </details>
    <details><summary><h5>class Finder(object)</h5></summary>
    <details><summary><b>def __init__(self)</b></summary>
    <p>Initialize self.  See help(type(self)) for accurate signature.</p>
    </details>
    <details><summary><b>def find_module(self, fullname, path=None)</b></summary>
    <p>An abstract method that should find a module.
The fullname is a str and the optional path is a str or None.
Returns a Loader object or None.</p>
    </details>
    </details>
    <details><summary><h5>class InspectLoader(Loader)</h5></summary>
    <details><summary><b>def create_module(self, spec)</b></summary>
    <p>Return a module to initialize and into which to load.

This method should raise ImportError if anything prevents it
from creating a new module.  It may return None to indicate
that the spec should create the new module.</p>
    </details>
    <details><summary><b>def exec_module(self, module)</b></summary>
    <p>Execute the module.</p>
    </details>
    <details><summary><b>def get_code(self, fullname)</b></summary>
    <p>Method which returns the code object for the module.

The fullname is a str.  Returns a types.CodeType if possible, else
returns None if a code object does not make sense
(e.g. built-in module). Raises ImportError if the module cannot be
found.</p>
    </details>
    <details><summary><b>def get_source(self, fullname)</b></summary>
    <p>Abstract method which should return the source code for the
module.  The fullname is a str.  Returns a str.

Raises ImportError if the module cannot be found.</p>
    </details>
    <details><summary><b>def is_package(self, fullname)</b></summary>
    <p>Optional method which when implemented should return whether the
module is a package.  The fullname is a str.  Returns a bool.

Raises ImportError if the module cannot be found.</p>
    </details>
    <details><summary><b>def load_module(self, fullname)</b></summary>
    <p>This method is deprecated.</p>
    </details>
    <details><summary><b>def module_repr(self, module)</b></summary>
    <p>Return a module's repr.

Used by the module type when the method does not raise
NotImplementedError.

This method is deprecated.</p>
    </details>
    <details><summary><b>def source_to_code(data, path='<string>')</b></summary>
    <p>Compile 'data' into a code object.

The 'data' argument can be anything that compile() can handle. The'path'
argument should be where the data was retrieved (when applicable).</p>
    </details>
    </details>
    <details><summary><h5>class Loader(object)</h5></summary>
    <details><summary><b>def create_module(self, spec)</b></summary>
    <p>Return a module to initialize and into which to load.

This method should raise ImportError if anything prevents it
from creating a new module.  It may return None to indicate
that the spec should create the new module.</p>
    </details>
    <details><summary><b>def load_module(self, fullname)</b></summary>
    <p>Return the loaded module.

The module must be added to sys.modules and have import-related
attributes set properly.  The fullname is a str.

ImportError is raised on failure.

This method is deprecated in favor of loader.exec_module(). If
exec_module() exists then it is used to provide a backwards-compatible
functionality for this method.</p>
    </details>
    <details><summary><b>def module_repr(self, module)</b></summary>
    <p>Return a module's repr.

Used by the module type when the method does not raise
NotImplementedError.

This method is deprecated.</p>
    </details>
    </details>
    <details><summary><h5>class MetaPathFinder(object)</h5></summary>
    <details><summary><b>def find_module(self, fullname, path)</b></summary>
    <p>Return a loader for the module.

If no module is found, return None.  The fullname is a str and
the path is a list of strings or None.

This method is deprecated since Python 3.4 in favor of
finder.find_spec(). If find_spec() exists then backwards-compatible
functionality is provided for this method.</p>
    </details>
    <details><summary><b>def invalidate_caches(self)</b></summary>
    <p>An optional method for clearing the finder's cache, if any.
This method is used by importlib.invalidate_caches().</p>
    </details>
    </details>
    <details><summary><h5>class PathEntryFinder(object)</h5></summary>
    <details><summary><b>def find_loader(self, fullname)</b></summary>
    <p>Return (loader, namespace portion) for the path entry.

The fullname is a str.  The namespace portion is a sequence of
path entries contributing to part of a namespace package. The
sequence may be empty.  If loader is not None, the portion will
be ignored.

The portion will be discarded if another path entry finder
locates the module as a normal module or package.

This method is deprecated since Python 3.4 in favor of
finder.find_spec(). If find_spec() is provided than backwards-compatible
functionality is provided.</p>
    </details>
    <details><summary><b>def _find_module_shim(self, fullname)</b></summary>
    <p>Try to find a loader for the specified module by delegating to
self.find_loader().

This method is deprecated in favor of finder.find_spec().</p>
    </details>
    <details><summary><b>def invalidate_caches(self)</b></summary>
    <p>An optional method for clearing the finder's cache, if any.
This method is used by PathFinder.invalidate_caches().</p>
    </details>
    </details>
    <details><summary><h5>class ResourceLoader(Loader)</h5></summary>
    <details><summary><b>def create_module(self, spec)</b></summary>
    <p>Return a module to initialize and into which to load.

This method should raise ImportError if anything prevents it
from creating a new module.  It may return None to indicate
that the spec should create the new module.</p>
    </details>
    <details><summary><b>def get_data(self, path)</b></summary>
    <p>Abstract method which when implemented should return the bytes for
the specified path.  The path must be a str.</p>
    </details>
    <details><summary><b>def load_module(self, fullname)</b></summary>
    <p>Return the loaded module.

The module must be added to sys.modules and have import-related
attributes set properly.  The fullname is a str.

ImportError is raised on failure.

This method is deprecated in favor of loader.exec_module(). If
exec_module() exists then it is used to provide a backwards-compatible
functionality for this method.</p>
    </details>
    <details><summary><b>def module_repr(self, module)</b></summary>
    <p>Return a module's repr.

Used by the module type when the method does not raise
NotImplementedError.

This method is deprecated.</p>
    </details>
    </details>
    <details><summary><h5>class ResourceReader(object)</h5></summary>
    <details><summary><b>def contents(self) -> Iterable[str]</b></summary>
    <p>Return an iterable of entries in `package`.</p>
    </details>
    <details><summary><b>def is_resource(self, path: str) -> bool</b></summary>
    <p>Return True if the named 'path' is a resource.

Files are resources, directories are not.</p>
    </details>
    <details><summary><b>def open_resource(self, resource: str) -> <class 'BinaryIO'></b></summary>
    <p>Return an opened, file-like object for binary reading.

The 'resource' argument is expected to represent only a file name.
If the resource cannot be found, FileNotFoundError is raised.</p>
    </details>
    <details><summary><b>def resource_path(self, resource: str) -> str</b></summary>
    <p>Return the file system path to the specified resource.

The 'resource' argument is expected to represent only a file name.
If the resource does not exist on the file system, raise
FileNotFoundError.</p>
    </details>
    </details>
    <details><summary><h5>class SourceLoader(SourceLoader, ResourceLoader, ExecutionLoader)</h5></summary>
    <details><summary><b>def _cache_bytecode(self, source_path, cache_path, data)</b></summary>
    <p>Optional method which writes data (bytes) to a file path (a str).

Implementing this method allows for the writing of bytecode files.

The source path is needed in order to correctly transfer permissions</p>
    </details>
    <details><summary><b>def create_module(self, spec)</b></summary>
    <p>Use default semantics for module creation.</p>
    </details>
    <details><summary><b>def exec_module(self, module)</b></summary>
    <p>Execute the module.</p>
    </details>
    <details><summary><b>def get_code(self, fullname)</b></summary>
    <p>Concrete implementation of InspectLoader.get_code.

Reading of bytecode requires path_stats to be implemented. To write
bytecode, set_data must also be implemented.</p>
    </details>
    <details><summary><b>def get_data(self, path)</b></summary>
    <p>Abstract method which when implemented should return the bytes for
the specified path.  The path must be a str.</p>
    </details>
    <details><summary><b>def get_filename(self, fullname)</b></summary>
    <p>Abstract method which should return the value that __file__ is to be
set to.

Raises ImportError if the module cannot be found.</p>
    </details>
    <details><summary><b>def get_source(self, fullname)</b></summary>
    <p>Concrete implementation of InspectLoader.get_source.</p>
    </details>
    <details><summary><b>def is_package(self, fullname)</b></summary>
    <p>Concrete implementation of InspectLoader.is_package by checking if
the path returned by get_filename has a filename of '__init__.py'.</p>
    </details>
    <details><summary><b>def load_module(self, fullname)</b></summary>
    <p>This method is deprecated.</p>
    </details>
    <details><summary><b>def module_repr(self, module)</b></summary>
    <p>Return a module's repr.

Used by the module type when the method does not raise
NotImplementedError.

This method is deprecated.</p>
    </details>
    <details><summary><b>def path_mtime(self, path)</b></summary>
    <p>Return the (int) modification time for the path (str).</p>
    </details>
    <details><summary><b>def path_stats(self, path)</b></summary>
    <p>Return a metadata dict for the source pointed to by the path (str).
Possible keys:
- 'mtime' (mandatory) is the numeric timestamp of last source
  code modification;
- 'size' (optional) is the size in bytes of the source code.</p>
    </details>
    <details><summary><b>def set_data(self, path, data)</b></summary>
    <p>Write the bytes to the path (if possible).

Accepts a str path and data as bytes.

Any needed intermediary directories are to be created. If for some
reason the file cannot be written because of permissions, fail
silently.</p>
    </details>
    <details><summary><b>def source_to_code(self, data, path, *, _optimize=-1)</b></summary>
    <p>Return the code object compiled from source.

The 'data' argument can be any object type that compile() supports.</p>
    </details>
    </details>
    <details><summary><h5>class Traversable(Protocol)</h5></summary>
    <details><summary><b>def __class_getitem__(params)</b></summary>
    <p>Parameterizes a generic class.

At least, parameterizing a generic class is the *main* thing this method
does. For example, for some generic class `Foo`, this is called when we
do `Foo[int]` - there, with `cls=Foo` and `params=int`.

However, note that this method is also called when defining generic
classes in the first place with `class Foo(Generic[T]): ...`.</p>
    </details>
    <details><summary><b>def _no_init_or_replace_init(self, *args, **kwargs)</b></summary>
    </details>
    <details><summary><b>def __init_subclass__(*args, **kwargs)</b></summary>
    <p>This method is called when a class is subclassed.

The default implementation does nothing. It may be
overridden to extend subclasses.</p>
    </details>
    <details><summary><b>def _proto_hook(other)</b></summary>
    </details>
    <details><summary><b>def __truediv__(self, child: Union[str, os.PathLike[str]]) -> 'Traversable'</b></summary>
    <p>Return Traversable child in self</p>
    </details>
    <details><summary><b>def is_dir(self) -> bool</b></summary>
    <p>Return True if self is a directory</p>
    </details>
    <details><summary><b>def is_file(self) -> bool</b></summary>
    <p>Return True if self is a file</p>
    </details>
    <details><summary><b>def iterdir(self) -> Iterator[ForwardRef('Traversable')]</b></summary>
    <p>Yield Traversable objects in self</p>
    </details>
    <details><summary><b>def joinpath(self, *descendants: Union[str, os.PathLike[str]]) -> 'Traversable'</b></summary>
    <p>Return Traversable resolved with any descendants applied.

Each descendant should be a path segment relative to self
and each may contain multiple levels separated by
``posixpath.sep`` (``/``).</p>
    </details>
    <li><b>name:</b> <abc.abstractproperty object at 0x1011f54e0></li>
    <details><summary><b>def open(self, mode='r', *args, **kwargs)</b></summary>
    <p>mode may be 'r' or 'rb' to open as text or binary. Return a handle
suitable for reading (same as pathlib.Path.open).

When opening as text, accepts encoding parameters such as those
accepted by io.TextIOWrapper.</p>
    </details>
    <details><summary><b>def read_bytes(self) -> bytes</b></summary>
    <p>Read contents of self as bytes</p>
    </details>
    <details><summary><b>def read_text(self, encoding: Optional[str] = None) -> str</b></summary>
    <p>Read contents of self as text</p>
    </details>
    </details>
    <details><summary><h5>class TraversableResources(ResourceReader)</h5></summary>
    <details><summary><b>def contents(self) -> Iterator[str]</b></summary>
    <p>Return an iterable of entries in `package`.</p>
    </details>
    <details><summary><b>def files(self) -> 'Traversable'</b></summary>
    <p>Return a Traversable object for the loaded package.</p>
    </details>
    <details><summary><b>def is_resource(self, path: Union[str, os.PathLike[str]]) -> bool</b></summary>
    <p>Return True if the named 'path' is a resource.

Files are resources, directories are not.</p>
    </details>
    <details><summary><b>def open_resource(self, resource: Union[str, os.PathLike[str]]) -> _io.BufferedReader</b></summary>
    <p>Return an opened, file-like object for binary reading.

The 'resource' argument is expected to represent only a file name.
If the resource cannot be found, FileNotFoundError is raised.</p>
    </details>
    <details><summary><b>def resource_path(self, resource: Any) -> NoReturn</b></summary>
    <p>Return the file system path to the specified resource.

The 'resource' argument is expected to represent only a file name.
If the resource does not exist on the file system, raise
FileNotFoundError.</p>
    </details>
    </details>
    <details><summary><h5>module abc</h5></summary>
    </details>
    <details><summary><h5>module importlib.machinery</h5></summary>
    </details>
    <details><summary><h5>module warnings</h5></summary>
    </details>
  </details>
  <details><summary><b>def find_loader(name, path=None)</b></summary>
  <p>Return the loader for the specified module.

This is a backward-compatible wrapper around find_spec().

This function is deprecated in favor of importlib.util.find_spec().</p>
  </details>
  <details><summary><b>def import_module(name, package=None)</b></summary>
  <p>Import a module.

The 'package' argument is required when performing a relative import. It
specifies the package to use as the anchor point from which to resolve the
relative import to an absolute import.</p>
  </details>
  <details><summary><b>def invalidate_caches()</b></summary>
  <p>Call the invalidate_caches() method on all meta path finders stored in
sys.meta_path (where implemented).</p>
  </details>
  <details><summary><h4>module importlib.machinery</h4></summary>
  <!-- Error processing item: 'list' object has no attribute '__name__' -->
  <details><summary><h4>module importlib.metadata</h4></summary>
    <details><summary><h5>class Deprecated(object)</h5></summary>
    <details><summary><b>def __contains__(self, *args)</b></summary>
    </details>
    <details><summary><b>def __getitem__(self, name)</b></summary>
    </details>
    <details><summary><b>def __iter__(self)</b></summary>
    </details>
    <details><summary><b>def get(self, name, default=None)</b></summary>
    </details>
    <details><summary><b>def keys(self)</b></summary>
    </details>
    <details><summary><b>def values(self)</b></summary>
    </details>
    </details>
    <details><summary><h5>class DeprecatedList(list)</h5></summary>
    <details><summary><b>def __add__(self, other)</b></summary>
    <p>Return self+value.</p>
    </details>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <details><summary><b>def __eq__(self, other)</b></summary>
    <p>Return self==value.</p>
    </details>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <details><summary><b>def _wrap_deprecated_method(method_name: str)</b></summary>
    </details>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <li><b>clear:</b> <method 'clear' of 'list' objects></li>
    <li><b>copy:</b> <method 'copy' of 'list' objects></li>
    <li><b>count:</b> <method 'count' of 'list' objects></li>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <li><b>index:</b> <method 'index' of 'list' objects></li>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    </details>
    <details><summary><h5>class DeprecatedTuple(object)</h5></summary>
    <details><summary><b>def __getitem__(self, item)</b></summary>
    </details>
    </details>
    <details><summary><h5>class Distribution(object)</h5></summary>
    <details><summary><b>def _convert_egg_info_reqs_to_simple_reqs(sections)</b></summary>
    <p>Historically, setuptools would solicit and store 'extra'
requirements, including those with environment markers,
in separate sections. More modern tools expect each
dependency to be defined separately, with any relevant
extras and environment markers attached directly to that
requirement. This method converts the former to the
latter. See _test_deps_from_requires_text for an example.</p>
    </details>
    <details><summary><b>def _deps_from_requires_text(source)</b></summary>
    </details>
    <details><summary><b>def _discover_resolvers()</b></summary>
    <p>Search the meta_path for resolvers.</p>
    </details>
    <details><summary><b>def _read_dist_info_reqs(self)</b></summary>
    </details>
    <details><summary><b>def _read_egg_info_reqs(self)</b></summary>
    </details>
    <details><summary><b>def _read_files_distinfo(self)</b></summary>
    <p>Read the lines of RECORD</p>
    </details>
    <details><summary><b>def _read_files_egginfo(self)</b></summary>
    <p>SOURCES.txt might contain literal commas, so wrap each line
in quotes.</p>
    </details>
    <details><summary><b>def at(path)</b></summary>
    <p>Return a Distribution for the indicated metadata path

:param path: a string or path-like object
:return: a concrete Distribution instance for the path</p>
    </details>
    <details><summary><b>def discover(**kwargs)</b></summary>
    <p>Return an iterable of Distribution objects for all packages.

Pass a ``context`` or pass keyword arguments for constructing
a context.

:context: A ``DistributionFinder.Context`` object.
:return: Iterable of Distribution objects for all packages.</p>
    </details>
    <li><b>entry_points:</b> <property object at 0x10121ac00></li>
    <li><b>files:</b> <property object at 0x10121ac50></li>
    <details><summary><b>def from_name(name: str)</b></summary>
    <p>Return the Distribution for the given package name.

:param name: The name of the distribution package to search for.
:return: The Distribution instance (or subclass thereof) for the named
    package, if found.
:raises PackageNotFoundError: When the named package's distribution
    metadata cannot be found.
:raises ValueError: When an invalid value is supplied for name.</p>
    </details>
    <details><summary><b>def locate_file(self, path)</b></summary>
    <p>Given a path to a file in this distribution, return a path
to it.</p>
    </details>
    <li><b>metadata:</b> <property object at 0x10121aac0></li>
    <li><b>name:</b> <property object at 0x10121ab10></li>
    <details><summary><b>def read_text(self, filename)</b></summary>
    <p>Attempt to load metadata file given by the name.

:param filename: The name of the file in the distribution info.
:return: The text if found, otherwise None.</p>
    </details>
    <li><b>requires:</b> <property object at 0x10121aca0></li>
    <li><b>version:</b> <property object at 0x10121abb0></li>
    </details>
    <details><summary><h5>class DistributionFinder(MetaPathFinder)</h5></summary>
    <li><b>Context:</b> <class 'importlib.metadata.DistributionFinder.Context'></li>
    <details><summary><b>def find_distributions(self, context=<importlib.metadata.DistributionFinder.Context object at 0x1012311d0>)</b></summary>
    <p>Find distributions.

Return an iterable of all Distribution instances capable of
loading the metadata for packages matching the ``context``,
a DistributionFinder.Context instance.</p>
    </details>
    <details><summary><b>def find_module(self, fullname, path)</b></summary>
    <p>Return a loader for the module.

If no module is found, return None.  The fullname is a str and
the path is a list of strings or None.

This method is deprecated since Python 3.4 in favor of
finder.find_spec(). If find_spec() exists then backwards-compatible
functionality is provided for this method.</p>
    </details>
    <details><summary><b>def invalidate_caches(self)</b></summary>
    <p>An optional method for clearing the finder's cache, if any.
This method is used by importlib.invalidate_caches().</p>
    </details>
    </details>
    <details><summary><h5>class EntryPoint(DeprecatedTuple)</h5></summary>
    <details><summary><b>def __eq__(self, other)</b></summary>
    <p>Return self==value.</p>
    </details>
    <details><summary><b>def __getitem__(self, item)</b></summary>
    </details>
    <details><summary><b>def __hash__(self)</b></summary>
    <p>Return hash(self).</p>
    </details>
    <details><summary><b>def __init__(self, name, value, group)</b></summary>
    <p>Initialize self.  See help(type(self)) for accurate signature.</p>
    </details>
    <details><summary><b>def __iter__(self)</b></summary>
    <p>Supply iter so one may construct dicts of EntryPoints by name.</p>
    </details>
    <details><summary><b>def __lt__(self, other)</b></summary>
    <p>Return self<value.</p>
    </details>
    <details><summary><b>def __repr__(self)</b></summary>
    <p>Return repr(self).</p>
    </details>
    <details><summary><b>def __setattr__(self, name, value)</b></summary>
    <p>Implement setattr(self, name, value).</p>
    </details>
    <details><summary><b>def _for(self, dist)</b></summary>
    </details>
    <details><summary><b>def _key(self)</b></summary>
    </details>
    <li><b>attr:</b> <property object at 0x10121a4d0></li>
    <li><b>dist:</b> None</li>
    <li><b>extras:</b> <property object at 0x10121a5c0></li>
    <details><summary><b>def load(self)</b></summary>
    <p>Load the entry point from its definition. If only a module
is indicated by the value, return that module. Otherwise,
return the named object.</p>
    </details>
    <details><summary><b>def matches(self, **params)</b></summary>
    <p>EntryPoint matches the given parameters.

>>> ep = EntryPoint(group='foo', name='bar', value='bing:bong [extra1, extra2]')
>>> ep.matches(group='foo')
True
>>> ep.matches(name='bar', value='bing:bong [extra1, extra2]')
True
>>> ep.matches(group='foo', name='other')
False
>>> ep.matches()
True
>>> ep.matches(extras=['extra1', 'extra2'])
True
>>> ep.matches(module='bing')
True
>>> ep.matches(attr='bong')
True</p>
    </details>
    <li><b>module:</b> <property object at 0x10121a480></li>
    <li><b>pattern:</b> re.compile('(?P<module>[\\w.]+)\\s*(:\\s*(?P<attr>[\\w.]+)\\s*)?((?P<extras>\\[.*\\])\\s*)?$')</li>
    </details>
    <details><summary><h5>class EntryPoints(DeprecatedList)</h5></summary>
    <details><summary><b>def __add__(self, other)</b></summary>
    <p>Return self+value.</p>
    </details>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <details><summary><b>def __eq__(self, other)</b></summary>
    <p>Return self==value.</p>
    </details>
    <details><summary><b>def __getitem__(self, name)</b></summary>
    <p>Get the EntryPoint in self matching name.</p>
    </details>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <details><summary><b>def _from_text(text)</b></summary>
    </details>
    <details><summary><b>def _from_text_for(text, dist)</b></summary>
    </details>
    <details><summary><b>def _wrap_deprecated_method(method_name: str)</b></summary>
    </details>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <li><b>clear:</b> <method 'clear' of 'list' objects></li>
    <li><b>copy:</b> <method 'copy' of 'list' objects></li>
    <li><b>count:</b> <method 'count' of 'list' objects></li>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <li><b>groups:</b> <property object at 0x10121a750></li>
    <li><b>index:</b> <method 'index' of 'list' objects></li>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <li><b>names:</b> <property object at 0x10121a700></li>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    <details><summary><b>def select(self, **params)</b></summary>
    <p>Select entry points from self that match the
given parameters (typically group and/or name).</p>
    </details>
    <details><summary><b>def wrapped(self, *args, **kwargs)</b></summary>
    </details>
    </details>
    <details><summary><h5>class FastPath(object)</h5></summary>
    <details><summary><b>def __init__(self, root)</b></summary>
    <p>Initialize self.  See help(type(self)) for accurate signature.</p>
    </details>
    <details><summary><b>def children(self)</b></summary>
    </details>
    <details><summary><b>def joinpath(self, child)</b></summary>
    </details>
    <details><summary><b>def wrapper(self, *args, **kwargs)</b></summary>
    </details>
    <li><b>mtime:</b> <property object at 0x10121ae80></li>
    <details><summary><b>def search(self, name)</b></summary>
    </details>
    <details><summary><b>def zip_children(self)</b></summary>
    </details>
    </details>
    <details><summary><h5>class FileHash(object)</h5></summary>
    <details><summary><b>def __init__(self, spec)</b></summary>
    <p>Initialize self.  See help(type(self)) for accurate signature.</p>
    </details>
    <details><summary><b>def __repr__(self)</b></summary>
    <p>Return repr(self).</p>
    </details>
    </details>
    <details><summary><h5>class FreezableDefaultDict(defaultdict)</h5></summary>
    <details><summary><b>def __missing__(self, key)</b></summary>
    <p>__missing__(key) # Called by __getitem__ for missing key; pseudo-code:
if self.default_factory is None: raise KeyError((key,))
self[key] = value = self.default_factory()
return value</p>
    </details>
    <li><b>clear:</b> <method 'clear' of 'dict' objects></li>
    <li><b>copy:</b> <method 'copy' of 'collections.defaultdict' objects></li>
    <li><b>default_factory:</b> <member 'default_factory' of 'collections.defaultdict' objects></li>
    <details><summary><b>def freeze(self)</b></summary>
    </details>
    <li><b>fromkeys:</b> <built-in method fromkeys of type object at 0x112e46ef0></li>
    <li><b>get:</b> <method 'get' of 'dict' objects></li>
    <li><b>items:</b> <method 'items' of 'dict' objects></li>
    <li><b>keys:</b> <method 'keys' of 'dict' objects></li>
    <li><b>pop:</b> <method 'pop' of 'dict' objects></li>
    <li><b>popitem:</b> <method 'popitem' of 'dict' objects></li>
    <li><b>setdefault:</b> <method 'setdefault' of 'dict' objects></li>
    <li><b>update:</b> <method 'update' of 'dict' objects></li>
    <li><b>values:</b> <method 'values' of 'dict' objects></li>
    </details>
    <li><b>List:</b> typing.List</li>
    <details><summary><h5>class Lookup(object)</h5></summary>
    <details><summary><b>def __init__(self, path: importlib.metadata.FastPath)</b></summary>
    <p>Initialize self.  See help(type(self)) for accurate signature.</p>
    </details>
    <details><summary><b>def search(self, prepared)</b></summary>
    </details>
    </details>
    <li><b>Mapping:</b> typing.Mapping</li>
    <details><summary><h5>class MetaPathFinder(object)</h5></summary>
    <details><summary><b>def find_module(self, fullname, path)</b></summary>
    <p>Return a loader for the module.

If no module is found, return None.  The fullname is a str and
the path is a list of strings or None.

This method is deprecated since Python 3.4 in favor of
finder.find_spec(). If find_spec() exists then backwards-compatible
functionality is provided for this method.</p>
    </details>
    <details><summary><b>def invalidate_caches(self)</b></summary>
    <p>An optional method for clearing the finder's cache, if any.
This method is used by importlib.invalidate_caches().</p>
    </details>
    </details>
    <details><summary><h5>class MetadataPathFinder(DistributionFinder)</h5></summary>
    <li><b>Context:</b> <class 'importlib.metadata.DistributionFinder.Context'></li>
    <details><summary><b>def _search_paths(name, paths)</b></summary>
    <p>Find metadata directories in paths heuristically.</p>
    </details>
    <details><summary><b>def find_distributions(context=<importlib.metadata.DistributionFinder.Context object at 0x101231790>)</b></summary>
    <p>Find distributions.

Return an iterable of all Distribution instances capable of
loading the metadata for packages matching ``context.name``
(or all names if ``None`` indicated) along the paths in the list
of directories ``context.path``.</p>
    </details>
    <details><summary><b>def find_module(self, fullname, path)</b></summary>
    <p>Return a loader for the module.

If no module is found, return None.  The fullname is a str and
the path is a list of strings or None.

This method is deprecated since Python 3.4 in favor of
finder.find_spec(). If find_spec() exists then backwards-compatible
functionality is provided for this method.</p>
    </details>
    <details><summary><b>def invalidate_caches()</b></summary>
    <p>An optional method for clearing the finder's cache, if any.
This method is used by importlib.invalidate_caches().</p>
    </details>
    </details>
    <li><b>Optional:</b> typing.Optional</li>
    <details><summary><h5>class PackageMetadata(Protocol)</h5></summary>
    <details><summary><b>def __class_getitem__(params)</b></summary>
    <p>Parameterizes a generic class.

At least, parameterizing a generic class is the *main* thing this method
does. For example, for some generic class `Foo`, this is called when we
do `Foo[int]` - there, with `cls=Foo` and `params=int`.

However, note that this method is also called when defining generic
classes in the first place with `class Foo(Generic[T]): ...`.</p>
    </details>
    <details><summary><b>def __contains__(self, item: str) -> bool</b></summary>
    </details>
    <details><summary><b>def __getitem__(self, key: str) -> str</b></summary>
    </details>
    <details><summary><b>def _no_init_or_replace_init(self, *args, **kwargs)</b></summary>
    </details>
    <details><summary><b>def __init_subclass__(*args, **kwargs)</b></summary>
    <p>This method is called when a class is subclassed.

The default implementation does nothing. It may be
overridden to extend subclasses.</p>
    </details>
    <details><summary><b>def __iter__(self) -> Iterator[str]</b></summary>
    </details>
    <details><summary><b>def __len__(self) -> int</b></summary>
    </details>
    <details><summary><b>def _proto_hook(other)</b></summary>
    </details>
    <details><summary><b>def get_all(self, name: str, failobj: ~_T = Ellipsis) -> Union[List[Any], ~_T]</b></summary>
    <p>Return all values associated with a possibly multi-valued key.</p>
    </details>
    <li><b>json:</b> <property object at 0x1011cb9c0></li>
    </details>
    <details><summary><h5>class PackageNotFoundError(ModuleNotFoundError)</h5></summary>
    <details><summary><b>def __str__(self)</b></summary>
    <p>Return str(self).</p>
    </details>
    <li><b>add_note:</b> <method 'add_note' of 'BaseException' objects></li>
    <li><b>args:</b> <attribute 'args' of 'BaseException' objects></li>
    <li><b>msg:</b> <member 'msg' of 'ImportError' objects></li>
    <li><b>name:</b> <property object at 0x101104e50></li>
    <li><b>path:</b> <member 'path' of 'ImportError' objects></li>
    <li><b>with_traceback:</b> <method 'with_traceback' of 'BaseException' objects></li>
    </details>
    <details><summary><h5>class PackagePath(PurePosixPath)</h5></summary>
    <details><summary><b>def __bytes__(self)</b></summary>
    <p>Return the bytes representation of the path.  This is only
recommended to use under Unix.</p>
    </details>
    <details><summary><b>def __eq__(self, other)</b></summary>
    <p>Return self==value.</p>
    </details>
    <details><summary><b>def __fspath__(self)</b></summary>
    </details>
    <details><summary><b>def __ge__(self, other)</b></summary>
    <p>Return self>=value.</p>
    </details>
    <details><summary><b>def __gt__(self, other)</b></summary>
    <p>Return self>value.</p>
    </details>
    <details><summary><b>def __hash__(self)</b></summary>
    <p>Return hash(self).</p>
    </details>
    <details><summary><b>def __le__(self, other)</b></summary>
    <p>Return self<=value.</p>
    </details>
    <details><summary><b>def __lt__(self, other)</b></summary>
    <p>Return self<value.</p>
    </details>
    <details><summary><b>def __new__(cls, *args)</b></summary>
    <p>Construct a PurePath from one or several strings and or existing
PurePath objects.  The strings and path objects are combined so as
to yield a canonicalized path, which is incorporated into the
new PurePath object.</p>
    </details>
    <details><summary><b>def __reduce__(self)</b></summary>
    <p>Helper for pickle.</p>
    </details>
    <details><summary><b>def __repr__(self)</b></summary>
    <p>Return repr(self).</p>
    </details>
    <details><summary><b>def __rtruediv__(self, key)</b></summary>
    </details>
    <details><summary><b>def __str__(self)</b></summary>
    <p>Return the string representation of the path, suitable for
passing to system calls.</p>
    </details>
    <details><summary><b>def __truediv__(self, key)</b></summary>
    </details>
    <details><summary><b>def _format_parsed_parts(drv, root, parts)</b></summary>
    </details>
    <details><summary><b>def _from_parsed_parts(drv, root, parts)</b></summary>
    </details>
    <details><summary><b>def _from_parts(args)</b></summary>
    </details>
    <details><summary><b>def _make_child(self, args)</b></summary>
    </details>
    <details><summary><b>def _parse_args(args)</b></summary>
    </details>
    <li><b>anchor:</b> <property object at 0x100d894e0></li>
    <details><summary><b>def as_posix(self)</b></summary>
    <p>Return the string representation of the path with forward (/)
slashes.</p>
    </details>
    <details><summary><b>def as_uri(self)</b></summary>
    <p>Return the path as a 'file' URI.</p>
    </details>
    <li><b>drive:</b> <property object at 0x100d89440></li>
    <details><summary><b>def is_absolute(self)</b></summary>
    <p>True if the path is absolute (has both a root and, if applicable,
a drive).</p>
    </details>
    <details><summary><b>def is_relative_to(self, *other)</b></summary>
    <p>Return True if the path is relative to another path or False.
        </p>
    </details>
    <details><summary><b>def is_reserved(self)</b></summary>
    <p>Return True if the path contains one of the special names reserved
by the system, if any.</p>
    </details>
    <details><summary><b>def joinpath(self, *args)</b></summary>
    <p>Combine this path with one or several arguments, and return a
new path representing either a subpath (if all arguments are relative
paths) or a totally different path (if one of the arguments is
anchored).</p>
    </details>
    <details><summary><b>def locate(self)</b></summary>
    <p>Return a path-like object for this path</p>
    </details>
    <details><summary><b>def match(self, path_pattern)</b></summary>
    <p>Return True if this path matches the given pattern.</p>
    </details>
    <li><b>name:</b> <property object at 0x100d89530></li>
    <li><b>parent:</b> <property object at 0x100d896c0></li>
    <li><b>parents:</b> <property object at 0x100d89710></li>
    <li><b>parts:</b> <property object at 0x100d89670></li>
    <details><summary><b>def read_binary(self)</b></summary>
    </details>
    <details><summary><b>def read_text(self, encoding='utf-8')</b></summary>
    </details>
    <details><summary><b>def relative_to(self, *other)</b></summary>
    <p>Return the relative path to another path identified by the passed
arguments.  If the operation is not possible (because this is not
a subpath of the other path), raise ValueError.</p>
    </details>
    <li><b>root:</b> <property object at 0x100d89490></li>
    <li><b>stem:</b> <property object at 0x100d89620></li>
    <li><b>suffix:</b> <property object at 0x100d89580></li>
    <li><b>suffixes:</b> <property object at 0x100d895d0></li>
    <details><summary><b>def with_name(self, name)</b></summary>
    <p>Return a new path with the file name changed.</p>
    </details>
    <details><summary><b>def with_stem(self, stem)</b></summary>
    <p>Return a new path with the stem changed.</p>
    </details>
    <details><summary><b>def with_suffix(self, suffix)</b></summary>
    <p>Return a new path with the file suffix changed.  If the path
has no suffix, add given suffix.  If the given suffix is an empty
string, remove the suffix from the path.</p>
    </details>
    </details>
    <details><summary><h5>class Pair(Pair)</h5></summary>
    <details><summary><b>def __getnewargs__(self)</b></summary>
    <p>Return self as a plain tuple.  Used by copy and pickle.</p>
    </details>
    <details><summary><b>def __new__(_cls, name, value)</b></summary>
    <p>Create new instance of Pair(name, value)</p>
    </details>
    <details><summary><b>def __repr__(self)</b></summary>
    <p>Return a nicely formatted representation string</p>
    </details>
    <details><summary><b>def _asdict(self)</b></summary>
    <p>Return a new dict which maps field names to their values.</p>
    </details>
    <details><summary><b>def _make(iterable)</b></summary>
    <p>Make a new Pair object from a sequence or iterable</p>
    </details>
    <details><summary><b>def _replace(self, /, **kwds)</b></summary>
    <p>Return a new Pair object replacing specified fields with new values</p>
    </details>
    <li><b>count:</b> <method 'count' of 'tuple' objects></li>
    <li><b>index:</b> <method 'index' of 'tuple' objects></li>
    <li><b>name:</b> _tuplegetter(0, 'Alias for field number 0')</li>
    <details><summary><b>def parse(text)</b></summary>
    </details>
    <li><b>value:</b> _tuplegetter(1, 'Alias for field number 1')</li>
    </details>
    <details><summary><h5>class PathDistribution(Distribution)</h5></summary>
    <details><summary><b>def __init__(self, path: importlib.metadata._meta.SimplePath)</b></summary>
    <p>Construct a distribution.

:param path: SimplePath indicating the metadata directory.</p>
    </details>
    <details><summary><b>def _convert_egg_info_reqs_to_simple_reqs(sections)</b></summary>
    <p>Historically, setuptools would solicit and store 'extra'
requirements, including those with environment markers,
in separate sections. More modern tools expect each
dependency to be defined separately, with any relevant
extras and environment markers attached directly to that
requirement. This method converts the former to the
latter. See _test_deps_from_requires_text for an example.</p>
    </details>
    <details><summary><b>def _deps_from_requires_text(source)</b></summary>
    </details>
    <details><summary><b>def _discover_resolvers()</b></summary>
    <p>Search the meta_path for resolvers.</p>
    </details>
    <details><summary><b>def _name_from_stem(stem)</b></summary>
    <p>>>> PathDistribution._name_from_stem('foo-3.0.egg-info')
'foo'
>>> PathDistribution._name_from_stem('CherryPy-3.0.dist-info')
'CherryPy'
>>> PathDistribution._name_from_stem('face.egg-info')
'face'
>>> PathDistribution._name_from_stem('foo.bar')</p>
    </details>
    <details><summary><b>def _read_dist_info_reqs(self)</b></summary>
    </details>
    <details><summary><b>def _read_egg_info_reqs(self)</b></summary>
    </details>
    <details><summary><b>def _read_files_distinfo(self)</b></summary>
    <p>Read the lines of RECORD</p>
    </details>
    <details><summary><b>def _read_files_egginfo(self)</b></summary>
    <p>SOURCES.txt might contain literal commas, so wrap each line
in quotes.</p>
    </details>
    <details><summary><b>def at(path)</b></summary>
    <p>Return a Distribution for the indicated metadata path

:param path: a string or path-like object
:return: a concrete Distribution instance for the path</p>
    </details>
    <details><summary><b>def discover(**kwargs)</b></summary>
    <p>Return an iterable of Distribution objects for all packages.

Pass a ``context`` or pass keyword arguments for constructing
a context.

:context: A ``DistributionFinder.Context`` object.
:return: Iterable of Distribution objects for all packages.</p>
    </details>
    <li><b>entry_points:</b> <property object at 0x10121ac00></li>
    <li><b>files:</b> <property object at 0x10121ac50></li>
    <details><summary><b>def from_name(name: str)</b></summary>
    <p>Return the Distribution for the given package name.

:param name: The name of the distribution package to search for.
:return: The Distribution instance (or subclass thereof) for the named
    package, if found.
:raises PackageNotFoundError: When the named package's distribution
    metadata cannot be found.
:raises ValueError: When an invalid value is supplied for name.</p>
    </details>
    <details><summary><b>def locate_file(self, path)</b></summary>
    <p>Given a path to a file in this distribution, return a path
to it.</p>
    </details>
    <li><b>metadata:</b> <property object at 0x10121aac0></li>
    <li><b>name:</b> <property object at 0x10121ab10></li>
    <details><summary><b>def read_text(self, filename)</b></summary>
    <p>Attempt to load metadata file given by the name.

:param filename: The name of the file in the distribution info.
:return: The text if found, otherwise None.</p>
    </details>
    <li><b>requires:</b> <property object at 0x10121aca0></li>
    <li><b>version:</b> <property object at 0x10121abb0></li>
    </details>
    <details><summary><h5>class Prepared(object)</h5></summary>
    <details><summary><b>def __bool__(self)</b></summary>
    </details>
    <details><summary><b>def __init__(self, name)</b></summary>
    <p>Initialize self.  See help(type(self)) for accurate signature.</p>
    </details>
    <details><summary><b>def legacy_normalize(name)</b></summary>
    <p>Normalize the package name as found in the convention in
older packaging tools versions and specs.</p>
    </details>
    <li><b>legacy_normalized:</b> None</li>
    <details><summary><b>def normalize(name)</b></summary>
    <p>PEP 503 normalization plus dashes as underscores.</p>
    </details>
    <li><b>normalized:</b> None</li>
    </details>
    <details><summary><h5>class Sectioned(object)</h5></summary>
    <details><summary><b>def read(text, filter_=None)</b></summary>
    </details>
    <details><summary><b>def section_pairs(text)</b></summary>
    </details>
    <details><summary><b>def valid(line)</b></summary>
    </details>
    </details>
    <details><summary><h5>class SelectableGroups(Deprecated, dict)</h5></summary>
    <details><summary><b>def __contains__(self, *args)</b></summary>
    </details>
    <details><summary><b>def __getitem__(self, name)</b></summary>
    </details>
    <details><summary><b>def __iter__(self)</b></summary>
    </details>
    <li><b>clear:</b> <method 'clear' of 'dict' objects></li>
    <li><b>copy:</b> <method 'copy' of 'dict' objects></li>
    <li><b>fromkeys:</b> <built-in method fromkeys of type object at 0x112e57ae0></li>
    <details><summary><b>def get(self, name, default=None)</b></summary>
    </details>
    <li><b>groups:</b> <property object at 0x10121a930></li>
    <li><b>items:</b> <method 'items' of 'dict' objects></li>
    <details><summary><b>def keys(self)</b></summary>
    </details>
    <details><summary><b>def load(eps)</b></summary>
    </details>
    <li><b>names:</b> <property object at 0x10121a980></li>
    <li><b>pop:</b> <method 'pop' of 'dict' objects></li>
    <li><b>popitem:</b> <method 'popitem' of 'dict' objects></li>
    <details><summary><b>def select(self, **params)</b></summary>
    </details>
    <li><b>setdefault:</b> <method 'setdefault' of 'dict' objects></li>
    <li><b>update:</b> <method 'update' of 'dict' objects></li>
    <details><summary><b>def values(self)</b></summary>
    </details>
    </details>
    <details><summary><h5>class SimplePath(Protocol)</h5></summary>
    <details><summary><b>def __class_getitem__(params)</b></summary>
    <p>Parameterizes a generic class.

At least, parameterizing a generic class is the *main* thing this method
does. For example, for some generic class `Foo`, this is called when we
do `Foo[int]` - there, with `cls=Foo` and `params=int`.

However, note that this method is also called when defining generic
classes in the first place with `class Foo(Generic[T]): ...`.</p>
    </details>
    <details><summary><b>def _no_init_or_replace_init(self, *args, **kwargs)</b></summary>
    </details>
    <details><summary><b>def __init_subclass__(*args, **kwargs)</b></summary>
    <p>This method is called when a class is subclassed.

The default implementation does nothing. It may be
overridden to extend subclasses.</p>
    </details>
    <details><summary><b>def _proto_hook(other)</b></summary>
    </details>
    <details><summary><b>def __truediv__(self) -> 'SimplePath'</b></summary>
    </details>
    <details><summary><b>def joinpath(self) -> 'SimplePath'</b></summary>
    </details>
    <details><summary><b>def parent(self) -> 'SimplePath'</b></summary>
    </details>
    <details><summary><b>def read_text(self) -> str</b></summary>
    </details>
    </details>
    <li><b>Union:</b> typing.Union</li>
    <details><summary><h5>module abc</h5></summary>
    </details>
    <details><summary><b>def always_iterable(obj, base_type=(<class 'str'>, <class 'bytes'>))</b></summary>
    <p>If *obj* is iterable, return an iterator over its items::

    >>> obj = (1, 2, 3)
    >>> list(always_iterable(obj))
    [1, 2, 3]

If *obj* is not iterable, return a one-item iterable containing *obj*::

    >>> obj = 1
    >>> list(always_iterable(obj))
    [1]

If *obj* is ``None``, return an empty iterable:

    >>> obj = None
    >>> list(always_iterable(None))
    []

By default, binary and text strings are not considered iterable::

    >>> obj = 'foo'
    >>> list(always_iterable(obj))
    ['foo']

If *base_type* is set, objects for which ``isinstance(obj, base_type)``
returns ``True`` won't be considered iterable.

    >>> obj = {'a': 1}
    >>> list(always_iterable(obj))  # Iterate over the dict's keys
    ['a']
    >>> list(always_iterable(obj, base_type=dict))  # Treat dicts as a unit
    [{'a': 1}]

Set *base_type* to ``None`` to avoid any special handling and treat objects
Python considers iterable as iterable:

    >>> obj = 'foo'
    >>> list(always_iterable(obj, base_type=None))
    ['f', 'o', 'o']</p>
    </details>
    <details><summary><h5>module collections</h5></summary>
    </details>
    <details><summary><h5>module csv</h5></summary>
    </details>
    <details><summary><b>def distribution(distribution_name)</b></summary>
    <p>Get the ``Distribution`` instance for the named package.

:param distribution_name: The name of the distribution package as a string.
:return: A ``Distribution`` instance (or subclass thereof).</p>
    </details>
    <details><summary><b>def distributions(**kwargs)</b></summary>
    <p>Get all ``Distribution`` instances in the current environment.

:return: An iterable of ``Distribution`` instances.</p>
    </details>
    <details><summary><h5>module email</h5></summary>
    </details>
    <details><summary><b>def entry_points(**params) -> Union[importlib.metadata.EntryPoints, importlib.metadata.SelectableGroups]</b></summary>
    <p>Return EntryPoint objects for all installed packages.

Pass selection parameters (group or name) to filter the
result to entry points matching those properties (see
EntryPoints.select()).

For compatibility, returns ``SelectableGroups`` object unless
selection parameters are supplied. In the future, this function
will return ``EntryPoints`` instead of ``SelectableGroups``
even when no selection parameters are supplied.

For maximum future compatibility, pass selection parameters
or invoke ``.select`` with parameters on the result.

:return: EntryPoints or SelectableGroups for all installed packages.</p>
    </details>
    <details><summary><b>def files(distribution_name)</b></summary>
    <p>Return a list of files for the named package.

:param distribution_name: The name of the distribution package to query.
:return: List of files composing the distribution.</p>
    </details>
    <details><summary><h5>module functools</h5></summary>
    </details>
    <details><summary><b>def import_module(name, package=None)</b></summary>
    <p>Import a module.

The 'package' argument is required when performing a relative import. It
specifies the package to use as the anchor point from which to resolve the
relative import to an absolute import.</p>
    </details>
    <details><summary><h5>module itertools</h5></summary>
    </details>
    <details><summary><b>def metadata(distribution_name) -> importlib.metadata._meta.PackageMetadata</b></summary>
    <p>Get the metadata for the named package.

:param distribution_name: The name of the distribution package to query.
:return: A PackageMetadata containing the parsed metadata.</p>
    </details>
    <details><summary><b>def method_cache(method, cache_wrapper=None)</b></summary>
    <p>Wrap lru_cache to support storing the cache data in the object instances.

Abstracts the common paradigm where the method explicitly saves an
underscore-prefixed protected property on first call and returns that
subsequently.

>>> class MyClass:
...     calls = 0
...
...     @method_cache
...     def method(self, value):
...         self.calls += 1
...         return value

>>> a = MyClass()
>>> a.method(3)
3
>>> for x in range(75):
...     res = a.method(x)
>>> a.calls
75

Note that the apparent behavior will be exactly like that of lru_cache
except that the cache is stored on each instance, so values in one
instance will not flush values from another, and when an instance is
deleted, so are the cached values for that instance.

>>> b = MyClass()
>>> for x in range(35):
...     res = b.method(x)
>>> b.calls
35
>>> a.method(0)
0
>>> a.calls
75

Note that if method had been decorated with ``functools.lru_cache()``,
a.calls would have been 76 (due to the cached value of 0 having been
flushed by the 'b' instance).

Clear the cache with ``.cache_clear()``

>>> a.method.cache_clear()

Same for a method that hasn't yet been called.

>>> c = MyClass()
>>> c.method.cache_clear()

Another cache wrapper may be supplied:

>>> cache = functools.lru_cache(maxsize=2)
>>> MyClass.method2 = method_cache(lambda self: 3, cache_wrapper=cache)
>>> a = MyClass()
>>> a.method2()
3

Caution - do not subsequently wrap the method with another decorator, such
as ``@property``, which changes the semantics of the function.

See also
http://code.activestate.com/recipes/577452-a-memoize-decorator-for-instance-methods/
for another implementation and additional justification.</p>
    </details>
    <details><summary><h5>module operator</h5></summary>
    </details>
    <details><summary><h5>module os</h5></summary>
    </details>
    <details><summary><b>def packages_distributions() -> Mapping[str, List[str]]</b></summary>
    <p>Return a mapping of top-level packages to their
distributions.

>>> import collections.abc
>>> pkgs = packages_distributions()
>>> all(isinstance(dist, collections.abc.Sequence) for dist in pkgs.values())
True</p>
    </details>
    <details><summary><b>def pass_none(func)</b></summary>
    <p>Wrap func so it's not called if its first param is None

>>> print_text = pass_none(print)
>>> print_text('text')
text
>>> print_text(None)</p>
    </details>
    <details><summary><h5>module pathlib</h5></summary>
    </details>
    <details><summary><h5>module posixpath</h5></summary>
    </details>
    <details><summary><h5>module re</h5></summary>
    </details>
    <details><summary><b>def requires(distribution_name)</b></summary>
    <p>Return a list of requirements for the named package.

:return: An iterator of requirements, suitable for
    packaging.requirement.Requirement.</p>
    </details>
    <details><summary><h5>class starmap(object)</h5></summary>
    </details>
    <details><summary><h5>class suppress(AbstractContextManager)</h5></summary>
    <!-- Error processing item: no signature found for builtin type <class 'types.GenericAlias'> -->
    <details><summary><h5>module sys</h5></summary>
    </details>
    <details><summary><h5>module textwrap</h5></summary>
    </details>
    <details><summary><b>def unique_everseen(iterable, key=None)</b></summary>
    <p>List unique elements, preserving order. Remember all elements ever seen.</p>
    </details>
    <details><summary><b>def version(distribution_name)</b></summary>
    <p>Get the version string for the named package.

:param distribution_name: The name of the distribution package to query.
:return: The version string for the package as defined in the package's
    "Version" metadata key.</p>
    </details>
    <details><summary><h5>module warnings</h5></summary>
    </details>
    <details><summary><h5>module zipfile</h5></summary>
    </details>
  </details>
  <details><summary><h4>module importlib.readers</h4></summary>
    <details><summary><h5>class FileReader(TraversableResources)</h5></summary>
    <details><summary><b>def __init__(self, loader)</b></summary>
    <p>Initialize self.  See help(type(self)) for accurate signature.</p>
    </details>
    <details><summary><b>def contents(self) -> Iterator[str]</b></summary>
    <p>Return an iterable of entries in `package`.</p>
    </details>
    <details><summary><b>def files(self)</b></summary>
    <p>Return a Traversable object for the loaded package.</p>
    </details>
    <details><summary><b>def is_resource(self, path: Union[str, os.PathLike[str]]) -> bool</b></summary>
    <p>Return True if the named 'path' is a resource.

Files are resources, directories are not.</p>
    </details>
    <details><summary><b>def open_resource(self, resource: Union[str, os.PathLike[str]]) -> _io.BufferedReader</b></summary>
    <p>Return an opened, file-like object for binary reading.

The 'resource' argument is expected to represent only a file name.
If the resource cannot be found, FileNotFoundError is raised.</p>
    </details>
    <details><summary><b>def resource_path(self, resource)</b></summary>
    <p>Return the file system path to prevent
`resources.path()` from creating a temporary
copy.</p>
    </details>
    </details>
    <details><summary><h5>class MultiplexedPath(Traversable)</h5></summary>
    <details><summary><b>def __class_getitem__(params)</b></summary>
    <p>Parameterizes a generic class.

At least, parameterizing a generic class is the *main* thing this method
does. For example, for some generic class `Foo`, this is called when we
do `Foo[int]` - there, with `cls=Foo` and `params=int`.

However, note that this method is also called when defining generic
classes in the first place with `class Foo(Generic[T]): ...`.</p>
    </details>
    <details><summary><b>def __init__(self, *paths)</b></summary>
    <p>Initialize self.  See help(type(self)) for accurate signature.</p>
    </details>
    <details><summary><b>def __init_subclass__(*args, **kwargs)</b></summary>
    <p>This method is called when a class is subclassed.

The default implementation does nothing. It may be
overridden to extend subclasses.</p>
    </details>
    <details><summary><b>def __repr__(self)</b></summary>
    <p>Return repr(self).</p>
    </details>
    <details><summary><b>def _proto_hook(other)</b></summary>
    </details>
    <details><summary><b>def joinpath(self, child)</b></summary>
    <p>Return Traversable resolved with any descendants applied.

Each descendant should be a path segment relative to self
and each may contain multiple levels separated by
``posixpath.sep`` (``/``).</p>
    </details>
    <details><summary><b>def is_dir(self)</b></summary>
    <p>Return True if self is a directory</p>
    </details>
    <details><summary><b>def is_file(self)</b></summary>
    <p>Return True if self is a file</p>
    </details>
    <details><summary><b>def iterdir(self)</b></summary>
    <p>Yield Traversable objects in self</p>
    </details>
    <details><summary><b>def joinpath(self, child)</b></summary>
    <p>Return Traversable resolved with any descendants applied.

Each descendant should be a path segment relative to self
and each may contain multiple levels separated by
``posixpath.sep`` (``/``).</p>
    </details>
    <li><b>name:</b> <property object at 0x1012cd800></li>
    <details><summary><b>def open(self, *args, **kwargs)</b></summary>
    <p>mode may be 'r' or 'rb' to open as text or binary. Return a handle
suitable for reading (same as pathlib.Path.open).

When opening as text, accepts encoding parameters such as those
accepted by io.TextIOWrapper.</p>
    </details>
    <details><summary><b>def read_bytes(self)</b></summary>
    <p>Read contents of self as bytes</p>
    </details>
    <details><summary><b>def read_text(self, *args, **kwargs)</b></summary>
    <p>Read contents of self as text</p>
    </details>
    </details>
    <details><summary><h5>class NamespaceReader(TraversableResources)</h5></summary>
    <details><summary><b>def __init__(self, namespace_path)</b></summary>
    <p>Initialize self.  See help(type(self)) for accurate signature.</p>
    </details>
    <details><summary><b>def contents(self) -> Iterator[str]</b></summary>
    <p>Return an iterable of entries in `package`.</p>
    </details>
    <details><summary><b>def files(self)</b></summary>
    <p>Return a Traversable object for the loaded package.</p>
    </details>
    <details><summary><b>def is_resource(self, path: Union[str, os.PathLike[str]]) -> bool</b></summary>
    <p>Return True if the named 'path' is a resource.

Files are resources, directories are not.</p>
    </details>
    <details><summary><b>def open_resource(self, resource: Union[str, os.PathLike[str]]) -> _io.BufferedReader</b></summary>
    <p>Return an opened, file-like object for binary reading.

The 'resource' argument is expected to represent only a file name.
If the resource cannot be found, FileNotFoundError is raised.</p>
    </details>
    <details><summary><b>def resource_path(self, resource)</b></summary>
    <p>Return the file system path to prevent
`resources.path()` from creating a temporary
copy.</p>
    </details>
    </details>
    <details><summary><h5>class ZipReader(TraversableResources)</h5></summary>
    <details><summary><b>def __init__(self, loader, module)</b></summary>
    <p>Initialize self.  See help(type(self)) for accurate signature.</p>
    </details>
    <details><summary><b>def contents(self) -> Iterator[str]</b></summary>
    <p>Return an iterable of entries in `package`.</p>
    </details>
    <details><summary><b>def files(self)</b></summary>
    <p>Return a Traversable object for the loaded package.</p>
    </details>
    <details><summary><b>def is_resource(self, path)</b></summary>
    <p>Return True if the named 'path' is a resource.

Files are resources, directories are not.</p>
    </details>
    <details><summary><b>def open_resource(self, resource)</b></summary>
    <p>Return an opened, file-like object for binary reading.

The 'resource' argument is expected to represent only a file name.
If the resource cannot be found, FileNotFoundError is raised.</p>
    </details>
    <details><summary><b>def resource_path(self, resource: Any) -> NoReturn</b></summary>
    <p>Return the file system path to the specified resource.

The 'resource' argument is expected to represent only a file name.
If the resource does not exist on the file system, raise
FileNotFoundError.</p>
    </details>
    </details>
  </details>
  <details><summary><b>def reload(module)</b></summary>
  <p>Reload the module and return it.

The module must have been successfully imported before.</p>
  </details>
  <details><summary><h4>module importlib.resources</h4></summary>
    <li><b>Package:</b> typing.Union[module, str]</li>
    <details><summary><h5>class str(object)</h5></summary>
    <li><b>capitalize:</b> <method 'capitalize' of 'str' objects></li>
    <li><b>casefold:</b> <method 'casefold' of 'str' objects></li>
    <li><b>center:</b> <method 'center' of 'str' objects></li>
    <li><b>count:</b> <method 'count' of 'str' objects></li>
    <li><b>encode:</b> <method 'encode' of 'str' objects></li>
    <li><b>endswith:</b> <method 'endswith' of 'str' objects></li>
    <li><b>expandtabs:</b> <method 'expandtabs' of 'str' objects></li>
    <li><b>find:</b> <method 'find' of 'str' objects></li>
    <li><b>format:</b> <method 'format' of 'str' objects></li>
    <li><b>format_map:</b> <method 'format_map' of 'str' objects></li>
    <li><b>index:</b> <method 'index' of 'str' objects></li>
    <li><b>isalnum:</b> <method 'isalnum' of 'str' objects></li>
    <li><b>isalpha:</b> <method 'isalpha' of 'str' objects></li>
    <li><b>isascii:</b> <method 'isascii' of 'str' objects></li>
    <li><b>isdecimal:</b> <method 'isdecimal' of 'str' objects></li>
    <li><b>isdigit:</b> <method 'isdigit' of 'str' objects></li>
    <li><b>isidentifier:</b> <method 'isidentifier' of 'str' objects></li>
    <li><b>islower:</b> <method 'islower' of 'str' objects></li>
    <li><b>isnumeric:</b> <method 'isnumeric' of 'str' objects></li>
    <li><b>isprintable:</b> <method 'isprintable' of 'str' objects></li>
    <li><b>isspace:</b> <method 'isspace' of 'str' objects></li>
    <li><b>istitle:</b> <method 'istitle' of 'str' objects></li>
    <li><b>isupper:</b> <method 'isupper' of 'str' objects></li>
    <li><b>join:</b> <method 'join' of 'str' objects></li>
    <li><b>ljust:</b> <method 'ljust' of 'str' objects></li>
    <li><b>lower:</b> <method 'lower' of 'str' objects></li>
    <li><b>lstrip:</b> <method 'lstrip' of 'str' objects></li>
    <li><b>maketrans:</b> <built-in method maketrans of type object at 0x102de47c8></li>
    <li><b>partition:</b> <method 'partition' of 'str' objects></li>
    <li><b>removeprefix:</b> <method 'removeprefix' of 'str' objects></li>
    <li><b>removesuffix:</b> <method 'removesuffix' of 'str' objects></li>
    <li><b>replace:</b> <method 'replace' of 'str' objects></li>
    <li><b>rfind:</b> <method 'rfind' of 'str' objects></li>
    <li><b>rindex:</b> <method 'rindex' of 'str' objects></li>
    <li><b>rjust:</b> <method 'rjust' of 'str' objects></li>
    <li><b>rpartition:</b> <method 'rpartition' of 'str' objects></li>
    <li><b>rsplit:</b> <method 'rsplit' of 'str' objects></li>
    <li><b>rstrip:</b> <method 'rstrip' of 'str' objects></li>
    <li><b>split:</b> <method 'split' of 'str' objects></li>
    <li><b>splitlines:</b> <method 'splitlines' of 'str' objects></li>
    <li><b>startswith:</b> <method 'startswith' of 'str' objects></li>
    <li><b>strip:</b> <method 'strip' of 'str' objects></li>
    <li><b>swapcase:</b> <method 'swapcase' of 'str' objects></li>
    <li><b>title:</b> <method 'title' of 'str' objects></li>
    <li><b>translate:</b> <method 'translate' of 'str' objects></li>
    <li><b>upper:</b> <method 'upper' of 'str' objects></li>
    <li><b>zfill:</b> <method 'zfill' of 'str' objects></li>
    </details>
    <details><summary><h5>class ResourceReader(object)</h5></summary>
    <details><summary><b>def contents(self) -> Iterable[str]</b></summary>
    <p>Return an iterable of entries in `package`.</p>
    </details>
    <details><summary><b>def is_resource(self, path: str) -> bool</b></summary>
    <p>Return True if the named 'path' is a resource.

Files are resources, directories are not.</p>
    </details>
    <details><summary><b>def open_resource(self, resource: str) -> <class 'BinaryIO'></b></summary>
    <p>Return an opened, file-like object for binary reading.

The 'resource' argument is expected to represent only a file name.
If the resource cannot be found, FileNotFoundError is raised.</p>
    </details>
    <details><summary><b>def resource_path(self, resource: str) -> str</b></summary>
    <p>Return the file system path to the specified resource.

The 'resource' argument is expected to represent only a file name.
If the resource does not exist on the file system, raise
FileNotFoundError.</p>
    </details>
    </details>
    <details><summary><h5>module importlib.resources.abc</h5></summary>
    </details>
    <details><summary><b>def as_file(path)</b></summary>
    <p>Given a Traversable object, return that object as a
path on the local file system in a context manager.</p>
    </details>
    <details><summary><b>def contents(package: Union[module, str]) -> Iterable[str]</b></summary>
    <p>Return an iterable of entries in `package`.

Note that not all entries are resources.  Specifically, directories are
not considered resources.  Use `is_resource()` on each entry returned here
to check if it is a resource or not.</p>
    </details>
    <details><summary><b>def files(package)</b></summary>
    <p>Get a Traversable resource from a package</p>
    </details>
    <details><summary><b>def is_resource(package: Union[module, str], name: str) -> bool</b></summary>
    <p>True if `name` is a resource inside `package`.

Directories are *not* resources.</p>
    </details>
    <details><summary><b>def open_binary(package: Union[module, str], resource: str) -> <class 'BinaryIO'></b></summary>
    <p>Return a file-like object opened for binary reading of the resource.</p>
    </details>
    <details><summary><b>def open_text(package: Union[module, str], resource: str, encoding: str = 'utf-8', errors: str = 'strict') -> <class 'TextIO'></b></summary>
    <p>Return a file-like object opened for text reading of the resource.</p>
    </details>
    <details><summary><b>def path(package: Union[module, str], resource: str) -> ContextManager[pathlib.Path]</b></summary>
    <p>A context manager providing a file path object to the resource.

If the resource does not already exist on its own on the file system,
a temporary file will be created. If the file was created, the file
will be deleted upon exiting the context manager (no exception is
raised if the file was deleted prior to the context manager
exiting).</p>
    </details>
    <details><summary><b>def read_binary(package: Union[module, str], resource: str) -> bytes</b></summary>
    <p>Return the binary contents of the resource.</p>
    </details>
    <details><summary><b>def read_text(package: Union[module, str], resource: str, encoding: str = 'utf-8', errors: str = 'strict') -> str</b></summary>
    <p>Return the decoded string of the resource.

The decoding-related arguments have the same semantics as those of
bytes.decode().</p>
    </details>
    <details><summary><h5>module importlib.resources.readers</h5></summary>
    </details>
  </details>
  <details><summary><h4>module sys</h4></summary>
  <!-- Error processing item: 'str' object has no attribute '__name__' -->
  <details><summary><h4>module importlib.util</h4></summary>
    <details><summary><h5>class LazyLoader(Loader)</h5></summary>
    <details><summary><b>def __check_eager_loader(loader)</b></summary>
    </details>
    <details><summary><b>def __init__(self, loader)</b></summary>
    <p>Initialize self.  See help(type(self)) for accurate signature.</p>
    </details>
    <details><summary><b>def create_module(self, spec)</b></summary>
    <p>Return a module to initialize and into which to load.

This method should raise ImportError if anything prevents it
from creating a new module.  It may return None to indicate
that the spec should create the new module.</p>
    </details>
    <details><summary><b>def exec_module(self, module)</b></summary>
    <p>Make the module load lazily.</p>
    </details>
    <details><summary><b>def factory(loader)</b></summary>
    <p>Construct a callable which returns the eager loader made lazy.</p>
    </details>
    <details><summary><b>def load_module(self, fullname)</b></summary>
    <p>Return the loaded module.

The module must be added to sys.modules and have import-related
attributes set properly.  The fullname is a str.

ImportError is raised on failure.

This method is deprecated in favor of loader.exec_module(). If
exec_module() exists then it is used to provide a backwards-compatible
functionality for this method.</p>
    </details>
    <details><summary><b>def module_repr(self, module)</b></summary>
    <p>Return a module's repr.

Used by the module type when the method does not raise
NotImplementedError.

This method is deprecated.</p>
    </details>
    </details>
    <details><summary><h5>class Loader(object)</h5></summary>
    <details><summary><b>def create_module(self, spec)</b></summary>
    <p>Return a module to initialize and into which to load.

This method should raise ImportError if anything prevents it
from creating a new module.  It may return None to indicate
that the spec should create the new module.</p>
    </details>
    <details><summary><b>def load_module(self, fullname)</b></summary>
    <p>Return the loaded module.

The module must be added to sys.modules and have import-related
attributes set properly.  The fullname is a str.

ImportError is raised on failure.

This method is deprecated in favor of loader.exec_module(). If
exec_module() exists then it is used to provide a backwards-compatible
functionality for this method.</p>
    </details>
    <details><summary><b>def module_repr(self, module)</b></summary>
    <p>Return a module's repr.

Used by the module type when the method does not raise
NotImplementedError.

This method is deprecated.</p>
    </details>
    </details>
  <!-- Error processing item: 'bytes' object has no attribute '__name__' -->
  <details><summary><h4>module warnings</h4></summary>
    <details><summary><h5>class WarningMessage(object)</h5></summary>
    <details><summary><b>def __init__(self, message, category, filename, lineno, file=None, line=None, source=None)</b></summary>
    <p>Initialize self.  See help(type(self)) for accurate signature.</p>
    </details>
    <details><summary><b>def __str__(self)</b></summary>
    <p>Return str(self).</p>
    </details>
    </details>
    <details><summary><h5>class catch_warnings(object)</h5></summary>
    <details><summary><b>def __enter__(self)</b></summary>
    </details>
    <details><summary><b>def __exit__(self, *exc_info)</b></summary>
    </details>
    <details><summary><b>def __init__(self, *, record=False, module=None, action=None, category=<class 'Warning'>, lineno=0, append=False)</b></summary>
    <p>Specify whether to record warnings and if an alternative module
should be used other than sys.modules['warnings'].

For compatibility with Python 3.0, please consider all arguments to be
keyword-only.</p>
    </details>
    <details><summary><b>def __repr__(self)</b></summary>
    <p>Return repr(self).</p>
    </details>
    </details>
  <!-- Error processing item: 'str' object has no attribute '__name__' -->
</details>
