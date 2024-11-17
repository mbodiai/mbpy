import functools
import inspect
import operator
import os
import re
import select as _select
import sys
import traceback
from bisect import bisect
from collections import defaultdict, deque, namedtuple
from collections.abc import (
    Callable,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    Set,
)
from contextlib import contextmanager
from functools import partial
from inspect import CO_VARARGS, CO_VARKEYWORDS, Signature, signature, unwrap  # reexport this for backwards compat
from itertools import (
    accumulate,
    chain,
    groupby,
    islice,
    tee,
)
from itertools import (
    dropwhile as _dropwhile,
)
from itertools import (
    takewhile as _takewhile,
)
from pathlib import Path
from timeit import default_timer as timer
from types import FunctionType, MethodType, NoneType, SimpleNamespace
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    ParamSpec,
    Self,
    Tuple,
    Type,
    TypeVar,
    Union,
    Unpack,
    cast,
    overload,
)

from more_itertools import locate as mlocate
from more_itertools import replace as mreplace
from more_itertools import seekable as mseekable
from more_itertools import spy as mspy

if TYPE_CHECKING:
    from mbpy.utils.proto_utils import SupportsIter, SupportsKeysItems
else:
    SupportsIter = SupportsKeysItems = Any

mods = {"decorator", "wraps", "unwrap", "ContextDecorator", "contextmanager"}


mods |= {
    "isa",
    "is_mapping",
    "is_set",
    "is_seq",
    "is_list",
    "is_tuple",
    "is_seqcoll",
    "is_seqcont",
    "iterable",
    "is_iter",
}

_T = TypeVar("_T")
_T_co = TypeVar("_T_co", covariant=True)
_S = TypeVar("_S")
_PWrapped = ParamSpec("_PWrapped")
_RWrapped = TypeVar("_RWrapped")
_PWrapper = ParamSpec("_PWrapper")
_RWrapper = TypeVar("_RWrapper")
if sys.version_info >= (3, 12):
    WRAPPER_ASSIGNMENTS: tuple[
        Literal["__module__"],
        Literal["__name__"],
        Literal["__qualname__"],
        Literal["__doc__"],
        Literal["__annotations__"],
        Literal["__type_params__"],
    ]
else:
    WRAPPER_ASSIGNMENTS: tuple[
        Literal["__module__"],
        Literal["__name__"],
        Literal["__qualname__"],
        Literal["__doc__"],
        Literal["__annotations__"],
    ]
WRAPPER_UPDATES: tuple[Literal["__dict__"]]


class Wrapped(Generic[_PWrapped, _RWrapped, _PWrapper, _RWrapper]):
    __wrapped__: Callable[_PWrapped, _RWrapped]

    def __call__(self, *args: _PWrapper.args, **kwargs: _PWrapper.kwargs) -> _RWrapper: ...

    # as with ``Callable``, we'll assume that these attributes exist
    __name__: str
    __qualname__: str


class Wrapper(Generic[_PWrapped, _RWrapped]):
    def __call__(self, f: Callable[_PWrapper, _RWrapper]) -> Wrapped[_PWrapped, _RWrapped, _PWrapper, _RWrapper]: ...


try:
    InterruptedError
except NameError:
    # Alias Python2 exception to Python3
    InterruptedError = _select.error

if sys.version_info[0] >= 3:
    string_types = (str,)
else:
    string_types = (unicode, str)

if sys.version_info >= (3, 12):

    def update_wrapper(
        wrapper: Callable[_PWrapper, _RWrapper],
        wrapped: Callable[_PWrapped, _RWrapped],
        assigned: Sequence[str] = (
            "__module__",
            "__name__",
            "__qualname__",
            "__doc__",
            "__annotations__",
            "__type_params__",
        ),
        updated: Sequence[str] = ("__dict__",),
    ) -> Wrapped[_PWrapped, _RWrapped, _PWrapper, _RWrapper]: ...
    def wraps(
        wrapped: Callable[_PWrapped, _RWrapped],
        assigned: Sequence[str] = (
            "__module__",
            "__name__",
            "__qualname__",
            "__doc__",
            "__annotations__",
            "__type_params__",
        ),
        updated: Sequence[str] = ("__dict__",),
    ) -> Wrapper[_PWrapped, _RWrapped]: ...
    wraps = functools.wraps
else:

    def update_wrapper(
        wrapper: Callable[_PWrapper, _RWrapper],
        wrapped: Callable[_PWrapped, _RWrapped],
        assigned: Sequence[str] = ("__module__", "__name__", "__qualname__", "__doc__", "__annotations__"),
        updated: Sequence[str] = ("__dict__",),
    ) -> Wrapped[_PWrapped, _RWrapped, _PWrapper, _RWrapper]: ...
    def wraps(
        wrapped: Callable[_PWrapped, _RWrapped],
        assigned: Sequence[str] = ("__module__", "__name__", "__qualname__", "__doc__", "__annotations__"),
        updated: Sequence[str] = ("__dict__",),
    ) -> Wrapper[_PWrapped, _RWrapped]:
        return cast(Wrapper[_PWrapped,_RWrapped],functools.wraps(wrapped, assigned=assigned, updated=updated))  # noqa: F821



class namespace(SimpleNamespace):  # noqa
    def __getitem__(self, key):
        if not key.startswith("__"):
            return getattr(self, key)
        raise KeyError(key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __call__(self, *args, **kwargs):
        return self

    def __init__(self, **kwargs: SupportsKeysItems | Dict[str, Any]):
        super().__init__(**kwargs)
class SkipMemory(Exception):
    pass


# TODO: use pos-only arg once in Python 3.8+ only
def memoize(_func=None, *, key_func=None):
    """@memoize(key_func=None). Makes decorated function memoize its results.

    If key_func is specified uses key_func(*func_args, **func_kwargs) as memory key.
    Otherwise uses args + tuple(sorted(kwargs.items()))

    Exposes its memory via .memory attribute.
    """
    if _func is not None:
        return memoize()(_func)
    return _memory_decorator({}, key_func)


memoize.skip = SkipMemory


def cache(timeout, *, key_func=None):
    """Caches a function results for timeout seconds."""
    if isinstance(timeout, timedelta):
        timeout = timeout.total_seconds()

    return _memory_decorator(CacheMemory(timeout), key_func)


cache.skip = SkipMemory


def _memory_decorator(memory, key_func):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # We inline this here since @memoize also targets microoptimizations
            key = key_func(*args, **kwargs) if key_func else args + tuple(sorted(kwargs.items())) if kwargs else args
            try:
                return memory[key]
            except KeyError:
                try:
                    value = memory[key] = func(*args, **kwargs)
                    return value
                except SkipMemory as e:
                    return e.args[0] if e.args else None

        def invalidate(*args, **kwargs):
            key = key_func(*args, **kwargs) if key_func else args + tuple(sorted(kwargs.items())) if kwargs else args
            memory.pop(key, None)

        wrapper.invalidate = invalidate

        def invalidate_all():
            memory.clear()

        wrapper.invalidate_all = invalidate_all

        wrapper.memory = memory
        return wrapper

    return decorator


class CacheMemory(dict):
    def __init__(self, timeout):
        self.timeout = timeout
        self.clear()

    def __setitem__(self, key, value):
        expires_at = time.time() + self.timeout
        dict.__setitem__(self, key, (value, expires_at))
        self._keys.append(key)
        self._expires.append(expires_at)

    def __getitem__(self, key):
        value, expires_at = dict.__getitem__(self, key)
        if expires_at <= time.time():
            self.expire()
            raise KeyError(key)
        return value

    def expire(self):
        i = bisect(self._expires, time.time())
        for _ in range(i):
            self._expires.popleft()
            self.pop(self._keys.popleft(), None)

    def clear(self):
        dict.clear(self)
        self._keys = deque()
        self._expires = deque()


def _make_lookuper(silent):
    def make_lookuper(func):
        """
        Creates a single argument function looking up result in a memory.

        Decorated function is called once on first lookup and should return all available
        arg-value pairs.

        Resulting function will raise LookupError when using @make_lookuper
        or simply return None when using @silent_lookuper.
        """
        has_args, has_keys = has_arg_types(func)
        assert not has_keys, "Lookup table building function should not have keyword arguments"

        if has_args:

            @memoize
            def wrapper(*args):
                f = lambda: func(*args)
                f.__name__ = "%s(%s)" % (func.__name__, ", ".join(map(str, args)))
                return make_lookuper(f)
        else:
            memory = {}

            def wrapper(arg):
                if not memory:
                    memory[object()] = None  # prevent continuos memory refilling
                    memory.update(func())

                if silent:
                    return memory.get(arg)
                elif arg in memory:
                    return memory[arg]
                else:
                    raise LookupError("Failed to look up %s(%s)" % (func.__name__, arg))

        return wraps(func)(wrapper)

    return make_lookuper


make_lookuper = _make_lookuper(False)
silent_lookuper = _make_lookuper(True)
silent_lookuper.__name__ = "silent_lookuper"


def has_arg_types(func):
    params = inspect.signature(func).parameters.values()
    return any(p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.VAR_POSITIONAL) for p in params), any(
        p.kind in (p.KEYWORD_ONLY, p.VAR_KEYWORD) for p in params
    )



### Add __original__ to update_wrapper and @wraps


def update_wrapper(wrapper, wrapped, assigned=functools.WRAPPER_ASSIGNMENTS, updated=functools.WRAPPER_UPDATES):
    functools.update_wrapper(wrapper, wrapped, assigned, updated)

    # Set an original ref for faster and more convenient access
    wrapper.__original__ = getattr(wrapped, "__original__", None) or unwrap(wrapped)

    return wrapper


update_wrapper.__doc__ = functools.update_wrapper.__doc__


def wraps(wrapped, assigned=functools.WRAPPER_ASSIGNMENTS, updated=functools.WRAPPER_UPDATES):
    return functools.partial(update_wrapper, wrapped=wrapped, assigned=assigned, updated=updated)


wraps.__doc__ = functools.wraps.__doc__





def isa(*types: Unpack[Tuple[Type]]) -> Callable[[Any], bool]:
    """Creates a function checking if its argument is of any of given types."""
    return lambda x: isinstance(x, types)


is_mapping = isa(Mapping)
is_set = isa(Set)
is_seq = isa(Sequence)
is_list = isa(list)
is_tuple = isa(tuple)

is_seqcoll = isa(list, tuple)
is_seqcont = isa(list, tuple, Iterator, range)

iterable = isa(Iterable)
is_iter = isa(Iterator)


__all__ = ["tree_leaves", "ltree_leaves", "tree_nodes", "ltree_nodes"]


def tree_leaves(root: Iterable[Any], follow=is_seqcont, children=iter):
    """Iterates over tree leaves."""
    q = deque([[root]])
    while q:
        node_iter = iter(q.pop())
        for sub in node_iter:
            if follow(sub):
                q.append(node_iter)
                q.append(children(sub))
                break
            else:
                yield sub


def ltree_leaves(root, follow=is_seqcont, children=iter):
    """Lists tree leaves."""
    return list(tree_leaves(root, follow, children))


def tree_nodes(root, follow=is_seqcont, children=iter):
    """Iterates over all tree nodes."""
    q = deque([[root]])
    while q:
        node_iter = iter(q.pop())
        for sub in node_iter:
            yield sub
            if follow(sub):
                q.append(node_iter)
                q.append(children(sub))
                break


def make_decorator(deco, dargs=(), dkwargs={}):
    @wraps(deco)
    def _decorator(func):
        def wrapper(*args, **kwargs):
            call = Call(func, args, kwargs)
            return deco(call, *dargs, **dkwargs)

        return wraps(func)(wrapper)

    # NOTE: should I update name to show args?
    # Save these for introspection
    _decorator._func, _decorator._args, _decorator._kwargs = deco, dargs, dkwargs
    return _decorator


class Call(object):
    """A call object to pass as first argument to decorator.

    Call object is just a proxy for decorated function
    with call arguments saved in its attributes.
    """

    def __init__(self, func, args, kwargs):
        self._func, self._args, self._kwargs = func, args, kwargs

    def __call__(self, *a, **kw):
        if not a and not kw:
            return self._func(*self._args, **self._kwargs)
        else:
            return self._func(*(self._args + a), **dict(self._kwargs, **kw))

    def __getattr__(self, name):
        try:
            res = self.__dict__[name] = arggetter(self._func)(name, self._args, self._kwargs)
            return res
        except TypeError as e:
            raise AttributeError(*e.args)

    def __str__(self):
        func = getattr(self._func, "__qualname__", str(self._func))
        args = ", ".join(list(map(str, self._args)) + ["%s=%s" % t for t in self._kwargs.items()])
        return "%s(%s)" % (func, args)

    def __repr__(self):
        return "<Call %s>" % self


def has_single_arg(func: Callable):
    sig = inspect.signature(func)
    if len(sig.parameters) != 1:
        return False
    arg = next(iter(sig.parameters.values()))
    return arg.kind not in (arg.VAR_POSITIONAL, arg.VAR_KEYWORD)


def has_1pos_and_kwonly(func):
    from collections import Counter
    from inspect import Parameter as P

    sig = inspect.signature(func)
    kinds = Counter(p.kind for p in sig.parameters.values())
    return kinds[P.POSITIONAL_ONLY] + kinds[P.POSITIONAL_OR_KEYWORD] == 1 and kinds[P.VAR_POSITIONAL] == 0


def get_argnames(func: FunctionType):
    func = getattr(func, "__original__", None) or unwrap(func)
    return func.__code__.co_varnames[: func.__code__.co_argcount]


MethodAttrCache = Dict[str, Callable[[Any], Any] | FunctionType | MethodType | Wrapped | property]


def arggetter(func, _cache: MethodAttrCache = {}):
    if func in _cache:
        return _cache[func]

    original = getattr(func, "__original__", None) or unwrap(func)
    code = original.__code__

    # Instrospect pos and kw names
    posnames = code.co_varnames[: code.co_argcount]
    n = code.co_argcount
    kwonlynames = code.co_varnames[n : n + code.co_kwonlyargcount]
    n += code.co_kwonlyargcount
    # TODO: remove this check once we drop Python 3.7
    if hasattr(code, "co_posonlyargcount"):
        kwnames = posnames[code.co_posonlyargcount :] + kwonlynames
    else:
        kwnames = posnames + kwonlynames

    varposname = varkwname = None
    if code.co_flags & inspect.CO_VARARGS:
        varposname = code.co_varnames[n]
        n += 1
    if code.co_flags & inspect.CO_VARKEYWORDS:
        varkwname = code.co_varnames[n]

    allnames = set(code.co_varnames)
    indexes = {name: i for i, name in enumerate(posnames)}
    defaults = {}
    if original.__defaults__:
        defaults.update(zip(posnames[-len(original.__defaults__) :], original.__defaults__))
    if original.__kwdefaults__:
        defaults.update(original.__kwdefaults__)

    def get_arg(name, args, kwargs):
        if name not in allnames:
            raise TypeError("%s() doesn't have argument named %s" % (func.__name__, name))

        index = indexes.get(name)
        if index is not None and index < len(args):
            return args[index]
        elif name in kwargs and name in kwnames:
            return kwargs[name]
        elif name == varposname:
            return args[len(posnames) :]
        elif name == varkwname:
            return omit(kwargs, kwnames)
        elif name in defaults:
            return defaults[name]
        else:
            raise TypeError("%s() missing required argument: '%s'" % (func.__name__, name))

    _cache[func] = get_arg
    return get_arg


mods |= {"isnone", "notnone", "inc", "dec", "even", "odd"}
CallableT = TypeVar("CallableT", bound=Callable)


def decorator(deco: CallableT) -> CallableT:
    """Transforms a flat wrapper into decorator.

    Example:
        @decorator
        def func(call, methods, content_type=DEFAULT):  # These are decorator params
            # Access call arg by name
            if call.request.method not in methods:
                # ...
            # Decorated functions and all the arguments are accesible as:
            print(call._func, call_args, call._kwargs)
            # Finally make a call:
            return call()
    """
    if has_single_arg(deco):
        return make_decorator(deco)
    if has_1pos_and_kwonly(deco):
        # Any arguments after first become decorator arguments
        # And a decorator with arguments is essentially a decorator fab
        # TODO: use pos-only arg once in Python 3.8+ only
        def decorator_fab(_func=None, **dkwargs):
            if _func is not None:
                return make_decorator(deco, (), dkwargs)(_func)
            return make_decorator(deco, (), dkwargs)
    else:

        def decorator_fab(*dargs, **dkwargs):
            return make_decorator(deco, dargs, dkwargs)

    return wraps(deco)(decorator_fab)


mods |= {
    "count",
    "cycle",
    "repeat",
    "repeatedly",
    "iterate",
    "take",
    "drop",
    "first",
    "second",
    "nth",
    "last",
    "rest",
    "butlast",
    "ilen",
    "map",
    "filter",
    "lmap",
    "lfilter",
    "remove",
    "lremove",
    "keep",
    "lkeep",
    "without",
    "lwithout",
    "concat",
    "lconcat",
    "chain",
    "cat",
    "lcat",
    "flatten",
    "lflatten",
    "mapcat",
    "lmapcat",
    "interleave",
    "interpose",
    "distinct",
    "ldistinct",
    "dropwhile",
    "takewhile",
    "split",
    "lsplit",
    "split_at",
    "lsplit_at",
    "split_by",
    "lsplit_by",
    "group_by",
    "group_by_keys",
    "group_values",
    "count_by",
    "count_reps",
    "partition",
    "lpartition",
    "chunks",
    "lchunks",
    "partition_by",
    "lpartition_by",
    "with_prev",
    "with_next",
    "pairwise",
    "lzip",
    "reductions",
    "lreductions",
    "sums",
    "lsums",
    "accumulate",
}

_map, _filter = map, filter


def _lmap(f, *seqs):
    return list(map(f, *seqs))


def _lfilter(f, seq):
    return list(filter(f, seq))


# Re-export
from itertools import count, cycle, repeat

EMPTY = object()


def repeatedly(f, n=EMPTY):
    """Takes a function of no args, presumably with side effects,
    and returns an infinite (or length n) iterator of calls to it."""
    _repeat = repeat(None) if n is EMPTY else repeat(None, n)
    return (f() for _ in _repeat)


def iterate(f, x):
    """Returns an infinite iterator of `x, f(x), f(f(x)), ...`"""
    while True:
        yield x
        x = f(x)


def take(n, seq):
    """Returns a list of first n items in the sequence,
    or all items if there are fewer than n."""
    return list(islice(seq, n))


def drop(n, seq):
    """Skips first n items in the sequence, yields the rest."""
    return islice(seq, n, None)


def first(seq):
    """Returns the first item in the sequence.
    Returns None if the sequence is empty."""
    return next(iter(seq), None)


def second(seq):
    """Returns second item in the sequence.
    Returns None if there are less than two items in it."""
    return first(rest(seq))


def nth(n, seq):
    """Returns nth item in the sequence or None if no such item exists."""
    try:
        return seq[n]
    except IndexError:
        return None
    except TypeError:
        return next(islice(seq, n, None), None)


def last(seq):
    """Returns the last item in the sequence or iterator.
    Returns None if the sequence is empty."""
    try:
        return seq[-1]
    except IndexError:
        return None
    except TypeError:
        item = None
        for item in seq:
            pass
        return item


def rest(seq):
    """Skips first item in the sequence, yields the rest."""
    return drop(1, seq)


def butlast(seq):
    """Iterates over all elements of the sequence but last."""
    it = iter(seq)
    try:
        prev = next(it)
    except StopIteration:
        pass
    else:
        for item in it:
            yield prev
            prev = item




# TODO: tree-seq equivalent


def lmap(f, *seqs):
    """An extended version of builtin map() returning a list.
    Derives a mapper from string, int, slice, dict or set."""
    return _lmap(make_func(f), *seqs)


def lfilter(pred, seq):
    """An extended version of builtin filter() returning a list.
    Derives a predicate from string, int, slice, dict or set."""
    return _lfilter(make_pred(pred), seq)


def map(f, *seqs):
    """An extended version of builtin map().
    Derives a mapper from string, int, slice, dict or set."""
    return _map(make_func(f), *seqs)


def filter(pred, seq):
    """An extended version of builtin filter().
    Derives a predicate from string, int, slice, dict or set."""
    return _filter(make_pred(pred), seq)


def lremove(pred, seq):
    """Creates a list if items passing given predicate."""
    return list(remove(pred, seq))


def remove(pred, seq):
    """Iterates items passing given predicate."""
    return filterfalse( seq,make_pred(pred))


def lkeep(f, seq=EMPTY):
    """Maps seq with f and keeps only truthy results.
    Simply lists truthy values in one argument version."""
    return list(keep(f, seq))


def keep(f, seq=EMPTY):
    """Maps seq with f and iterates truthy results.
    Simply iterates truthy values in one argument version."""
    if seq is EMPTY:
        return _filter(bool, f)
    else:
        return _filter(bool, map(f, seq))


def without(seq, *items):
    """Iterates over sequence skipping items."""
    for value in seq:
        if value not in items:
            yield value


def lwithout(seq, *items):
    """Removes items from sequence, preserves order."""
    return list(without(seq, *items))


def lconcat(*seqs):
    """Concatenates several sequences."""
    return list(chain(*seqs))


concat = chain


def lcat(seqs):
    """Concatenates the sequence of sequences."""
    return list(cat(seqs))


cat = chain.from_iterable


def flatten(seq, follow=is_seqcont):
    """Flattens arbitrary nested sequence.
    Unpacks an item if follow(item) is truthy."""
    for item in seq:
        if follow(item):
            yield from flatten(item, follow)
        else:
            yield item


def lflatten(seq, follow=is_seqcont):
    """Iterates over arbitrary nested sequence.
    Dives into when follow(item) is truthy."""
    return list(flatten(seq, follow))


def lmapcat(f, *seqs):
    """Maps given sequence(s) and concatenates the results."""
    return lcat(map(f, *seqs))


def mapcat(f, *seqs):
    """Maps given sequence(s) and chains the results."""
    return cat(map(f, *seqs))


def interleave(*seqs):
    """Yields first item of each sequence, then second one and so on."""
    return cat(zip(*seqs))


def interpose(sep, seq):
    """Yields items of the sequence alternating with sep."""
    return drop(1, interleave(repeat(sep), seq))


def takewhile(pred, seq=EMPTY):
    """Yields sequence items until first predicate fail.
    Stops on first falsy value in one argument version."""
    if seq is EMPTY:
        pred, seq = bool, pred
    else:
        pred = make_pred(pred)
    return _takewhile(pred, seq)


def dropwhile(pred, seq=EMPTY):
    """Skips the start of the sequence passing pred (or just truthy),
    then iterates over the rest."""
    if seq is EMPTY:
        pred, seq = bool, pred
    else:
        pred = make_pred(pred)
    return _dropwhile(pred, seq)


def ldistinct(seq, key=EMPTY):
    """Removes duplicates from sequences, preserves order."""
    return list(distinct(seq, key))


def distinct(seq, key=EMPTY):
    """Iterates over sequence skipping duplicates"""
    seen = set()
    # check if key is supplied out of loop for efficiency
    if key is EMPTY:
        for item in seq:
            if item not in seen:
                seen.add(item)
                yield item
    else:
        key = make_func(key)
        for item in seq:
            k = key(item)
            if k not in seen:
                seen.add(k)
                yield item


def split(pred, seq):
    """Lazily splits items which pass the predicate from the ones that don't.
    Returns a pair (passed, failed) of respective iterators."""
    pred = make_pred(pred)
    yes, no = deque(), deque()
    splitter = (yes.append(item) if pred(item) else no.append(item) for item in seq)

    def _split(q):
        while True:
            while q:
                yield q.popleft()
            try:
                next(splitter)
            except StopIteration:
                return

    return _split(yes), _split(no)


def lsplit(pred, seq):
    """Splits items which pass the predicate from the ones that don't.
    Returns a pair (passed, failed) of respective lists."""
    pred = make_pred(pred)
    yes, no = [], []
    for item in seq:
        if pred(item):
            yes.append(item)
        else:
            no.append(item)
    return yes, no


def split_at(n, seq):
    """Lazily splits the sequence at given position,
    returning a pair of iterators over its start and tail."""
    a, b = tee(seq)
    return islice(a, n), islice(b, n, None)


def lsplit_at(n, seq):
    """Splits the sequence at given position,
    returning a tuple of its start and tail."""
    a, b = split_at(n, seq)
    return list(a), list(b)


def split_by(pred, seq):
    """Lazily splits the start of the sequence,
    consisting of items passing pred, from the rest of it."""
    a, b = tee(seq)
    return takewhile(pred, a), dropwhile(pred, b)


def lsplit_by(pred, seq):
    """Splits the start of the sequence,
    consisting of items passing pred, from the rest of it."""
    a, b = split_by(pred, seq)
    return list(a), list(b)


def group_by(f, seq):
    """Groups given sequence items into a mapping f(item) -> [item, ...]."""
    f = make_func(f)
    result = defaultdict(list)
    for item in seq:
        result[f(item)].append(item)
    return result


def group_by_keys(get_keys, seq):
    """Groups items having multiple keys into a mapping key -> [item, ...].
    Item might be repeated under several keys."""
    get_keys = make_func(get_keys)
    result = defaultdict(list)
    for item in seq:
        for k in get_keys(item):
            result[k].append(item)
    return result


def group_values(seq):
    """Takes a sequence of (key, value) pairs and groups values by keys."""
    result = defaultdict(list)
    for key, value in seq:
        result[key].append(value)
    return result


def count_by(f, seq):
    """Counts numbers of occurrences of values of f()
    on elements of given sequence."""
    f = make_func(f)
    result = defaultdict(int)
    for item in seq:
        result[f(item)] += 1
    return result


def count_reps(seq):
    """Counts number occurrences of each value in the sequence."""
    result = defaultdict(int)
    for item in seq:
        result[item] += 1
    return result


# For efficiency we use separate implementation for cutting sequences (those capable of slicing)
def _cut_seq(drop_tail, n, step, seq):
    limit = len(seq) - n + 1 if drop_tail else len(seq)
    return (seq[i : i + n] for i in range(0, limit, step))


def _cut_iter(drop_tail, n, step, seq):
    it = iter(seq)
    pool = take(n, it)
    while True:
        if len(pool) < n:
            break
        yield pool
        pool = pool[step:]
        pool.extend(islice(it, step))
    if not drop_tail:
        for item in _cut_seq(drop_tail, n, step, pool):
            yield item


def _cut(drop_tail, n, step, seq=EMPTY):
    if seq is EMPTY:
        step, seq = n, step
    if isinstance(seq, Sequence):
        return _cut_seq(drop_tail, n, step, seq)
    else:
        return _cut_iter(drop_tail, n, step, seq)


def partition(n, step, seq=EMPTY):
    """Lazily partitions seq into parts of length n.
    Skips step items between parts if passed. Non-fitting tail is ignored."""
    return _cut(True, n, step, seq)


def lpartition(n, step, seq=EMPTY):
    """Partitions seq into parts of length n.
    Skips step items between parts if passed. Non-fitting tail is ignored."""
    return list(partition(n, step, seq))


def chunks(n, step, seq=EMPTY):
    """Lazily chunks seq into parts of length n or less.
    Skips step items between parts if passed."""
    return _cut(False, n, step, seq)


def lchunks(n, step, seq=EMPTY):
    """Chunks seq into parts of length n or less.
    Skips step items between parts if passed."""
    return list(chunks(n, step, seq))


def partition_by(f, seq):
    """Lazily partition seq into continuous chunks with constant value of f."""
    f = make_func(f)
    for _, items in groupby(seq, f):
        yield items


def lpartition_by(f, seq):
    """Partition seq into continuous chunks with constant value of f."""
    return _lmap(list, partition_by(f, seq))


def with_prev(seq, fill=None):
    """Yields each item paired with its preceding: (item, prev)."""
    a, b = tee(seq)
    return zip(a, chain([fill], b))


def with_next(seq, fill=None):
    """Yields each item paired with its following: (item, next)."""
    a, b = tee(seq)
    next(b, None)
    return zip(a, chain(b, [fill]))


# An itertools recipe
# NOTE: this is the same as ipartition(2, 1, seq) only faster and with distinct name
def pairwise(seq):
    """Yields all pairs of neighboring items in seq."""
    a, b = tee(seq)
    next(b, None)
    return zip(a, b)


if sys.version_info >= (3, 10):

    def lzip(*seqs, strict=False):
        """List zip() version."""
        return list(zip(*seqs, strict=strict))
else:

    def lzip(*seqs, strict=False):
        """List zip() version."""
        if strict and len(seqs) > 1:
            return list(_zip_strict(*seqs))
        return list(zip(*seqs))

    def _zip_strict(*seqs):
        try:
            # Try compare lens if they are available and use a fast zip() builtin
            len_1 = len(seqs[0])
            for i, s in enumerate(seqs, start=1):
                len_i = len(s)
                if len_i != len_1:
                    short_i, long_i = (1, i) if len_1 < len_i else (i, 1)
                    raise _zip_strict_error(short_i, long_i)
        except TypeError:
            return _zip_strict_iters(*seqs)
        else:
            return zip(*seqs)

    def _zip_strict_iters(*seqs):
        iters = [iter(s) for s in seqs]
        while True:
            values, stop_i, val_i = [], 0, 0
            for i, it in enumerate(iters, start=1):
                try:
                    values.append(next(it))
                    if not val_i:
                        val_i = i
                except StopIteration:
                    if not stop_i:
                        stop_i = i

            if stop_i:
                if val_i:
                    raise _zip_strict_error(stop_i, val_i)
                break
            yield tuple(values)

    def _zip_strict_error(short_i, long_i):
        if short_i == 1:
            return ValueError("zip() argument %d is longer than argument 1" % long_i)
        else:
            start = "argument 1" if short_i == 2 else "argument 1-%d" % (short_i - 1)
            return ValueError("zip() argument %d is shorter than %s" % (short_i, start))


def _reductions(f, seq, acc):
    last = acc
    for x in seq:
        last = f(last, x)
        yield last


def reductions(f, seq, acc=EMPTY):
    """Yields intermediate reductions of seq by f."""
    if acc is EMPTY:
        return accumulate(seq) if f is operator.add else accumulate(seq, f)
    return _reductions(f, seq, acc)


def lreductions(f, seq, acc=EMPTY):
    """Lists intermediate reductions of seq by f."""
    return list(reductions(f, seq, acc))


def sums(seq, acc=EMPTY):
    """Yields partial sums of seq."""
    return reductions(operator.add, seq, acc)


def lsums(seq, acc=EMPTY):
    """Lists partial sums of seq."""
    return lreductions(operator.add, seq, acc)


"""Bisection algorithms."""


def insort_right(a, x, lo=0, hi=None, *, key=None):
    """Insert item x in list a, and keep it sorted assuming a is sorted.

    If x is already in a, insert it to the right of the rightmost x.

    Optional args lo (default 0) and hi (default len(a)) bound the
    slice of a to be searched.

    A custom key function can be supplied to customize the sort order.
    """
    if key is None:
        lo = bisect_right(a, x, lo, hi)
    else:
        lo = bisect_right(a, key(x), lo, hi, key=key)
    a.insert(lo, x)


def bisect_right(a, x, lo=0, hi=None, *, key=None):
    """Return the index where to insert item x in list a, assuming a is sorted.

    The return value i is such that all e in a[:i] have e <= x, and all e in
    a[i:] have e > x.  So if x already appears in the list, a.insert(i, x) will
    insert just after the rightmost x already there.

    Optional args lo (default 0) and hi (default len(a)) bound the
    slice of a to be searched.

    A custom key function can be supplied to customize the sort order.
    """

    if lo < 0:
        raise ValueError("lo must be non-negative")
    if hi is None:
        hi = len(a)
    # Note, the comparison uses "<" to match the
    # __lt__() logic in list.sort() and in heapq.
    if key is None:
        while lo < hi:
            mid = (lo + hi) // 2
            if x < a[mid]:
                hi = mid
            else:
                lo = mid + 1
    else:
        while lo < hi:
            mid = (lo + hi) // 2
            if x < key(a[mid]):
                hi = mid
            else:
                lo = mid + 1
    return lo


def insort_left(a, x, lo=0, hi=None, *, key=None):
    """Insert item x in list a, and keep it sorted assuming a is sorted.

    If x is already in a, insert it to the left of the leftmost x.

    Optional args lo (default 0) and hi (default len(a)) bound the
    slice of a to be searched.

    A custom key function can be supplied to customize the sort order.
    """

    if key is None:
        lo = bisect_left(a, x, lo, hi)
    else:
        lo = bisect_left(a, key(x), lo, hi, key=key)
    a.insert(lo, x)


def bisect_left(a, x, lo=0, hi=None, *, key=None):
    """Return the index where to insert item x in list a, assuming a is sorted.

    The return value i is such that all e in a[:i] have e < x, and all e in
    a[i:] have e >= x.  So if x already appears in the list, a.insert(i, x) will
    insert just before the leftmost x already there.

    Optional args lo (default 0) and hi (default len(a)) bound the
    slice of a to be searched.

    A custom key function can be supplied to customize the sort order.
    """

    if lo < 0:
        raise ValueError("lo must be non-negative")
    if hi is None:
        hi = len(a)
    # Note, the comparison uses "<" to match the
    # __lt__() logic in list.sort() and in heapq.
    if key is None:
        while lo < hi:
            mid = (lo + hi) // 2
            if a[mid] < x:
                lo = mid + 1
            else:
                hi = mid
    else:
        while lo < hi:
            mid = (lo + hi) // 2
            if key(a[mid]) < x:
                lo = mid + 1
            else:
                hi = mid
    return lo


mods |= {"make_func", "make_pred"}


def make_func(f, test=False):
    if callable(f):
        return f
    elif f is None:
        # pass None to builtin as predicate or mapping function for speed
        return bool if test else lambda x: x
    elif isinstance(f, (bytes, str, _re_type)):
        return re_tester(f) if test else re_finder(f)
    elif isinstance(f, (int, slice)):
        return itemgetter(f)
    elif isinstance(f, Mapping):
        return f.__getitem__
    elif isinstance(f, Set):
        return f.__contains__
    else:
        raise TypeError("Can't make a func from %s" % f.__class__.__name__)


def make_pred(pred):
    return make_func(pred, test=True)




mods |= {"re_iter", "re_all", "re_find", "re_test", "re_finder", "re_tester"}


def _make_getter(regex):
    if regex.groups == 0:
        return methodcaller("group")
    elif regex.groups == 1 and regex.groupindex == {}:
        return methodcaller("group", 1)
    elif regex.groupindex == {}:
        return methodcaller("groups")
    elif regex.groups == len(regex.groupindex):
        return methodcaller("groupdict")
    else:
        return lambda m: m


_re_type = type(re.compile(r""))  # re.Pattern was added in Python 3.7


def _prepare(regex, flags):
    if not isinstance(regex, _re_type):
        regex = re.compile(regex, flags)
    return regex, _make_getter(regex)


def re_iter(regex, s, flags=0):
    """Iterates over matches of regex in s, presents them in simplest possible form"""
    regex, getter = _prepare(regex, flags)
    return map(getter, regex.finditer(s))


def re_all(regex, s, flags=0):
    """Lists all matches of regex in s, presents them in simplest possible form"""
    return list(re_iter(regex, s, flags))


def re_find(regex, s, flags=0):
    """Matches regex against the given string,
    returns the match in the simplest possible form."""
    return re_finder(regex, flags)(s)


def re_test(regex, s, flags=0):
    """Tests whether regex matches against s."""
    return re_tester(regex, flags)(s)


def re_finder(regex, flags=0):
    """Creates a function finding regex in passed string."""
    regex, _getter = _prepare(regex, flags)
    getter = lambda m: _getter(m) if m else None
    return lambda s: getter(regex.search(s))


def re_tester(regex, flags=0):
    """Creates a predicate testing passed string with regex."""
    if not isinstance(regex, _re_type):
        regex = re.compile(regex, flags)
    return lambda s: bool(regex.search(s))


def str_join(sep, seq=EMPTY):
    """Joins the given sequence with sep.
    Forces stringification of seq items."""
    if seq is EMPTY:
        return str_join("", sep)
    else:
        return sep.join(map(sep.__class__, seq))


def cut_prefix(s, prefix):
    """Cuts prefix from given string if it's present."""
    return s[len(prefix) :] if s.startswith(prefix) else s


def cut_suffix(s, suffix):
    """Cuts suffix from given string if it's present."""
    return s[: -len(suffix)] if s.endswith(suffix) else s



mods |= {"threaded", "threaded_iter", "threaded_map", "threaded_starmap", "threaded_filter", "threaded_lfilter"}

### Error handling utilities


def raiser(exception_or_class=Exception, *args, **kwargs):
    """Constructs function that raises the given exception
    with given arguments on any invocation."""
    if isinstance(exception_or_class, str):
        exception_or_class = Exception(exception_or_class)

    def _raiser(*a, **kw):
        if args or kwargs:
            raise exception_or_class(*args, **kwargs)
        else:
            raise exception_or_class

    return _raiser


# Not using @decorator here for speed,
# since @ignore and @silent should be used for very simple and fast functions
def ignore(errors, default=None):
    """Alters function to ignore given errors, returning default instead."""
    errors = _ensure_exceptable(errors)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except errors:
                return default

        return wrapper

    return decorator


def silent(func):
    """Alters function to ignore all exceptions."""
    return ignore(Exception)(func)


### Backport of Python 3.7 nullcontext
try:
    from contextlib import nullcontext
except ImportError:

    class nullcontext(object):
        """Context manager that does no additional processing.

        Used as a stand-in for a normal context manager, when a particular
        block of code is only sometimes used with a normal context manager:

        cm = optional_cm if condition else nullcontext()
        with cm:
            # Perform operation, using optional_cm if condition is True
        """

        def __init__(self, enter_result=None):
            self.enter_result = enter_result

        def __enter__(self):
            return self.enter_result

        def __exit__(self, *excinfo):
            pass


@contextmanager
def reraise(errors, into):
    """Reraises errors as other exception."""
    errors = _ensure_exceptable(errors)
    try:
        yield
    except errors as e:
        if callable(into) and not _is_exception_type(into):
            into = into(e)
        raise into from e


@decorator
def retry(call, tries, errors=Exception, timeout=0, filter_errors=None):
    """Makes decorated function retry up to tries times.
    Retries only on specified errors.
    Sleeps timeout or timeout(attempt) seconds between tries."""
    errors = _ensure_exceptable(errors)
    for attempt in range(tries):
        try:
            return call()
        except errors as e:
            if not (filter_errors is None or filter_errors(e)):
                raise

            # Reraise error on last attempt
            if attempt + 1 == tries:
                raise
            else:
                timeout_value = timeout(attempt) if callable(timeout) else timeout
                if timeout_value > 0:
                    time.sleep(timeout_value)


def fallback(*approaches):
    """Tries several approaches until one works.
    Each approach has a form of (callable, expected_errors)."""
    for approach in approaches:
        func, catch = (approach, Exception) if callable(approach) else approach
        catch = _ensure_exceptable(catch)
        try:
            return func()
        except catch:
            pass


def _ensure_exceptable(errors):
    """Ensures that errors are passable to except clause.
    I.e. should be BaseException subclass or a tuple."""
    return errors if _is_exception_type(errors) else tuple(errors)


def _is_exception_type(value):
    return isinstance(value, type) and issubclass(value, BaseException)


class ErrorRateExceeded(Exception):
    pass


def limit_error_rate(fails, timeout, exception=ErrorRateExceeded):
    """If function fails to complete fails times in a row,
    calls to it will be intercepted for timeout with exception raised instead."""
    if isinstance(timeout, int):
        timeout = timedelta(seconds=timeout)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if wrapper.blocked:
                if datetime.now() - wrapper.blocked < timeout:
                    raise exception
                else:
                    wrapper.blocked = None

            try:
                result = func(*args, **kwargs)
            except:  # noqa
                wrapper.fails += 1
                if wrapper.fails >= fails:
                    wrapper.blocked = datetime.now()
                raise
            else:
                wrapper.fails = 0
                return result

        wrapper.fails = 0
        wrapper.blocked = None
        return wrapper

    return decorator


def throttle(period):
    """Allows only one run in a period, the rest is skipped"""
    if isinstance(period, timedelta):
        period = period.total_seconds()

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            if wrapper.blocked_until and wrapper.blocked_until > now:
                return
            wrapper.blocked_until = now + period

            return func(*args, **kwargs)

        wrapper.blocked_until = None
        return wrapper

    return decorator


### Post processing decorators


@decorator
def post_processing(call, func):
    """Post processes decorated function result with func."""
    return func(call())


collecting = post_processing(list)
collecting.__name__ = "collecting"
collecting.__doc__ = "Transforms a generator into list returning function."


@decorator
def joining(call, sep):
    """Joins decorated function results with sep."""
    return sep.join(map(sep.__class__, call()))


from inspect import isclass, ismodule


__all__ += ["cached_property", "cached_readonly", "wrap_prop", "monkey", "LazyObject"]


class cached_property(object):
    """
    Decorator that converts a method with a single self argument into
    a property cached on the instance.
    """

    # NOTE: implementation borrowed from Django.
    # NOTE: we use fget, fset and fdel attributes to mimic @property.
    fset = fdel = None

    def __init__(self, fget):
        self.fget = fget
        self.__doc__ = getattr(fget, "__doc__")

    def __get__(self, instance, type=None):
        if instance is None:
            return self
        res = instance.__dict__[self.fget.__name__] = self.fget(instance)
        return res


class cached_readonly(cached_property):
    """Same as @cached_property, but protected against rewrites."""

    def __set__(self, instance, value):
        raise AttributeError("property is read-only")


def wrap_prop(ctx):
    """Wrap a property accessors with a context manager"""

    def decorator(prop):
        class WrapperProp(object):
            def __repr__(self):
                return repr(prop)

            def __get__(self, instance, type=None):
                if instance is None:
                    return self

                with ctx:
                    return prop.__get__(instance, type)

            if hasattr(prop, "__set__"):

                def __set__(self, name, value):
                    with ctx:
                        return prop.__set__(name, value)

            if hasattr(prop, "__del__"):

                def __del__(self, name):
                    with ctx:
                        return prop.__del__(name)

        return WrapperProp()

    return decorator


def monkey(cls, name=None):
    """
    Monkey patches class or module by adding to it decorated function.

    Anything overwritten could be accessed via .original attribute of decorated object.
    """
    assert isclass(cls) or ismodule(cls), "Attempting to monkey patch non-class and non-module"

    def decorator(value):
        func = getattr(value, "fget", value)  # Support properties
        func_name = name or cut_prefix(func.__name__, "%s__" % cls.__name__)

        func.__name__ = func_name
        func.original = getattr(cls, func_name, None)

        setattr(cls, func_name, value)
        return value

    return decorator


mods |= {
    "empty",
    "iteritems",
    "itervalues",
    "join",
    "merge",
    "join_with",
    "merge_with",
    "walk",
    "walk_keys",
    "walk_values",
    "select",
    "select_keys",
    "select_values",
    "compact",
    "is_distinct",
    "all",
    "any",
    "none",
    "one",
    "some",
    "zipdict",
    "flip",
    "project",
    "omit",
    "zip_values",
    "zip_dicts",
    "where",
    "pluck",
    "pluck_attr",
    "invoke",
    "lwhere",
    "lpluck",
    "lpluck_attr",
    "linvoke",
    "get_in",
    "get_lax",
    "set_in",
    "update_in",
    "del_in",
    "has_path",
}


class EmptyType:
    def __repr__(self):
        return "EMPTY"


EMPTY = EmptyType()  # Used as unique default for optional arguments
P = ParamSpec("P")
class Predicate(Generic[P,_T]):
    def __init__(self, fn: Callable[P,_T]):
        self.fn = fn
        
    def __call__(self, *args: P.args, **kwargs: P.kwargs):
        return self.fn(*args,**kwargs)
    
    def __mul__(self, other: Callable | Self) -> "Callable":
        self.fn = compose(self.fn, other)
        return self
    def __rmul__(self, other: Callable | Self) -> "Callable":
        self.fn = compose(other, self.fn)
        return self
    def __imul__(self, other: Callable | Self) -> "Callable":
        self.fn = compose(self.fn, other)
        return self

    
    

def _filterfalse(iterable: Iterable[_T], predicate=None) -> Iterable[_T]:
    if predicate is None:
        predicate = bool
    return (item for item in iterable if not predicate(item))


def _equals(value):
    return lambda x: x == value


def _nonzero(d):
    return {k: v for k, v in d.items() if v}


def _notequals(value):
    return lambda x: x != value

def _isnone(x):
    return x is None


def _notnone(x):
    return x is not None


def _inc(x):
    return x + 1


def _dec(x):
    return x - 1


def _even(x):
    return x % 2 == 0


def _odd(x):
    return x % 2 == 1

filterfalse = Predicate(_filterfalse)
equals = Predicate(_equals)
nonzero = Predicate(_nonzero)
notequals = Predicate(_notequals)
isnone = Predicate(_isnone)
notnone = Predicate(_notnone)
inc = Predicate(_inc)
dec = Predicate(_dec)
even = Predicate(_even)
odd = Predicate(_odd)



def seekable(iterable: Iterable[_T]) -> Iterable[_T]:
    iterable = mseekable(iterable)
    iterable.seek(0)
    return iterable


def exists(key: str) -> Callable[[str], bool]:
    return lambda e: e is not None and key in e

@overload
def removenone(d: Mapping) -> Mapping:...
@overload
def removenone(d: Iterable) -> Iterable:...
def removenone(d: Iterable | Mapping) -> Iterable | Mapping:
    d = d.items() if isinstance(d, Mapping) else d
    outtype = dict if isinstance(d, Mapping) else identity
    yield from outtype(e for e in d if e is not None)


def ilen(iterable, consume=True):
    def _ilen(seq):
        """Consumes an iterable not reading it into memory
        and returns the number of items."""
        # NOTE: implementation borrowed from http://stackoverflow.com/a/15112059/753382
        counter = count()
        deque(zip(seq, counter), maxlen=0)  # (consume at C speed)
        return next(counter)

    if consume:
        return _ilen(iterable)
    copy, iterable = mspy(iterable, _ilen(seekable(iterable)))
    return _ilen(iterable)


def spy(iterable, length: int | None = None) -> Tuple[List[_T], Iterable[_T]]:
    return mspy(iterable, ilen(iterable, consume=False) if length is None else length)


def locate(iterable, pred, window: int | None = None, consume=True):
    if window is not None and window < 1:
        raise ValueError("window size must be at least 1")
    if not consume:
        iterable, copy = spy(iterable)
        return mlocate(copy, pred, window)
    return mlocate(iterable, pred, window)


def replace(iterable, pred, sub, window: int = 1):
    """Replace or append if not found.

    Return seekable iterable.
    """
    sub = (sub,) if not isinstance(sub, tuple) else sub

    copy, iterable = spy(iterable)
    window_size = (window,) if window > -1 else ()
    if ilen(locate(*(copy, pred, *window_size), consume=False)) > 0:
        return spy(list(mreplace(copy, pred, sub, *window_size)))[0]
    return spy(list(chain(copy, sub)))[0]


### Generic ops
FACTORY_REPLACE = {
    type(object.__dict__): dict,
    type({}.keys()): list,
    type({}.values()): list,
    type({}.items()): list,
}


def _factory(coll: Iterable[_T] | Iterator[_T], mapper: Mapping | None = None):
    coll_type = type(coll)
    # Hack for defaultdicts overridden constructor
    if isinstance(coll, defaultdict):
        item_factory = (
            compose(mapper, coll.default_factory) if mapper and coll.default_factory else coll.default_factory
        )
        return partial(defaultdict, cast(Callable, item_factory))
    if isinstance(coll, Iterator):
        return iter
    if isinstance(coll, bytes | str):
        return coll_type().join
    if coll_type in FACTORY_REPLACE:
        return FACTORY_REPLACE[coll_type]

    return cast(Callable[...,Iterable | Iterator],coll_type)


def empty(coll: Iterable[_T] | Iterator[_T]):
    """Creates an empty collection of the same type."""
    if isinstance(coll, SupportsIter):
        return iter([])
    return _factory(coll)() # type: ignore

def iterkeys(coll: SupportsKeysItems):
    return coll.keys() if hasattr(coll, "keys") else coll

def iteritems(coll: SupportsKeysItems):
    return coll.items() if hasattr(coll, "items") else coll


def itervalues(coll: SupportsKeysItems):
    return coll.values() if hasattr(coll, "values") else coll


iteritems.__doc__ = "Yields (key, value) pairs of the given collection."
itervalues.__doc__ = "Yields values of the given collection."
iterkeys.__doc__ = "Yields keys of the given collection."

def join(colls):
    """Joins several collections of same type into one."""
    colls, colls_copy = tee(colls)
    it = iter(colls_copy)
    try:
        dest = next(it)
    except StopIteration:
        return None
    cls = dest.__class__

    if isinstance(dest, (bytes, str)):
        return "".join(colls)
    elif isinstance(dest, Mapping):
        result = dest.copy()
        for d in it:
            result.update(d)
        return result
    elif isinstance(dest, Set):
        return dest.union(*it)
    elif isinstance(dest, (Iterator, range)):
        return chain.from_iterable(colls)
    elif isinstance(dest, Iterable):
        # NOTE: this could be reduce(concat, ...),
        #       more effective for low count
        return cls(chain.from_iterable(colls))
    else:
        raise TypeError("Don't know how to join %s" % cls.__name__)


def merge(*colls):
    """Merges several collections of same type into one.

    Works with dicts, sets, lists, tuples, iterators and strings.
    For dicts later values take precedence.
    """
    return join(colls)


def join_with(f, dicts, strict=False):
    """Joins several dicts, combining values with given function."""
    dicts = list(dicts)
    if not dicts:
        return {}
    elif not strict and len(dicts) == 1:
        return dicts[0]

    lists = {}
    for c in dicts:
        for k, v in iteritems(c):
            if k in lists:
                lists[k].append(v)
            else:
                lists[k] = [v]

    if f is not list:
        # kind of walk_values() inplace
        for k, v in iteritems(lists):
            lists[k] = f(v)

    return lists


def merge_with(f, *dicts):
    """Merges several dicts, combining values with given function."""
    return join_with(f, dicts)


def walk(f, coll):
    """Walks the collection transforming its elements with f.
    Same as map, but preserves coll type.
    """
    return _factory(coll)(xmap(f, iteritems(coll)))


def walk_keys(f, coll):
    """Walks keys of the collection, mapping them with f."""
    f = make_func(f)

    # NOTE: we use this awkward construct instead of lambda to be Python 3 compatible
    def pair_f(pair):
        k, v = pair
        return f(k), v

    return walk(pair_f, coll)


def walk_values(f, coll):
    """Walks values of the collection, mapping them with f."""
    f = make_func(f)

    # NOTE: we use this awkward construct instead of lambda to be Python 3 compatible
    def pair_f(pair):
        k, v = pair
        return k, f(v)

    return _factory(coll, mapper=f)(xmap(pair_f, iteritems(coll)))


def prewalk(f, coll):
    """Walks the collection transforming its elements with f.
    Same as map, but preserves coll type.
    """
    return _factory(coll)(xmap(f, coll))


def select(pred, coll):
    """Same as filter but preserves coll type."""
    return _factory(coll)(xfilter(pred, iteritems(coll)))


def select_keys(pred, coll):
    """Select part of the collection with keys passing pred."""
    pred = make_pred(pred)
    return select(lambda pair: pred(pair[0]), coll)


def select_values(pred, coll):
    """Select part of the collection with values passing pred."""
    pred = make_pred(pred)
    return select(lambda pair: pred(pair[1]), coll)


def compact(coll):
    """Removes falsy values from the collection."""
    if isinstance(coll, Mapping):
        return select_values(bool, coll)
    else:
        return select(bool, coll)


### Content tests


def is_distinct(coll, key=EMPTY):
    """Checks if all elements in the collection are different."""
    if key is EMPTY:
        return len(coll) == len(set(coll))
    else:
        return len(coll) == len(set(xmap(key, coll)))


def all(pred, seq=EMPTY):
    """Checks if all items in seq pass pred (or are truthy)."""
    if seq is EMPTY:
        return _all(pred)
    return _all(xmap(pred, seq))


def any(pred, seq=EMPTY):
    """Checks if any item in seq passes pred (or is truthy)."""
    if seq is EMPTY:
        return _any(pred)
    return _any(xmap(pred, seq))


def none(pred, seq=EMPTY):
    """ "Checks if none of the items in seq pass pred (or are truthy)."""
    return not any(pred, seq)


def one(pred, seq=EMPTY):
    """Checks whether exactly one item in seq passes pred (or is truthy)."""
    if seq is EMPTY:
        return one(bool, pred)
    return len(take(2, xfilter(pred, seq))) == 1


# Not same as in clojure! returns value found not pred(value)
def some(pred, seq=EMPTY):
    """Finds first item in seq passing pred or first that is truthy."""
    if seq is EMPTY:
        return some(bool, pred)
    return next(xfilter(pred, seq), None)


# TODO: a variant of some that returns mapped value,
#       one can use some(map(f, seq)) or first(keep(f, seq)) for now.

# TODO: vector comparison tests - ascending, descending and such
# def chain_test(compare, seq):
#     return all(compare, zip(seq, rest(seq))


def zipdict(keys, vals):
    """Creates a dict with keys mapped to the corresponding vals."""
    return dict(zip(keys, vals, strict=False))


def flip(mapping):
    """Flip passed dict or collection of pairs swapping its keys and values."""

    def flip_pair(pair):
        k, v = pair
        return v, k

    return walk(flip_pair, mapping)


def project(mapping, keys):
    """Leaves only given keys in mapping."""
    return _factory(mapping)((k, mapping[k]) for k in keys if k in mapping)


def omit(mapping, keys):
    """Removes given keys from mapping."""
    return _factory(mapping)((k, v) for k, v in iteritems(mapping) if k not in keys)


def zip_values(*dicts):
    """Yields tuples of corresponding values of several dicts."""
    if len(dicts) < 1:
        raise TypeError("zip_values expects at least one argument")
    keys = set.intersection(*map(set, dicts))
    for key in keys:
        yield tuple(d[key] for d in dicts)


def zip_dicts(*dicts):
    """Yields tuples like (key, (val1, val2, ...))
    for each common key in all given dicts."""
    if len(dicts) < 1:
        raise TypeError("zip_dicts expects at least one argument")
    keys = set.intersection(*map(set, dicts))
    for key in keys:
        yield key, tuple(d[key] for d in dicts)


def getin(coll: SupportsKeysItems, path: Iterable[str] | str, default=None, delimeter="."):
    """Returns a value at path in the given nested collection."""
    return setdefault(coll, path.split(delimeter)[:-1], default, delimeter).get(path.split(delimeter)[-1], default)


def setdefault(coll: SupportsKeysItems, key: str | Iterable[str], default=None, delimeter="."):
    if isinstance(key, str):
        path = key.split(delimeter)
    d = coll if hasattr(coll, "setdefault") else defaultdict(d)
    for key in path:
        d = d.setdefault(key, {})
    coll.update(d) if coll is not d else {}
    return coll


def getlax(coll, path, default=None):
    """Returns a value at path in the given nested collection.
    Does not raise on a wrong collection type along the way, but removes default.
    """  # noqa: D205
    for key in path:
        try:
            coll = coll[key]
        except (KeyError, IndexError, TypeError):
            return default
    return coll


def updatein(coll, path, update, default=None):
    """Creates a copy of coll with a value updated at path."""
    if not path:
        return update(coll)
    if isinstance(coll, list):
        copy = coll[:]
        # NOTE: there is no auto-vivication for lists
        copy[path[0]] = updatein(copy[path[0]], path[1:], update, default)
        return copy

    copy = coll.copy()
    current_default = {} if len(path) > 1 else default
    copy[path[0]] = updatein(copy.get(path[0], current_default), path[1:], update, default)
    return copy


def delin(coll, path):
    """Creates a copy of coll with a nested key or index deleted."""
    if not path:
        return coll
    try:
        next_coll = coll[path[0]]
    except (KeyError, IndexError):
        return coll

    coll_copy = copy(coll)
    if len(path) == 1:
        del coll_copy[path[0]]
    else:
        coll_copy[path[0]] = delin(next_coll, path[1:])
    return coll_copy


def haspath(coll, path):
    """Checks if path exists in the given nested collection."""
    for p in path:
        try:
            coll = coll[p]
        except (KeyError, IndexError):
            return False
    return True


def lwhere(mappings, **cond):
    """Selects mappings containing all pairs in cond."""
    return list(where(mappings, **cond))


def lpluck(key, mappings):
    """Lists values for key in each mapping."""
    return list(pluck(key, mappings))


def lpluck_attr(attr, objects):
    """Lists values of given attribute of each object."""
    return list(pluck_attr(attr, objects))


def linvoke(objects, name, *args, **kwargs):
    """Makes a list of results of the obj.name(*args, **kwargs)
    for each object in objects.
    """  # noqa: D205
    return list(invoke(objects, name, *args, **kwargs))


# Iterator versions for python 3 interface


def where(mappings, **cond):
    """Iterates over mappings containing all pairs in cond."""
    items = cond.items()
    match = lambda m: all(k in m and m[k] == v for k, v in items)
    return filter(match, mappings)


def pluck(key, mappings):
    """Iterates over values for key in mappings."""
    return map(itemgetter(key), mappings)


def pluckattr(attr, objects):
    """Iterates over values of given attribute of given objects."""
    return map(attrgetter(attr), objects)


def invoke(objects, name, *args, **kwargs):
    """Yields results of the obj.name(*args, **kwargs)
    for each object in objects.
    """  # noqa: D205
    return map(methodcaller(name, *args, **kwargs), objects)


mods |= {
    "log_calls",
    "log_enters",
    "log_exits",
    "print_calls",
    "print_enters",
    "print_exits",
    "log_errors",
    "print_errors",
}

REPR_LEN = 25


def tap(x, label=None):
    """Prints x and then returns it."""
    if label:
        print(f"{label}: {x}")
    else:
        print(x)
    return x


@decorator
def log_calls(call, print_func, errors=True, stack=True, repr_len=REPR_LEN):
    """Logs or prints all function calls.

    Includes call signature, arguments and return value, and errors.
    """
    signature = signature_repr(call, repr_len)
    try:
        print_func(f"Call {signature}")
        result = call()
        # NOTE: using full repr of result
        print_func(f"-> {smart_repr(result, max_len=None)} from {signature}")
        return result
    except BaseException as e:
        if errors:
            print_func("-> " + _format_error(signature, e, stack))
        raise


def print_calls(errors=True, stack=True, repr_len=REPR_LEN):
    if callable(errors):
        return log_calls(print)(errors)

    return log_calls(print, errors, stack, repr_len)


print_calls.__doc__ = log_calls.__doc__


@decorator
def log_enters(call, print_func, repr_len=REPR_LEN):
    """Logs each entrance to a function."""
    print_func(f"Call {signature_repr(call, repr_len)}")
    return call()


def print_enters(repr_len=REPR_LEN):
    """Prints on each entrance to a function."""
    if callable(repr_len):
        return log_enters(print)(repr_len)

    return log_enters(print, repr_len)


@decorator
def logexits(call, print_func, errors=True, stack=True, repr_len=REPR_LEN):
    """Logs exits from a function."""
    signature = signature_repr(call, repr_len)
    try:
        result = call()
        # NOTE: using full repr of result
        print_func(f"-> {smart_repr(result, max_len=None)} from {signature}")
        return result
    except BaseException as e:
        if errors:
            print_func("-> " + _format_error(signature, e, stack))
        raise


def print_exits(errors=True, stack=True, repr_len=REPR_LEN):
    """Prints on exits from a function."""
    if callable(errors):
        return logexits(print)(errors)

    return logexits(print, errors, stack, repr_len)


class LabeledContextDecorator(object):
    """A context manager which also works as decorator, passing call signature as its label."""

    def __init__(self, print_func, label=None, repr_len=REPR_LEN):
        self.print_func = print_func
        self.label = label
        self.repr_len = repr_len

    def __call__(self, label=None, **kwargs):
        if callable(label):
            return self.decorator(label)

        return self.__class__(self.print_func, label, **kwargs)

    def decorator(self, func):
        @wraps(func)
        def inner(*args, **kwargs):
            # Recreate self with a new label so that nested and recursive calls will work
            cm = self.__class__.__new__(self.__class__)
            cm.__dict__.update(self.__dict__)
            cm.label = signature_repr(Call(func, args, kwargs), self.repr_len)
            with cm:
                return func(*args, **kwargs)

        return inner


class logerrors(LabeledContextDecorator):
    """Logs or prints all errors within a function or block."""

    def __init__(self, print_func, label=None, stack=True, repr_len=REPR_LEN):
        LabeledContextDecorator.__init__(self, print_func, label=label, repr_len=repr_len)
        self.stack = stack

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if exc_type:
            if self.stack:
                exc_message = "".join(traceback.format_exception(exc_type, exc_value, tb))
            else:
                exc_message = f"{exc_type.__name__}: {exc_value}"
            self.print_func(_format_error(self.label, exc_message, self.stack))


print_errors = logerrors(print)


# Duration utils


def format_time(sec):
    if sec < 1e-6:
        return "%8.2f ns" % (sec * 1e9)
    if sec < 1e-3:
        return "%8.2f mks" % (sec * 1e6)
    if sec < 1:
        return "%8.2f ms" % (sec * 1e3)

    return f"{sec:8.2f} s"


time_formatters = {
    "auto": format_time,
    "ns": lambda sec: "%8.2f ns" % (sec * 1e9),
    "mks": lambda sec: "%8.2f mks" % (sec * 1e6),
    "ms": lambda sec: "%8.2f ms" % (sec * 1e3),
    "s": lambda sec: f"{sec:8.2f} s",
}


class log_durations(LabeledContextDecorator):
    """Times each function call or block execution."""

    def __init__(self, print_func, label=None, unit="auto", threshold=-1, repr_len=REPR_LEN):
        LabeledContextDecorator.__init__(self, print_func, label=label, repr_len=repr_len)
        if unit not in time_formatters:
            raise ValueError("Unknown time unit: %s. It should be ns, mks, ms, s or auto." % unit)
        self.format_time = time_formatters[unit]
        self.threshold = threshold

    def __enter__(self):
        self.start = timer()
        return self

    def __exit__(self, *exc):
        duration = timer() - self.start
        if duration >= self.threshold:
            duration_str = self.format_time(duration)
            self.print_func("%s in %s" % (duration_str, self.label) if self.label else duration_str)


print_durations = log_durations(print)


def log_iter_durations(seq, print_func, label=None, unit="auto"):
    """Times processing of each item in seq."""
    if unit not in time_formatters:
        raise ValueError(f"Unknown time unit: {unit}. It should be ns, mks, ms, s or auto.")
    _format_time = time_formatters[unit]
    suffix = f" of {label}" if label else ""
    it = iter(seq)
    for i, item in enumerate(it):
        start = timer()
        yield item
        duration = _format_time(timer() - start)
        print_func("%s in iteration %d%s" % (duration, i, suffix))


def print_iter_durations(seq, label=None, unit="auto"):
    """Times processing of each item in seq."""
    return log_iter_durations(seq, print, label, unit=unit)


### Formatting utils


def _format_error(label, e, stack=True):
    e_message = (traceback.format_exc() if stack else f"{e.__class__.__name__}: {e}") if isinstance(e, Exception) else e

    if label:
        template = "%s    raised in %s" if stack else "%s raised in %s"
        return template % (e_message, label)

    return e_message


### Call signature stringification utils


def signature_repr(call, repr_len=REPR_LEN):
    if isinstance(call._func, partial):
        if hasattr(call._func.func, "__name__"):
            name = "<%s partial>" % call._func.func.__name__
        else:
            name = "<unknown partial>"
    else:
        name = getattr(call._func, "__name__", "<unknown>")
    args_repr = (smart_repr(arg, repr_len) for arg in call._args)
    kwargs_repr = ("%s=%s" % (key, smart_repr(value, repr_len)) for key, value in call._kwargs.items())
    return "%s(%s)" % (name, ", ".join(chain(args_repr, kwargs_repr)))


def smart_repr(value, max_len=REPR_LEN):
    res = repr(value) if isinstance(value, bytes | str) else str(value)

    res = re.sub(r"\s+", " ", res)
    if max_len and len(res) > max_len:
        res = res[: max_len - 3] + "..."
    return res


class LazyObject(object):
    """
    A simplistic lazy init object.
    Rewrites itself when any attribute is accessed.
    """

    # NOTE: we can add lots of magic methods here to intercept on more events,
    #       this is postponed. As well as metaclass to support isinstance() check.
    def __init__(self, init):
        self.__dict__["_init"] = init

    def _setup(self):
        obj = self._init()
        object.__setattr__(self, "__class__", obj.__class__)
        object.__setattr__(self, "__dict__", obj.__dict__)

    def __getattr__(self, name):
        self._setup()
        return getattr(self, name)

    def __setattr__(self, name, value):
        self._setup()
        return setattr(self, name, value)


### Initialization helpers


def once_per(*argnames):
    """Call function only once for every combination of the given arguments."""

    def once(func):
        lock = threading.Lock()
        done_set = set()
        done_list = list()

        get_arg = arggetter(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                values = tuple(get_arg(name, args, kwargs) for name in argnames)
                if isinstance(values, Hashable):
                    done, add = done_set, done_set.add
                else:
                    done, add = done_list, done_list.append

                if values not in done:
                    add(values)
                    return func(*args, **kwargs)
                return None

        return wrapper

    return once


once = once_per()
once.__doc__ = "Let function execute once, noop all subsequent calls."


def once_per_args(func):
    """Call function once for every combination of values of its arguments."""
    return once_per(*get_argnames(func))(func)


@decorator
def wrap_with(call, ctx):
    """Turn context manager into a decorator"""
    with ctx:
        return call()





mods |= {
    "identity",
    "constantly",
    "caller",
    "partial",
    "rpartial",
    "func_partial",
    "curry",
    "rcurry",
    "autocurry",
    "iffy",
    "compose",
    "rcompose",
    "complement",
    "juxt",
    "ljuxt",
}



# This provides sufficient introspection for *curry() functions.
#
# We only really need a number of required positional arguments.
# If arguments can be specified by name (not true for many builtin functions),
# then we need to now their names to ignore anything else passed by name.
#
# Stars mean some positional argument which can't be passed by name.
# Functions not mentioned here get one star "spec".
ARGS = {}


ARGS["builtins"] = {
    "bool": "*",
    "complex": "real,imag",
    "enumerate": "iterable,start",
    "file": "file-**",
    "float": "x",
    "int": "x-*",
    "long": "x-*",
    "open": "file-**",
    "round": "number-*",
    "setattr": "***",
    "str": "object-*",
    "unicode": "string-**",
    "__import__": "name-****",
    "__buildclass__": "***",
    # Complex functions with different set of arguments
    "iter": "*-*",
    "format": "*-*",
    "type": "*-**",
}
# Add two argument functions
two_arg_funcs = """cmp coerce delattr divmod filter getattr hasattr isinstance issubclass
                   map pow reduce"""
ARGS["builtins"].update(dict.fromkeys(two_arg_funcs.split(), "**"))


ARGS["functools"] = {"reduce": "**"}


ARGS["itertools"] = {
    "accumulate": "iterable-*",
    "combinations": "iterable,r",
    "combinations_with_replacement": "iterable,r",
    "compress": "data,selectors",
    "groupby": "iterable-*",
    "permutations": "iterable-*",
    "repeat": "object-*",
}
two_arg_funcs = "dropwhile filterfalse ifilter ifilterfalse starmap takewhile"
ARGS["itertools"].update(dict.fromkeys(two_arg_funcs.split(), "**"))


ARGS["operator"] = {
    "delslice": "***",
    "getslice": "***",
    "setitem": "***",
    "setslice": "****",
}
two_arg_funcs = """
    _compare_digest add and_ concat contains countOf delitem div eq floordiv ge getitem
    gt iadd iand iconcat idiv ifloordiv ilshift imatmul imod imul indexOf ior ipow irepeat
    irshift is_ is_not isub itruediv ixor le lshift lt matmul mod mul ne or_ pow repeat rshift
    sequenceIncludes sub truediv xor
"""
ARGS["operator"].update(dict.fromkeys(two_arg_funcs.split(), "**"))
ARGS["operator"].update([("__%s__" % op.strip("_"), args) for op, args in ARGS["operator"].items()])
ARGS["_operator"] = ARGS["operator"]


# Fixate this
STD_MODULES = set(ARGS)


# Describe some funcy functions, mostly for r?curry()
ARGS["funcy.seqs"] = {
    "map": "f*",
    "lmap": "f*",
    "xmap": "f*",
    "mapcat": "f*",
    "lmapcat": "f*",
}
ARGS["funcy.colls"] = {
    "merge_with": "f*",
}


Spec = namedtuple("Spec", "max_n names req_n req_names varkw")


def get_spec(func, _cache={}):
    func = getattr(func, "__original__", None) or unwrap(func)
    try:
        return _cache[func]
    except (KeyError, TypeError):
        pass

    mod = getattr(func, "__module__", None)
    if mod in STD_MODULES or mod in ARGS and func.__name__ in ARGS[mod]:
        _spec = ARGS[mod].get(func.__name__, "*")
        required, _, optional = _spec.partition("-")
        req_names = re.findall(r"\w+|\*", required)  # a list with dups of *
        max_n = len(req_names) + len(optional)
        req_n = len(req_names)
        spec = Spec(max_n=max_n, names=set(), req_n=req_n, req_names=set(req_names), varkw=False)
        _cache[func] = spec
        return spec
    elif isinstance(func, type):
        # __init__ inherited from builtin classes
        objclass = getattr(func.__init__, "__objclass__", None)
        if objclass and objclass is not func:
            return get_spec(objclass)
        # Introspect constructor and remove self
        spec = get_spec(func.__init__)
        self_set = {func.__init__.__code__.co_varnames[0]}
        return spec._replace(
            max_n=spec.max_n - 1, names=spec.names - self_set, req_n=spec.req_n - 1, req_names=spec.req_names - self_set
        )
    elif hasattr(func, "__code__"):
        return _code_to_spec(func)
    else:
        # We use signature last to be fully backwards compatible. Also it's slower
        try:
            sig = signature(func)
            # import ipdb; ipdb.set_trace()
        except (ValueError, TypeError):
            raise ValueError(
                "Unable to introspect %s() arguments"
                % (getattr(func, "__qualname__", None) or getattr(func, "__name__", func))
            )
        else:
            spec = _cache[func] = _sig_to_spec(sig)
            return spec


def _code_to_spec(func):
    code = func.__code__

    # Weird function like objects
    defaults = getattr(func, "__defaults__", None)
    defaults_n = len(defaults) if isinstance(defaults, tuple) else 0

    kwdefaults = getattr(func, "__kwdefaults__", None)
    if not isinstance(kwdefaults, dict):
        kwdefaults = {}

    # Python 3.7 and earlier does not have this
    posonly_n = getattr(code, "co_posonlyargcount", 0)

    varnames = code.co_varnames
    pos_n = code.co_argcount
    n = pos_n + code.co_kwonlyargcount
    names = set(varnames[posonly_n:n])
    req_n = n - defaults_n - len(kwdefaults)
    req_names = set(varnames[posonly_n : pos_n - defaults_n] + varnames[pos_n:n]) - set(kwdefaults)
    varkw = bool(code.co_flags & CO_VARKEYWORDS)
    # If there are varargs they could be required
    max_n = n + 1 if code.co_flags & CO_VARARGS else n
    return Spec(max_n=max_n, names=names, req_n=req_n, req_names=req_names, varkw=varkw)


def _sig_to_spec(sig):
    max_n, names, req_n, req_names, varkw = 0, set(), 0, set(), False
    for name, param in sig.parameters.items():
        max_n += 1
        if param.kind == param.VAR_KEYWORD:
            max_n -= 1
            varkw = True
        elif param.kind == param.VAR_POSITIONAL:
            req_n += 1
        elif param.kind == param.POSITIONAL_ONLY:
            if param.default is param.empty:
                req_n += 1
        else:
            names.add(name)
            if param.default is param.empty:
                req_n += 1
                req_names.add(name)
    return Spec(max_n=max_n, names=names, req_n=req_n, req_names=req_names, varkw=varkw)


def identity(x):
    """Returns its argument."""
    return x


def constantly(x):
    """Creates a function accepting any args, but always returning x."""
    return lambda *a, **kw: x


# an operator.methodcaller() brother
def caller(*a, **kw):
    """Creates a function calling its sole argument with given *a, **kw."""
    return lambda f: f(*a, **kw)


def func_partial(func, *args, **kwargs):
    """A functools.partial alternative, which returns a real function.
    Can be used to construct methods."""
    return lambda *a, **kw: func(*(args + a), **dict(kwargs, **kw))


def rpartial(func, *args, **kwargs):
    """Partially applies last arguments.
    New keyworded arguments extend and override kwargs."""
    return lambda *a, **kw: func(*(a + args), **dict(kwargs, **kw))


def curry(func, n=EMPTY):
    """Curries func into a chain of one argument functions."""
    if n is EMPTY:
        n = get_spec(func).max_n

    if n <= 1:
        return func
    elif n == 2:
        return lambda x: lambda y: func(x, y)
    else:
        return lambda x: curry(partial(func, x), n - 1)


def rcurry(func, n=EMPTY):
    """Curries func into a chain of one argument functions.

    Arguments are passed from right to left.
    """
    if n is EMPTY:
        n = get_spec(func).max_n

    if n <= 1:
        return func
    if n == 2:
        return lambda x: lambda y: func(y, x)
    else:
        return lambda x: rcurry(rpartial(func, x), n - 1)



def autocurry(func, n=EMPTY, _spec=None, _args=(), _kwargs={}):
    """Creates a version of func returning its partial applications
    until sufficient arguments are passed."""
    spec = _spec or (get_spec(func) if n is EMPTY else Spec(n, set(), n, set(), False))

    @wraps(func)
    def autocurried(*a, **kw):
        args = _args + a
        kwargs = _kwargs.copy()
        kwargs.update(kw)

        if not spec.varkw and len(args) + len(kwargs) >= spec.max_n or len(args) + len(set(kwargs) & spec.names) >= spec.max_n:
            return func(*args, **kwargs)
        elif len(args) + len(set(kwargs) & spec.req_names) >= spec.req_n:
            try:
                return func(*args, **kwargs)
            except TypeError:
                return autocurry(func, _spec=spec, _args=args, _kwargs=kwargs)
        else:
            return autocurry(func, _spec=spec, _args=args, _kwargs=kwargs)

    return autocurried


def iffy(pred, action=EMPTY, default=identity):
    """Creates a function, which conditionally applies action or default."""
    if action is EMPTY:
        return iffy(bool, pred, default)
    else:
        pred = make_pred(pred)
        action = make_func(action)
        return lambda v: action(v) if pred(v) else default(v) if callable(default) else default

class MissingT:
    pass
_initial_missing = MissingT()

def reduce(function: Callable[[_T, _T], _T], sequence: Iterable[_T], initial: _T | MissingT = _initial_missing) -> _T:
    """`reduce(function, iterable[, initial]) -> value`.

    Apply a function of two arguments cumulatively to the items of a sequence
    or iterable, from left to right, so as to reduce the iterable to a single
    value.  For example, reduce(lambda x, y: x+y, [1, 2, 3, 4, 5]) calculates
    ((((1+2)+3)+4)+5).  If initial is present, it is placed before the items
    of the iterable in the calculation, and serves as a default when the
    iterable is empty.
    """
    it = iter(sequence)

    if initial is _initial_missing:
        try:
            value = next(it)
        except StopIteration:
            raise TypeError(
                "reduce() of empty iterable with no initial value"
            ) from None
    elif isinstance(initial, MissingT):
        raise TypeError("reduce() of empty sequence with no initial value")
    else:
        value = initial

    for element in it:
        value = function(value, element)

    return value

def compose(*fs: Callable) -> Callable:
    """Composes passed functions."""
    if fs:
        def pair(f: Callable, g: Callable):
            return lambda *a, **kw: f(g(*a, **kw))

        return reduce(pair, map(make_func, fs))

    return identity


def rcompose(*fs):
    """Composes functions, calling them from left to right."""
    return compose(*reversed(fs))


def complement(pred):
    """Constructs a complementary predicate."""
    return compose(operator.not_, pred)


# NOTE: using lazy map in these two will result in empty list/iterator
#       from all calls to i?juxt result since map iterator will be depleted


def ljuxt(*fs):
    """Constructs a juxtaposition of the given functions.
    Result returns a list of results of fs."""
    extended_fs = list(map(make_func, fs))
    return lambda *a, **kw: [f(*a, **kw) for f in extended_fs]


def juxt(*fs):
    """Constructs a lazy juxtaposition of the given functions.
    Result returns an iterator of results of fs."""
    extended_fs = list(map(make_func, fs))
    return lambda *a, **kw: (f(*a, **kw) for f in extended_fs)



mods |= {"memoize", "cache", "make_lookuper", "silent_lookuper", "EMPTY"}


class SkipMemory(Exception):
    pass


class memoize: # noqa: N801
    skip = SkipMemory
    def __call__(self,_func=None, *, key_func=None):
        """@memoize(key_func=None). Makes decorated function memoize its results.

        If key_func is specified uses key_func(*func_args, **func_kwargs) as memory key.
        Otherwise uses args + tuple(sorted(kwargs.items()))

        Exposes its memory via .memory attribute.
        """
        if _func is not None:
            return memoize()(_func)
        return _memory_decorator({}, key_func)

    def __new__(cls, *args, **kwargs):
        if args and callable(args[0]):
            return cls()(args[0])
        return super().__new__(cls)

class cache: # noqa: N801
    skip = SkipMemory

    def __call__(self,timeout, *, key_func=None):
        """Caches a function results for timeout seconds."""
        if isinstance(timeout, timedelta):
            timeout = timeout.total_seconds()

        return _memory_decorator(CacheMemory(timeout), key_func)



def _memory_decorator(memory, key_func):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # We inline this here since @memoize also targets microoptimizations
            key = key_func(*args, **kwargs) if key_func else args + tuple(sorted(kwargs.items())) if kwargs else args
            try:
                return memory[key]
            except KeyError:
                try:
                    value = memory[key] = func(*args, **kwargs)
                    return value
                except SkipMemory as e:
                    return e.args[0] if e.args else None

        def invalidate(*args, **kwargs):
            key = key_func(*args, **kwargs) if key_func else args + tuple(sorted(kwargs.items())) if kwargs else args
            memory.pop(key, None)

        wrapper.invalidate = invalidate

        def invalidate_all():
            memory.clear()

        wrapper.invalidate_all = invalidate_all

        wrapper.memory = memory
        return wrapper

    return decorator


class CacheMemory(dict):
    def __init__(self, timeout):
        self.timeout = timeout
        self.clear()

    def __setitem__(self, key, value):
        expires_at = time.time() + self.timeout
        dict.__setitem__(self, key, (value, expires_at))
        self._keys.append(key)
        self._expires.append(expires_at)

    def __getitem__(self, key):
        value, expires_at = dict.__getitem__(self, key)
        if expires_at <= time.time():
            self.expire()
            raise KeyError(key)
        return value

    def expire(self):
        i = bisect(self._expires, time.time())
        for _ in range(i):
            self._expires.popleft()
            self.pop(self._keys.popleft(), None)

    def clear(self):
        dict.clear(self)
        self._keys = deque()
        self._expires = deque()


def has_arg_types(func):
    params = inspect.signature(func).parameters.values()
    return any(p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.VAR_POSITIONAL) for p in params), any(
        p.kind in (p.KEYWORD_ONLY, p.VAR_KEYWORD) for p in params
    )


def _make_lookuper(silent):
    def make_lookuper(func):
        """Creates a single argument function looking up result in a memory.

        Decorated function is called once on first lookup and should return all available
        arg-value pairs.

        Resulting function will raise LookupError when using @make_lookuper
        or simply return None when using @silent_lookuper.
        """
        has_args, has_keys = has_arg_types(func)
        assert not has_keys, "Lookup table building function should not have keyword arguments"
        _wrapper: Callable
        if has_args:

            @memoize
            def args_wrapper(*args):
                f = lambda: func(*args)
                f.__name__ = "{}({})".format(func.__name__, ", ".join(map(str, args)))
                return make_lookuper(f)
            _wrapper = args_wrapper
        else:
            memory = {}

            def arg_wrapper(arg):
                if not memory:
                    memory[object()] = None  # prevent continuos memory refilling
                    memory.update(func())

                if silent:
                    return memory.get(arg)
                elif arg in memory:
                    return memory[arg]
                else:
                    raise LookupError(f"Failed to look up {func.__name__}({arg})")
            _wrapper = arg_wrapper
        return wraps(func)(_wrapper) # type: ignore noqa

    return make_lookuper


make_lookuper = _make_lookuper(False)
silent_lookuper = _make_lookuper(True)
silent_lookuper.__name__ = "silent_lookuper"



class PathLike(Path):
    parser = os.path
    if sys.version_info >= (3, 12): # noqa: UP036
        _globber = os.fspath
    else:
        _flavour = Path()._flavour # type: ignore # mypy bug
    _raw_path: str
    _raw_paths: list[str]

    
    def __init__(self,*args: str | Path) -> None:
        self._flavor = type(self)._flavor
        self._raw_path = "/".join(str(p) for p in args)
        self._raw_paths = [str(p) for p in args]
        
    def __new__(cls, *paths: str | Path) -> Self:
        cls._flavor = "posix"

        if isinstance(paths, list | tuple) and len(paths) > 1:
            paths = tuple(str(p) for p in paths)
            path = Path.__new__(cls, *paths)
            path._raw_path = str(path)
            path._raw_paths = cast(list[str],paths)
            return path
        if len(paths) == 1:
            raw_paths = paths
            raw_path = str(paths[0])
            path = Path.__new__(cls, raw_path)
            path._raw_path = raw_path
            path._raw_paths = [str(p) for p in paths]
            return path
        path = super().__new__(cls,_raw_path="",_raw_paths=[])
        path._raw_path = ""
        path._raw_paths = []
        return path

PathType = PathLike | str | Path

mods |= {"PathLike", "seekable", "exists", "ilen", "spy", "locate", "replace", "cat"}


