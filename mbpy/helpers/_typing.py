from __future__ import annotations

import collections.abc
import contextlib
import copy
import errno
import functools
import itertools
import operator
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import types
import urllib.request
from collections.abc import Container, Hashable, Iterable, Mapping, MutableMapping
from pathlib import Path
from random import random
from time import sleep, time
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    Literal,
    Tuple,
    Type,
    TypeAlias,
    TypeVar,
    Union,
    overload,
)

import more_itertools
from typing_extensions import Final

from mbpy.collect import compose, wraps



class _PeekableReader:
    """lightweight stream wrapper that implements peek()."""

    def __init__(self, stream):
        self.stream = stream

    def read(self, n):
        return self.stream.read(n)

    def readline(self):
        return self.stream.readline()

    def tell(self):
        return self.stream.tell()

    def close(self):
        return self.stream.close()

    def peek(self, n):
        stream = self.stream
        try:
            if hasattr(stream, "flush"):
                stream.flush()
            position = stream.tell()
            stream.seek(position)  # assert seek() works before reading
            chunk = stream.read(n)
            stream.seek(position)
            return chunk
        except (AttributeError, OSError):
            raise NotImplementedError("stream is not peekable: %r", stream) from None


def once(func):
    """
    Decorate func so it's only ever called the first time.

    This decorator can ensure that an expensive or non-idempotent function
    will not be expensive on subsequent calls and is idempotent.

    >>> add_three = once(lambda a: a+3)
    >>> add_three(3)
    6
    >>> add_three(9)
    6
    >>> add_three('12')
    6

    To reset the stored value, simply clear the property ``saved_result``.

    >>> del add_three.saved_result
    >>> add_three(9)
    12
    >>> add_three(8)
    12

    Or invoke 'reset()' on it.

    >>> add_three.reset()
    >>> add_three(-3)
    0
    >>> add_three(0)
    0
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not hasattr(wrapper, 'saved_result'):
            wrapper.saved_result = func(*args, **kwargs)
        return wrapper.saved_result

    wrapper.reset = lambda: vars(wrapper).__delitem__('saved_result')
    return wrapper

def _make_peekable(stream):
    """Return stream as an object with a peek() method."""
    import io

    if hasattr(stream, "peek"):
        return stream
    if not (hasattr(stream, "tell") and hasattr(stream, "seek")):
        try:
            return io.BufferedReader(stream)
        except Exception:
            pass
    return _PeekableReader(stream)

def instanceproperty(fget=None, fset=None, fdel=None, doc=None, classval=None):
    """Like @property, but returns ``classval`` when used as a class attribute.

    >>> class MyClass(object):
    ...     '''The class docstring'''
    ...
    ...     @instanceproperty(classval=__doc__)
    ...     def __doc__(self):
    ...         return "An object docstring"
    ...
    ...     @instanceproperty
    ...     def val(self):
    ...         return 42
    >>> MyClass.__doc__
    'The class docstring'
    >>> MyClass.val is None
    True
    >>> obj = MyClass()
    >>> obj.__doc__
    'An object docstring'
    >>> obj.val
    42
    """
    if fget is None:
        return functools.partial(instanceproperty, fset=fset, fdel=fdel, doc=doc, classval=classval)
    return InstanceProperty(fget=fget, fset=fset, fdel=fdel, doc=doc, classval=classval)


class InstanceProperty(property):
    """Like @property, but returns ``classval`` when used as a class attribute.

    Should not be used directly.  Use ``instanceproperty`` instead.
    """

    def __init__(self, fget=None, fset=None, fdel=None, doc=None, classval=None):
        self.classval = classval
        property.__init__(self, fget=fget, fset=fset, fdel=fdel, doc=doc)

    def __get__(self, obj, type=None):
        if obj is None:
            return self.classval
        return property.__get__(self, obj, type)

    def __reduce__(self):
        state = (self.fget, self.fset, self.fdel, self.__doc__, self.classval)
        return InstanceProperty, state


class IntConversionDescriptor:
    def __init__(self, *, default):
        self._default = default

    def __set_name__(self, owner, name):
        self._name = "_" + name

    def __get__(self, obj, type):
        if obj is None:
            return Literal[self._default]

        return getattr(obj, self._name, self._default)

    @overload
    def __set__(self, obj, value: int): ...
    @overload
    def __set__(self, obj, value: str): ...
    def __set__(self, obj, value):
        if isinstance(value, str | int):
            setattr(obj, self._name, Literal[value])
        if isinstance(value, Tuple) and len(value) >= 1 and isinstance(value[0], int | str):
            setattr(obj, self._name, Literal[value[0]])
        setattr(obj, self._name, Literal[-1])


@contextlib.contextmanager
def pushd(dir: str | os.PathLike) -> Iterator[str | os.PathLike]:
    """>>> tmp_path = getfixture("tmp_path")
    >>> with pushd(tmp_path):
    ...     assert os.getcwd() == os.fspath(tmp_path)
    >>> assert os.getcwd() != os.fspath(tmp_path).
    """  # noqa: D205
    orig = os.getcwd()
    os.chdir(dir)
    try:
        yield dir
    finally:
        os.chdir(orig)


@contextlib.contextmanager
def tarball(url, target_dir: str | os.PathLike | None = None) -> Iterator[str | os.PathLike]:
    """Get a URL to a tarball, download, extract, yield, then clean up.

    Assumes everything in the tarball is prefixed with a common
    directory. That common path is stripped and the contents
    are extracted to ``target_dir``, similar to passing
    ``-C {target} --strip-components 1`` to the ``tar`` command.

    Uses the streaming protocol to extract the contents from a
    stream in a single pass without loading the whole file into
    memory.

    >>> import urllib.request
    >>> url = getfixture("tarfile_served")
    >>> target = getfixture("tmp_path") / "out"
    >>> tb = tarball(url, target_dir=target)
    >>> import pathlib
    >>> with tb as extracted:
    ...     contents = pathlib.Path(extracted, "contents.txt").read_text(encoding="utf-8")
    >>> assert not os.path.exists(extracted)

    If the target is not specified, contents are extracted to a
    directory relative to the current working directory named after
    the name of the file as extracted from the URL.

    >>> target = getfixture("tmp_path")
    >>> with pushd(target), tarball(url):
    ...     target.joinpath("served").is_dir()
    True
    """
    if target_dir is None:
        target_dir = Path(url).name.replace(".tar.gz", "").replace(".tgz", "")
    Path(target_dir).mkdir(exist_ok=True)
    try:
        req = urllib.request.urlopen(url)
        with tarfile.open(fileobj=req, mode="r|*") as tf:
            tf.extractall(path=target_dir, filter=strip_first_component)
        yield target_dir
    finally:
        shutil.rmtree(target_dir)


def strip_first_component(
    member: tarfile.TarInfo,
    path,
) -> tarfile.TarInfo:
    _, member.name = member.name.split("/", 1)
    return member


def _compose(*cmgrs):
    """Compose any number of dependent context managers into a single one.

    The last, innermost context manager may take arbitrary arguments, but
    each successive context manager should accept the result from the
    previous as a single parameter.
    Like compose
    left, so the context manager should be indicated from outermost to
    innermost.

    Example, to create a context manager to change to a temporary
    directory:

    >>> temp_dir_as_cwd = _compose(pushd, temp_dir)
    >>> with temp_dir_as_cwd() as dir:
    ...     assert os.path.samefile(os.getcwd(), dir)
    """

    def compose_two(inner, outer):
        def composed(*args, **kwargs):
            with inner(*args, **kwargs) as saved, outer(saved) as res:
                yield res

        return contextlib.contextmanager(composed)

    return functools.reduce(compose_two, reversed(cmgrs))


tarball_cwd = _compose(pushd, tarball)
"""
A tarball context with the current working directory pointing to the contents.
"""


def remove_readonly(func, path, exc_info):
    """Add support for removing read-only files on Windows."""
    _, exc, _ = exc_info
    if func in (os.rmdir, os.remove, os.unlink) and exc.errno == errno.EACCES:
        # change the file to be readable,writable,executable: 0777
        os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        # retry
        func(path)
    else:
        raise


def robust_remover():
    return (
        functools.partial(shutil.rmtree, onerror=remove_readonly) if platform.system() == "Windows" else shutil.rmtree
    )


@contextlib.contextmanager
def temp_dir(remover=shutil.rmtree):
    """Create a temporary directory context. Pass a custom remover
    to override the removal behavior.

    >>> import pathlib
    >>> with temp_dir() as the_dir:
    ...     assert os.path.isdir(the_dir)
    >>> assert not os.path.exists(the_dir)
    """  # noqa: D205
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        remover(temp_dir)


robust_temp_dir = functools.partial(temp_dir, remover=robust_remover())


@contextlib.contextmanager
def repo_context(repo: str, branch: str | None = None, quiet: bool = True, dest_ctx=robust_temp_dir):
    """Check out the repo indicated by url.

    If dest_ctx is supplied, it should be a context manager
    to yield the target directory for the check out.

    >>> repo = repo_context("https://github.com/mbodiai/mbpy")
    >>> with repo as dest:
    ...     listing = os.listdir(dest)
    >>> "README.rst" in listing
    True
    """
    exe = "git" 
    if repo.startswith("git+"):
        exe = "git"
        repo = repo[4:]
    if not repo.startswith("https://"):
        repo = f"https://github.com/{repo}"
    with dest_ctx() as repo_dir:
        cmd = [exe, "clone",repo , repo_dir]
        cmd.extend(["--branch", branch] * bool(branch))
        stream = subprocess.DEVNULL if quiet else None
        subprocess.check_call(cmd, stdout=stream, stderr=stream)
        yield repo_dir


METHOD_CACHE_INIT = functools.lru_cache(maxsize=None)
def method_cache(method, cache_wrapper=METHOD_CACHE_INIT):
    """Wrap lru_cache to support storing the cache data in the object instances.

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

    See Also:
    http://code.activestate.com/recipes/577452-a-memoize-decorator-for-instance-methods/
    for another implementation and additional justification.
    """

    def wrapper(self, *args, **kwargs):
        # it's the first call, replace the method with a cached, bound method
        bound_method = types.MethodType(method, self)
        cached_method = cache_wrapper(bound_method)
        setattr(self, method.__name__, cached_method)
        return cached_method(*args, **kwargs)

    # Support cache clear even before cache has been created.
    wrapper.cache_clear = lambda: None

    return _special_method_cache(method, cache_wrapper) or wrapper


def _special_method_cache(method, cache_wrapper):
    """Because Python treats special methods differently, it's not
    possible to use instance attributes to implement the cached
    methods.

    Instead, install the wrapper method under a different name
    and return a simple proxy to that wrapper.

    https://github.com/jaraco/jaraco.functools/issues/5
    """  # noqa: D205
    name = method.__name__
    special_names = "__getattr__", "__getitem__"

    if name not in special_names:
        return None

    wrapper_name = "__cached" + name

    def proxy(self, /, *args, **kwargs):
        if wrapper_name not in vars(self):
            bound = types.MethodType(method, self)
            cache = cache_wrapper(bound)
            setattr(self, wrapper_name, cache)
        else:
            cache = getattr(self, wrapper_name)
        return cache(*args, **kwargs)

    return proxy


class Throttler:
    """Rate-limit a function (or other callable)."""

    def __init__(self, func, max_rate=float("Inf")):
        if isinstance(func, Throttler):
            func = func.func
        self.func = func
        self.max_rate = max_rate
        self.reset()

    def reset(self):
        self.last_called = 0

    def __call__(self, *args, **kwargs):
        self._wait()
        return self.func(*args, **kwargs)

    def _wait(self):
        """Ensure at least 1/max_rate seconds from last call."""
        elapsed = time() - self.last_called
        must_wait = 1 / self.max_rate - elapsed
        sleep(max(0, must_wait))
        self.last_called = time()

    def __get__(self, obj, owner=None):
        return first_invoke(self._wait, functools.partial(self.func, obj))


def first_invoke(func1, func2):
    """Return a function that when invoked will invoke func1 without
    any parameters (for its side effect) and then invoke func2
    with whatever parameters were passed, returning its result.
    """  # noqa: D205

    def wrapper(*args, **kwargs):
        func1()
        return func2(*args, **kwargs)

    return wrapper


def apply(transform):
    """Decorate a function with a transform function that is
    invoked on results returned from the decorated function.

    >>> @apply(reversed)
    ... def get_numbers(start):
    ...     "doc for get_numbers"
    ...     return range(start, start + 3)
    >>> list(get_numbers(4))
    [6, 5, 4]
    >>> get_numbers.__doc__
    'doc for get_numbers'
    """  # noqa: D205

    def wrap(func):
        return functools.wraps(func)(compose(transform, func))

    return wrap


def result_invoke(action):
    r"""Decorate a function with an action function that is
    invoked on the results returned from the decorated
    function (for its side effect), then return the original
    result.

    >>> @result_invoke(print)
    ... def add_two(a, b):
    ...     return a + b
    >>> x = add_two(2, 3)
    5
    >>> x
    5
    """  # noqa: D205

    def wrap(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            action(result)
            return result

        return wrapper

    return wrap


def invoke(f, /, *args, **kwargs):
    """Call a function for its side effect after initialization.

    The benefit of using the decorator instead of simply invoking a function
    after defining it is that it makes explicit the author's intent for the
    function to be called immediately. Whereas if one simply calls the
    function immediately, it's less obvious if that was intentional or
    incidental. It also avoids repeating the name - the two actions, defining
    the function and calling it immediately are modeled separately, but linked
    by the decorator construct.

    The benefit of having a function construct (opposed to just invoking some
    behavior inline) is to serve as a scope in which the behavior occurs. It
    avoids polluting the global namespace with local variables, provides an
    anchor on which to attach documentation (docstring), keeps the behavior
    logically separated (instead of conceptually separated or not separated at
    all), and provides potential to re-use the behavior for testing or other
    purposes.

    This function is named as a pithy way to communicate, "call this function
    primarily for its side effect", or "while defining this function, also
    take it aside and call it". It exists because there's no Python construct
    for "define and call" (nor should there be, as decorators serve this need
    just fine). The behavior happens immediately and synchronously.

    >>> @invoke
    ... def func():
    ...     print("called")
    called
    >>> func()
    called

    Use functools.partial to pass parameters to the initial call

    >>> @functools.partial(invoke, name="bingo")
    ... def func(name):
    ...     print("called with", name)
    called with bingo
    """
    f(*args, **kwargs)
    return f



if TYPE_CHECKING:
    from _operator import _SupportsComparison

    from _typeshed import SupportsKeysAndGetItem
    from typing_extensions import Self

    _RangeMapKT = TypeVar('_RangeMapKT', bound=_SupportsComparison)
else:
    # _SupportsComparison doesn't exist at runtime,
    # but _RangeMapKT is used in RangeMap's superclass' type parameters
    _RangeMapKT = TypeVar('_RangeMapKT')

_T = TypeVar('_T')
_VT = TypeVar('_VT')

_Matchable = Union[Callable, Container, Iterable, re.Pattern]


def _dispatch(obj: _Matchable) -> Callable:
    # can't rely on singledispatch for Union[Container, Iterable]
    # due to ambiguity
    # (https://peps.python.org/pep-0443/#abstract-base-classes).
    if isinstance(obj, re.Pattern):
        return obj.fullmatch
    # mypy issue: https://github.com/python/mypy/issues/11071
    if not isinstance(obj, Callable):  # type: ignore[arg-type]
        if not isinstance(obj, Container):
            obj = set(obj)  # type: ignore[arg-type]
        obj = obj.__contains__
    return obj  # type: ignore[return-value]


class Projection(collections.abc.Mapping):
    """Project a set of keys over a mapping.

    >>> sample = {'a': 1, 'b': 2, 'c': 3}
    >>> prj = Projection(['a', 'c', 'd'], sample)
    >>> dict(prj)
    {'a': 1, 'c': 3}

    Projection also accepts an iterable or callable or pattern.

    >>> iter_prj = Projection(iter('acd'), sample)
    >>> call_prj = Projection(lambda k: ord(k) in (97, 99, 100), sample)
    >>> pat_prj = Projection(re.compile(r'[acd]'), sample)
    >>> prj == iter_prj == call_prj == pat_prj
    True

    Keys should only appear if they were specified and exist in the space.
    Order is retained.

    >>> list(prj)
    ['a', 'c']

    Attempting to access a key not in the projection
    results in a KeyError.

    >>> prj['b']
    Traceback (most recent call last):
    ...
    KeyError: 'b'

    Use the projection to update another dict.

    >>> target = {'a': 2, 'b': 2}
    >>> target.update(prj)
    >>> targ.et
    {'a': 1, 'b': 2, 'c': 3}

    Projection keeps a reference to the original dict, so
    modifying the original dict may modify the Projection.

    >>> del sample['a']
    >>> dict(prj)
    {'c': 3}
    """

    def __init__(self, keys: _Matchable, space: Mapping):
        self._match = _dispatch(keys)
        self._space = space

    def __getitem__(self, key):
        if not self._match(key):
            raise KeyError(key)
        return self._space[key]

    def _keys_resolved(self):
        return filter(self._match, self._space)

    def __iter__(self):
        return self._keys_resolved()

    def __len__(self):
        return len(tuple(self._keys_resolved()))


class Mask(Projection):
    """The inverse of a :class:`Projection`, masking out keys.

    >>> sample = {'a': 1, 'b': 2, 'c': 3}
    >>> msk = Mask(['a', 'c', 'd'], sample)
    >>> dict(msk)
    {'b': 2}
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self._match = compose(operator.not_, self._match)
        self._match = lambda key, orig=self._match: not orig(key)


def mapvalues(function, dictionary):
    """Return a new dict with function applied to values of dictionary.

    >>> dict_map(lambda x: x+1, dict(a=1, b=2))
    {'a': 2, 'b': 3}
    """
    return {key: function(value) for key, value in dictionary.items()}


class MapInputsToRanges(Dict[_RangeMapKT, _VT]):
    """A dictionary-like object that uses the keys as bounds for a range.
    Inclusion of the value for that range is determined by the
    key_match_comparator, which defaults to less-than-or-equal.
    A value is returned for a key if it is the first key that matches in
    the sorted list of keys.

    One may supply keyword parameters to be passed to the sort function used
    to sort keys (i.e. key, reverse) as sort_params.

    Create a map that maps 1-3 -> 'a', 4-6 -> 'b'

    >>> r = RangeMap({3: 'a', 6: 'b'})  # boy, that was easy
    >>> r[1], r[2], r[3], r[4], r[5], r[6]
    ('a', 'a', 'a', 'b', 'b', 'b')

    Even float values should work so long as the comparison operator
    supports it.

    >>> r[4.5]
    'b'

    Notice that the way rangemap is defined, it must be open-ended
    on one side.

    >>> r[0]
    'a'
    >>> r[-1]
    'a'

    One can close the open-end of the RangeMap by using undefined_value

    >>> r = RangeMap({0: RangeMap.undefined_value, 3: 'a', 6: 'b'})
    >>> r[0]
    Traceback (most recent call last):
    ...
    KeyError: 0

    One can get the first or last elements in the range by using RangeMap.Item

    >>> last_item = RangeMap.Item(-1)
    >>> r[last_item]
    'b'

    .last_item is a shortcut for Item(-1)

    >>> r[RangeMap.last_item]
    'b'

    Sometimes it's useful to find the bounds for a RangeMap

    >>> r.bounds()
    (0, 6)

    RangeMap supports .get(key, default)

    >>> r.get(0, 'not found')
    'not found'

    >>> r.get(7, 'not found')
    'not found'

    One often wishes to define the ranges by their left-most values,
    which requires use of sort params and a key_match_comparator.

    >>> r = RangeMap({1: 'a', 4: 'b'},
    ...     sort_params=dict(reverse=True),
    ...     key_match_comparator=operator.ge)
    >>> r[1], r[2], r[3], r[4], r[5], r[6]
    ('a', 'a', 'a', 'b', 'b', 'b')

    That wasn't nearly as easy as before, so an alternate constructor
    is provided:

    >>> r = RangeMap.left({1: 'a', 4: 'b', 7: RangeMap.undefined_value})
    >>> r[1], r[2], r[3], r[4], r[5], r[6]
    ('a', 'a', 'a', 'b', 'b', 'b')

    """  # noqa: D205

    def __init__(
        self,
        source: (
            SupportsKeysAndGetItem[_RangeMapKT, _VT] | Iterable[tuple[_RangeMapKT, _VT]]
        ),
        sort_params: Mapping[str, Any] = {},
        discriminator: Callable[[Any], Hashable] | None = None,
    ):
        dict.__init__(self, source)
        self.sort_params = sort_params
        self.match = discriminator  
    def __init__(
        self,
        source: (
            SupportsKeysAndGetItem[_RangeMapKT, _VT] | Iterable[tuple[_RangeMapKT, _VT]]
        ),
        sort_params: Mapping[str, Any] = {},
        key_match_comparator: Callable[[Any, Any], bool] = operator.le,
    ):
        dict.__init__(self, source)
        self.sort_params = sort_params
        self.match = key_match_comparator


    def __getitem__(self, item: _RangeMapKT) -> _VT:
        sorted_keys = sorted(self.keys(), **self.sort_params)
        if isinstance(item, MapInputsToRanges.Item):
            result = self.__getitem__(sorted_keys[item])
        else:
            key = self._find_first_match_(sorted_keys, item)
            result = dict.__getitem__(self, key)
            if result is MapInputsToRanges.undefined_value:
                raise KeyError(key)
        return result

    @classmethod
    def LessThan(
        cls,
        source: (
            SupportsKeysAndGetItem[_RangeMapKT, _VT] | Iterable[tuple[_RangeMapKT, _VT]]
        ),
    ) -> Self:
        return cls(source, sort_params={"reverse": True}, key_match_comparator=operator.lt)
    
    @classmethod
    def LessThanOrEqualTo(
        cls,
        source: (
            SupportsKeysAndGetItem[_RangeMapKT, _VT] | Iterable[tuple[_RangeMapKT, _VT]]
        ),
    ) -> Self:
        return cls(source, sort_params={"reverse": True}, key_match_comparator=operator.le)
    
    @classmethod
    def GreaterThan(
        cls,
        source: (
            SupportsKeysAndGetItem[_RangeMapKT, _VT] | Iterable[tuple[_RangeMapKT, _VT]]
        ),
    ) -> Self:
        return cls(source, sort_params={"reverse": True}, key_match_comparator=operator.gt)
    @classmethod
    def GreaterThanOrEqualTo(
        cls,
        source: (
            SupportsKeysAndGetItem[_RangeMapKT, _VT] | Iterable[tuple[_RangeMapKT, _VT]]
        ),
    ) -> Self:
        return cls(source, sort_params={"reverse": True}, key_match_comparator=operator.ge)
    
    @classmethod
    def By(
        cls,
        source: (
            SupportsKeysAndGetItem[_RangeMapKT, _VT] | Iterable[tuple[_RangeMapKT, _VT]]
        ),
        discriminator: Callable[[Any], Hashable],
    ) -> Self:
        return cls(source, discriminator=discriminator)
    @overload  # type: ignore[override] # Signature simplified over dict and Mapping
    def get(self, key: _RangeMapKT, default: _T) -> _VT | _T: ...
    @overload
    def get(self, key: _RangeMapKT, default: None = None) -> _VT | None: ...
    def get(self, key: _RangeMapKT, default: _T | None = None) -> _VT | _T | None:
        """Return the value for key if key is in the dictionary, else default.
        If default is not given, it defaults to None, so that this method
        never raises a KeyError.
        """  # noqa: D205
        try:
            return self[key]
        except KeyError:
            return default

    def _find_first_match_(
        self, keys: Iterable[_RangeMapKT], item: _RangeMapKT,
    ) -> _RangeMapKT:
        is_match = functools.partial(self.match, item)
        matches = filter(is_match, keys)
        try:
            return next(matches)
        except StopIteration:
            raise KeyError(item) from None

    def bounds(self) -> tuple[_RangeMapKT, _RangeMapKT]:
        sorted_keys = sorted(self.keys(), **self.sort_params)
        return (sorted_keys[MapInputsToRanges.first_item], sorted_keys[MapInputsToRanges.last_item])

    # some special values for the RangeMap
    undefined_value = type('RangeValueUndefined', (), {})()

    class Item(int):
        """RangeMap Item."""

    first_item = Item(0)
    last_item = Item(-1)


def __identity(x):
    return x


def sorted_items(d, key=__identity, reverse=False):
    """Return the items of the dictionary sorted by the keys.

    >>> sample = dict(foo=20, bar=42, baz=10)
    >>> tuple(sorted_items(sample))
    (('bar', 42), ('baz', 10), ('foo', 20))

    >>> reverse_string = lambda s: ''.join(reversed(s))
    >>> tuple(sorted_items(sample, key=reverse_string))
    (('foo', 20), ('bar', 42), ('baz', 10))

    >>> tuple(sorted_items(sample, reverse=True))
    (('foo', 20), ('baz', 10), ('bar', 42))
    """

    # wrap the key func so it operates on the first element of each item
    def pairkey_key(item):
        return key(item[0])

    return sorted(d.items(), key=pairkey_key, reverse=reverse)


class KeyTransformingDict(dict):
    """A dict subclass that transforms the keys before they're used.
    Subclasses may override the default transform_key to customize behavior.
    """  # noqa: D205

    @staticmethod
    def transform_key(key):  # pragma: nocover
        return key

    def __init__(self, *args, **kargs):
        super().__init__()
        # build a dictionary using the default constructs
        d = dict(*args, **kargs)
        # build this dictionary using transformed keys.
        for item in d.items():
            self.__setitem__(*item)

    def __setitem__(self, key, val):
        key = self.transform_key(key)
        super().__setitem__(key, val)

    def __getitem__(self, key):
        key = self.transform_key(key)
        return super().__getitem__(key)

    def __contains__(self, key):
        key = self.transform_key(key)
        return super().__contains__(key)

    def __delitem__(self, key):
        key = self.transform_key(key)
        return super().__delitem__(key)

    def get(self, key, *args, **kwargs):
        key = self.transform_key(key)
        return super().get(key, *args, **kwargs)

    def setdefault(self, key, *args, **kwargs):
        key = self.transform_key(key)
        return super().setdefault(key, *args, **kwargs)

    def pop(self, key, *args, **kwargs):
        key = self.transform_key(key)
        return super().pop(key, *args, **kwargs)

    def matching_key_for(self, key):
        """Given a key, return the actual key stored in self that matches.
        Raise KeyError if the key isn't found.
        """
        try:
            return next(e_key for e_key in self.keys() if e_key == key)
        except StopIteration as err:
            raise KeyError(key) from err


class DictAdapter:
    """Provide a getitem interface for attributes of an object.

    Let's say you want to get at the string.lowercase property in a formatted
    string. It's easy with DictAdapter.

    >>> import string
    >>> print("lowercase is %(ascii_lowercase)s" % DictAdapter(string))
    lowercase is abcdefghijklmnopqrstuvwxyz
    """

    def __init__(self, wrapped_ob):
        self.object = wrapped_ob

    def __getitem__(self, name):
        return getattr(self.object, name)


class NamespaceAdapter:
    """Mix-in class to enable a mapping object to provide items as
    attributes.

    >>> C = type('C', (dict, ItemsAsAttributes), dict())
    >>> i = C()
    >>> i['foo'] = 'bar'
    >>> i.foo
    'bar'

    Natural attribute access takes precedence

    >>> i.foo = 'henry'
    >>> i.foo
    'henry'

    But as you might expect, the mapping functionality is preserved.

    >>> i['foo']
    'bar'

    A normal attribute error should be raised if an attribute is
    requested that doesn't exist.

    >>> i.missing
    Traceback (most recent call last):
    ...
    AttributeError: 'C' object has no attribute 'missing'

    It also works on dicts that customize __getitem__

    >>> missing_func = lambda self, key: 'missing item'
    >>> C = type(
    ...     'C',
    ...     (dict, ItemsAsAttributes),
    ...     dict(__missing__ = missing_func),
    ... )
    >>> i = C()
    >>> i.missing
    'missing item'
    >>> i.foo
    'missing item'
    """  # noqa: D205

    def __getattr__(self, key):
        try:
            return getattr(super(), key)
        except AttributeError as e:
            # attempt to get the value from the mapping (return self[key])
            #  but be careful not to lose the original exception context.
            noval = object()

            def _safe_getitem(cont, key, missing_result):
                try:
                    return cont[key]
                except KeyError:
                    return missing_result

            result = _safe_getitem(self, key, noval)
            if result is not noval:
                return result
            # raise the original exception, but use the original class
            #  name, not 'super'.
            (message,) = e.args
            message = message.replace('super', self.__class__.__name__, 1)
            e.args = (message,)
            raise


def invertmap(map):
    """Given a dictionary, return another dictionary with keys and values
    switched. If any of the values resolve to the same key, raises
    a ValueError.

    >>> numbers = dict(a=1, b=2, c=3)
    >>> letters = invert_map(numbers)
    >>> letters[1]
    'a'
    >>> numbers['d'] = 3
    >>> invert_map(numbers)
    Traceback (most recent call last):
    ...
    ValueError: Key conflict in inverted mapping
    """  # noqa: D205
    res = {v: k for k, v in map.items()}
    if not len(res) == len(map):
        raise ValueError('Key conflict in inverted mapping')
    return res


class IdentityOverrideMap(dict):
    """A dictionary that by default maps each key to itself, but otherwise
    acts like a normal dictionary.

    >>> d = IdentityOverrideMap()
    >>> d[42]
    42
    >>> d['speed'] = 'speedo'
    >>> print(d['speed'])
    speedo
    """  # noqa: D205

    def __missing__(self, key):
        return key


class MapStack(list, collections.abc.MutableMapping):
    """A stack of dictionaries that behaves as a view on those dictionaries, giving preference to the last.

    >>> stack = DictStack([dict(a=1, c=2), dict(b=2, a=2)])
    >>> stack['a']
    2
    >>> stack['b']
    2
    >>> stack['c']
    2
    >>> len(stack)
    3
    >>> stack.push(dict(a=3))
    >>> stack['a']
    3
    >>> stack['a'] = 4
    >>> set(stack.keys()) == set(['a', 'b', 'c'])
    True
    >>> set(stack.items()) == set([('a', 4), ('b', 2), ('c', 2)])
    True
    >>> dict(**stack) == dict(stack) == dict(a=4, c=2, b=2)
    True
    >>> d = stack.pop()
    >>> stack['a']
    2
    >>> d = stack.pop()
    >>> stack['a']
    1
    >>> stack.get('b', None)
    >>> 'c' in stack
    True
    >>> del stack['c']
    >>> dict(stack)
    {'a': 1}
    """

    def __iter__(self):
        dicts = list.__iter__(self)
        return iter(set(itertools.chain.from_iterable(c.keys() for c in dicts)))

    def __getitem__(self, key):
        for scope in reversed(tuple(list.__iter__(self))):
            if key in scope:
                return scope[key]
        raise KeyError(key)


    def push(self, d: Dict, ctx=None,maxlen=None):
        d = d.copy()
        if ctx is not None:
            d.update(ctx if isinstance(ctx, Mapping) else {"IMPORTANT_CONTEXT": ctx})
        list.append(self, d)

    def __contains__(self, other):
        return collections.abc.Mapping.__contains__(self, other)

    def __len__(self):
        return len(list(iter(self)))

    def __setitem__(self, key, item):
        last = list.__getitem__(self, -1)
        return last.__setitem__(key, item)

    def __delitem__(self, key):
        last = list.__getitem__(self, -1)
        return last.__delitem__(key)

    # workaround for mypy confusion
    @wraps(list.pop)
    def pop(self, *args, **kwargs):
        return list.pop(self, *args, **kwargs)



class Bijection(dict):
    """A Bijective Map (two-way mapping).

    Implemented as a simple dictionary of 2x the size, mapping values back
    to keys.

    Note, this implementation may be incomplete. If there's not a test for
    your use case below, it's likely to fail, so please test and send pull
    requests or patches for additional functionality needed.


    >>> m = BijectiveMap()
    >>> m['a'] = 'b'
    >>> m == {'a': 'b', 'b': 'a'}
    True
    >>> print(m['b'])
    a

    >>> m['c'] = 'd'
    >>> len(m)
    2

    Some weird things happen if you map an item to itself or overwrite a
    single key of a pair, so it's disallowed.

    >>> m['e'] = 'e'
    Traceback (most recent call last):
    ValueError: Key cannot map to itself

    >>> m['d'] = 'e'
    Traceback (most recent call last):
    ValueError: Key/Value pairs may not overlap

    >>> m['e'] = 'd'
    Traceback (most recent call last):
    ValueError: Key/Value pairs may not overlap

    >>> print(m.pop('d'))
    c

    >>> 'c' in m
    False

    >>> m = BijectiveMap(dict(a='b'))
    >>> len(m)
    1
    >>> print(m['b'])
    a

    >>> m = BijectiveMap()
    >>> m.update(a='b')
    >>> m['b']
    'a'

    >>> del m['b']
    >>> len(m)
    0
    >>> 'a' in m
    False
    """

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.update(*args, **kwargs)

    def __setitem__(self, item, value):
        if item == value:
            raise ValueError("Key cannot map to itself")
        overlap = (
            item in self
            and self[item] != value
            or value in self
            and self[value] != item
        )
        if overlap:
            raise ValueError("Key/Value pairs may not overlap")
        super().__setitem__(item, value)
        super().__setitem__(value, item)

    def __delitem__(self, item):
        self.pop(item)

    def __len__(self):
        return super().__len__() // 2

    def pop(self, key, *args, **kwargs):
        mirror = self[key]
        super().__delitem__(mirror)
        return super().pop(key, *args, **kwargs)

    def update(self, *args, **kwargs):
        # build a dictionary using the default constructs
        d = dict(*args, **kwargs)
        # build this dictionary using transformed keys.
        for item in d.items():
            self.__setitem__(*item)


class FrozenDict(collections.abc.Mapping, collections.abc.Hashable):
    """An immutable mapping.

    >>> a = FrozenDict(a=1, b=2)
    >>> b = FrozenDict(a=1, b=2)
    >>> a == b
    True

    >>> a == dict(a=1, b=2)
    True
    >>> dict(a=1, b=2) == a
    True
    >>> 'a' in a
    True
    >>> type(hash(a)) is type(0)
    True
    >>> set(iter(a)) == {'a', 'b'}
    True
    >>> len(a)
    2
    >>> a['a'] == a.get('a') == 1
    True

    >>> a['c'] = 3
    Traceback (most recent call last):
    ...
    TypeError: 'FrozenDict' object does not support item assignment

    >>> a.update(y=3)
    Traceback (most recent call last):
    ...
    AttributeError: 'FrozenDict' object has no attribute 'update'

    Copies should compare equal

    >>> copy.copy(a) == a
    True

    Copies should be the same type

    >>> isinstance(copy.copy(a), FrozenDict)
    True

    FrozenDict supplies .copy(), even though
    collections.abc.Mapping doesn't demand it.

    >>> a.copy() == a
    True
    >>> a.copy() is not a
    True
    """

    __slots__ = ['__data']

    def __new__(cls, *args, **kwargs):
        self = super().__new__(cls)
        self.__data = dict(*args, **kwargs)
        return self

    # Container
    def __contains__(self, key):
        return key in self.__data

    # Hashable
    def __hash__(self):
        return hash(tuple(sorted(self.__data.items())))

    # Mapping
    def __iter__(self):
        return iter(self.__data)

    def __len__(self):
        return len(self.__data)

    def __getitem__(self, key):
        return self.__data[key]

    # override get for efficiency provided by dict
    def get(self, *args, **kwargs):
        return self.__data.get(*args, **kwargs)

    # override eq to recognize underlying implementation
    def __eq__(self, other):
        if isinstance(other, FrozenDict):
            other = other.__data
        return self.__data.__eq__(other)

    def copy(self):
        """Return a shallow copy of self."""
        return copy.copy(self)


class Enumerate(NamespaceAdapter, Bijection):
    """A convenient way to provide enumerated values.
    
    >>> e = Enumeration('a b c')
    >>> e['a']
    0

    >>> e.a
    0

    >>> e[1]
    'b'

    >>> set(e.names) == set('abc')
    True

    >>> set(e.codes) == set(range(3))
    True

    >>> e.get('d') is None
    True

    Codes need not start with 0

    >>> e = Enumeration('a b c', range(1, 4))
    >>> e['a']
    1

    >>> e[3]
    'c'
    """

    def __init__(self, names, codes=None):
        if isinstance(names, str):
            names = names.split()
        if codes is None:
            codes = itertools.count()
        super().__init__(zip(names, codes,strict=True))

    @property
    def names(self):
        return (key for key in self if isinstance(key, str))

    @property
    def codes(self):
        return (self[name] for name in self.names)


class Everything:
    """A collection "containing" every possible thing.

    >>> 'foo' in Everything()
    True

    >>> import random
    >>> random.randint(1, 999) in Everything()
    True

    >>> random.choice([None, 'foo', 42, ('a', 'b', 'c')]) in Everything()
    True
    """

    def __contains__(self, other):
        return True


class InstrumentedDict(collections.UserDict):
    """Instrument an existing dictionary with additional functionality.
    
    But always reference and mutate
    the original dictionary.

    >>> orig = {'a': 1, 'b': 2}
    >>> inst = InstrumentedDict(orig)
    >>> inst['a']
    1
    >>> inst['c'] = 3
    >>> orig['c']
    3
    >>> inst.keys() == orig.keys()
    True
    """

    def __init__(self, data):
        super().__init__()
        self.data = data


class Least:
    """A value that is always lesser than any other.

    >>> least = Least()
    >>> 3 < least
    False
    >>> 3 > least
    True
    >>> least < 3
    True
    >>> least <= 3
    True
    >>> least > 3
    False
    >>> 'x' > least
    True
    >>> None > least
    True
    """

    def __le__(self, other):
        return True

    __lt__ = __le__

    def __ge__(self, other):
        return False

    __gt__ = __ge__


class Greatest:
    """A value that is always greater than any other.

    >>> greatest = Greatest()
    >>> 3 < greatest
    True
    >>> 3 > greatest
    False
    >>> greatest < 3
    False
    >>> greatest > 3
    True
    >>> greatest >= 3
    True
    >>> 'x' > greatest
    False
    >>> None > greatest
    False
    """

    def __ge__(self, other):
        return True

    __gt__ = __ge__

    def __le__(self, other):
        return False

    __lt__ = __le__


def popall(items):
    """Clear items in place and return a copy of items.

    >>> items = [1, 2, 3]
    >>> popped = pop_all(items)
    >>> popped is items
    False
    >>> popped
    [1, 2, 3]
    >>> items
    []
    """
    result, items[:] = items[:], []
    return result


class FreezableDefaultDict(collections.defaultdict):
    """Often it is desirable to prevent the mutation of
    a default dict after its initial construction, such
    as to prevent mutation during iteration.

    >>> dd = FreezableDefaultDict(list)
    >>> dd[0].append('1')
    >>> dd.freeze()
    >>> dd[1]
    []
    >>> len(dd)
    1
    """  # noqa: D205

    def __missing__(self, key):
        return getattr(self, '_frozen', super().__missing__)(key)

    def freeze(self):
        self._frozen = lambda key: self.default_factory() if self.default_factory is not None else None


class Accumulator:
    def __init__(self, initial=0):
        self.val = initial

    def __call__(self, val):
        self.val += val
        return self.val


class WeightedLookup(MapInputsToRanges):
    """Given parameters suitable for a dict representing keys
    and a weighted proportion, return a RangeMap representing
    spans of values proportial to the weights:

    >>> even = WeightedLookup(a=1, b=1)

    [0, 1) -> a
    [1, 2) -> b

    >>> lk = WeightedLookup(a=1, b=2)

    [0, 1) -> a
    [1, 3) -> b

    >>> lk[.5]
    'a'
    >>> lk[1.5]
    'b'

    Adds ``.random()`` to select a random weighted value:

    >>> lk.random() in ['a', 'b']
    True

    >>> choices = [lk.random() for x in range(1000)]

    Statistically speaking, choices should be .5 a:b
    >>> ratio = choices.count('a') / choices.count('b')
    >>> .4 < ratio < .6
    True
    """  # noqa: D205, D415

    def __init__(self, *args, **kwargs):
        raw = dict(*args, **kwargs)

        # allocate keys by weight
        indexes = map(Accumulator(), raw.values())
        super().__init__(zip(indexes, raw.keys(), strict=False), key_match_comparator=operator.lt)

    def random(self):
        lower, upper = self.bounds()
        selector = random() * (upper - lower) + lower # noqa: S311
        return self[selector]
    
def caller(depth=1, default='__main__'):
    try:
        return sys._getframemodulename(depth + 1) or default
    except AttributeError:  # For platforms without _getframemodulename()
        pass
    try:
        return sys._getframe(depth + 1).f_globals.get('__name__', default)
    except (AttributeError, ValueError):  # For platforms without _getframe()
        pass
    return None


PositiveInteger: TypeAlias = Literal[
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25,
]
NegativeInteger: TypeAlias = Literal[
    -1, -2, -3, -4, -5, -6, -7, -8, -9, -10, -11, -12, -13, -14, -15, -16, -17, -18, -19, -20,
]
Countable: TypeAlias = PositiveInteger | NegativeInteger | Literal[0]  # noqa: Y026  # TODO: Use TypeAlias once mypy bugs are fixed

# This is an internal CPython type that is like, but subtly different from, a NamedTuple
# Subclasses of this type are found in multiple modules.
# In typeshed, `structseq` is only ever used as a mixin in combination with a fixed-length `Tuple`
# See discussion at #6546 & #6560
# `structseq` classes are unsubclassable, so are all decorated with `@final`.
_T_co = TypeVar('_T_co', covariant=True)
from typing import Protocol
class structseq(Protocol[_T_co]): # type: ignore  # noqa: N801
    n_fields: Final[int]
    n_unnamed_fields: Final[int]
    n_sequence_fields: Final[int]
    # The first parameter will generally only take an iterable of a specific length.
    # E.g. `os.uname_result` takes any iterable of length exactly 5.
    #
    # The second parameter will accept a dict of any kind without raising an exception,
    # but only has any meaning if you supply it a dict where the keys are strings.
    # https://github.com/python/typeshed/pull/6560#discussion_r767149830
    def __new__(cls: type[Self], sequence: Iterable[_T_co], dict: dict[str, Any] = ...) -> Self: ...
    if sys.version_info >= (3, 13):
        def __replace__(self: Self, **kwargs: Any) -> Self: ...
        


class ExceptionTrap:
    """
    A context manager that will catch certain exceptions and provide an
    indication they occurred.

    >>> with ExceptionTrap() as trap:
    ...     raise Exception()
    >>> bool(trap)
    True

    >>> with ExceptionTrap() as trap:
    ...     pass
    >>> bool(trap)
    False

    >>> with ExceptionTrap(ValueError) as trap:
    ...     raise ValueError("1 + 1 is not 3")
    >>> bool(trap)
    True
    >>> trap.value
    ValueError('1 + 1 is not 3')
    >>> trap.tb
    <traceback object at ...>

    >>> with ExceptionTrap(ValueError) as trap:
    ...     raise Exception()
    Traceback (most recent call last):
    ...
    Exception

    >>> bool(trap)
    False
    """

    exc_info = None, None, None

    def __init__(self, exceptions=(Exception,)):
        self.exceptions = exceptions

    def __enter__(self):
        return self

    @property
    def type(self):
        return self.exc_info[0]

    @property
    def value(self):
        return self.exc_info[1]

    @property
    def tb(self):
        return self.exc_info[2]

    def __exit__(self, *exc_info):
        type = exc_info[0]
        matches = type and issubclass(type, self.exceptions)
        if matches:
            self.exc_info = exc_info
        return matches

    def __bool__(self):
        return bool(self.type)

    def raises(self, func, *, _test=bool):
        """
        Wrap func and replace the result with the truth
        value of the trap (True if an exception occurred).

        First, give the decorator an alias to support Python 3.8
        Syntax.

        >>> raises = ExceptionTrap(ValueError).raises

        Now decorate a function that always fails.

        >>> @raises
        ... def fail():
        ...     raise ValueError('failed')
        >>> fail()
        True
        """

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with ExceptionTrap(self.exceptions) as trap:
                func(*args, **kwargs)
            return _test(trap)

        return wrapper

    def passes(self, func):
        """
        Wrap func and replace the result with the truth
        value of the trap (True if no exception).

        First, give the decorator an alias to support Python 3.8
        Syntax.

        >>> passes = ExceptionTrap(ValueError).passes

        Now decorate a function that always fails.

        >>> @passes
        ... def fail():
        ...     raise ValueError('failed')

        >>> fail()
        False
        """
        return self.raises(func, _test=operator.not_)


class suppress(contextlib.suppress, contextlib.ContextDecorator):
    """
    A version of contextlib.suppress with decorator support.

    >>> @suppress(KeyError)
    ... def key_error():
    ...     {}['']
    >>> key_error()
    """


class on_interrupt(contextlib.ContextDecorator):
    """
    Replace a KeyboardInterrupt with SystemExit(1).

    Useful in conjunction with console entry point functions.

    >>> def do_interrupt():
    ...     raise KeyboardInterrupt()
    >>> on_interrupt('error')(do_interrupt)()
    Traceback (most recent call last):
    ...
    SystemExit: 1
    >>> on_interrupt('error', code=255)(do_interrupt)()
    Traceback (most recent call last):
    ...
    SystemExit: 255
    >>> on_interrupt('suppress')(do_interrupt)()
    >>> with __import__('pytest').raises(KeyboardInterrupt):
    ...     on_interrupt('ignore')(do_interrupt)()
    """

    def __init__(self, action='error', /, code=1):
        self.action = action
        self.code = code

    def __enter__(self):
        return self

    def __exit__(self, exctype, excinst, exctb):
        if exctype is not KeyboardInterrupt or self.action == 'ignore':
            return
        elif self.action == 'error':
            raise SystemExit(self.code) from excinst
        return self.action == 'suppress'


def retry_call(func, cleanup=lambda: None, retries=0, trap=()):
    """
    Given a callable func, trap the indicated exceptions
    for up to 'retries' times, invoking cleanup on the
    exception. On the final attempt, allow any exceptions
    to propagate.
    """
    attempts = itertools.count() if retries == float('inf') else range(retries)
    for _ in attempts:
        try:
            return func()
        except trap:
            cleanup()

    return func()


def retry(*r_args, **r_kwargs):
    """
    Decorator wrapper for retry_call. Accepts arguments to retry_call
    except func and then returns a decorator for the decorated function.

    Ex:

    >>> @retry(retries=3)
    ... def my_func(a, b):
    ...     "this is my funk"
    ...     print(a, b)
    >>> my_func.__doc__
    'this is my funk'
    """

    def decorate(func):
        @functools.wraps(func)
        def wrapper(*f_args, **f_kwargs):
            bound = functools.partial(func, *f_args, **f_kwargs)
            return retry_call(bound, *r_args, **r_kwargs)

        return wrapper

    return decorate


def print_yielded(func):
    """
    Convert a generator into a function that prints all yielded elements.

    >>> @print_yielded
    ... def x():
    ...     yield 3; yield None
    >>> x()
    3
    None
    """
    print_all = functools.partial(map, print)
    print_results = compose(more_itertools.consume, print_all, func)
    return functools.wraps(func)(print_results)


def passnone(func):
    """Wrap func so it's not called if its first param is None.

    >>> print_text = pass_none(print)
    >>> print_text('text')
    text
    >>> print_text(None)
    """

    @functools.wraps(func)
    def wrapper(param, /, *args, **kwargs):
        if param is not None:
            return func(param, *args, **kwargs)
        return None

    return wrapper



def chain(method: Callable[[_T, Any | Type[Any]], None]) -> Callable[[_T, Any | Type[Any]], _T]:
    """Wrap None-returning method to return self for chaining.


    >>> class Dingus:
    ...     @chainable
    ...     def set_attr(self, name, val):
    ...         setattr(self, name, val)
    >>> d = Dingus().set_attr('a', 'eh!')
    >>> d.a
    'eh!'
    >>> d2 = Dingus().set_attr('a', 'eh!').set_attr('b', 'bee!')
    >>> d2.a + d2.b
    'eh!bee!'

    Enforces that the return value is null.

    >>> class BorkedDingus:
    ...     @chainable
    ...     def set_attr(self, name, val):
    ...         setattr(self, name, val)
    ...         return len(name)
    >>> BorkedDingus().set_attr('a', 'eh!')
    Traceback (most recent call last):
    ...
    AssertionError
    """

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        assert method(self, *args, **kwargs) is None
        return self

    return wrapper
