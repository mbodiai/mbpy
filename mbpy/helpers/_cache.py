from __future__ import annotations
from collections import defaultdict
import atexit
import os
import pickle
from asyncio import iscoroutine
from pathlib import Path
from queue import Queue
from threading import RLock
from types import GenericAlias, new_class
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Callable,
    Coroutine,
    Generator,
    ParamSpec,
    Protocol,
    Type,
    TypeVar,
    overload,
    NamedTuple,
    Self,
    Literal,
    Generic,

)
from time import sleep
import time
from mbpy.import_utils import smart_import
from dataclasses import dataclass
P = ParamSpec("P")
R = TypeVar("R")
_R = TypeVar("_R")
__R = TypeVar("__R")
AR = AsyncGenerator[None, _R]
GR = Generator[None, _R, None]
CR = Coroutine[None, None, __R]
GenFunc = Callable[P, GR]
Func = Callable[P, R]
CoroFunc = Callable[P, CR]
AsyncGenFunc = Callable[P, AR]
FuncTs = TypeAlias = Func | GenFunc | AsyncGenFunc | CoroFunc

R_co = TypeVar("R_co", covariant=True)

STARTUP_CACHES = os.environ.get("MB_STARTUP_CACHES", "pypi,github").split(",")
MB_CACHE_PATH = Path.home() / ".mb" / "cache"
TTL = os.getenv("MB_CACHE_TTL", 60 * 60 * 24 * 7)  # 1 week

_cache = {}
class _HashedSeq(list):
    """ This class guarantees that hash() will be called no more than once
        per element.  This is important because the lru_cache() will hash
        the key multiple times on a cache miss.

    """

    __slots__ = 'hashvalue'

    def __init__(self, tup, hash=hash):
        self[:] = tup
        self.hashvalue = hash(tup)

    def __hash__(self):
        return self.hashvalue

def _make_key(args, kwds, typed,
             kwd_mark = (object(),),
             fasttypes = {int, str, float},
             tuple=tuple, type=type, len=len, func=None):
    """Make a cache key from optionally typed positional and keyword arguments
    that includes function identity for cross-module caching
    """
    # Add function identification to the key
    if func is None:
        raise ValueError("Function reference is required for cross-module caching")
        
    # Normalize __main__ module to avoid duplicate caching
    module_name = func.__module__ if func.__module__ != '__main__' else 'main'
    func_id = (module_name, func.__qualname__)
    
    # Start the key with the function identifier
    key = (func_id,) + args
    
    if kwds:
        key += kwd_mark
        for item in kwds.items():
            key += item
    if typed:
        key += tuple(type(v) for v in args)
        if kwds:
            key += tuple(type(v) for v in kwds.values())
    # Don't return raw values anymore since we need to keep the function identifier
    return _HashedSeq(key)

@dataclass
class CacheEntry:
    value: Any | None = None
    ttl: int = -1
    last_accessed: float = 0.0
    last_updated: float = 0.0
    last_missed: float = 0.0

@dataclass
class CacheInfo:
    hits: int = 0
    misses: int = 0
    maxsize: int = 128
    currsize: int = 0


class FunctionCacheInfo(NamedTuple):
    kind: Literal["function","coroutine","generator","async_generator"] = "function"
    total: CacheInfo = CacheInfo()
    by_key: dict[str, CacheInfo] = {}
    

async def consume(value):
    if not TYPE_CHECKING:
        cast = smart_import("typing.cast")
        asyncio = smart_import("asyncio")
        AsyncGenerator = smart_import("typing.AsyncGenerator")
    else:
        import asyncio
        from typing import cast


    
    if asyncio.iscoroutine(value) or hasattr(value, "__await__"):
        value = await value
    

    if hasattr(value, "__aiter__"):
        value = cast(AsyncGenerator, value)
        yield [v async for v in value]
    
    if hasattr(value, "__iter__"):
        yield list(value)

    if asyncio.iscoroutinefunction(value):
        yield consume(value)
    elif isinstance(value, Generator):
        yield list(value)

    else:
        yield value
    return


async def make_cache_tree(cache_dict, filepath):
    filepath = Path(str(filepath))
    if not filepath.parent.exists():
        filepath.parent.mkdir(parents=True)
        
    
    # Clean save - no merging
    serializable = {}
    for k, v in cache_dict.items():
        if isinstance(v, CacheEntry):
            # Only materialize async generators at pickle time
            value = v.value
            if hasattr(value, '__aiter__'):
                value = [x async for x in value]
            serializable[k] = CacheEntry(
                value=value,
                ttl=v.ttl, 
                last_accessed=v.last_accessed,
                last_updated=v.last_updated,
                last_missed=v.last_missed
            )
    
    # Handle file operations in a context manager 
    with open(filepath, 'wb') as f:
        pickle.dump(serializable, f)


def make_cache_trees(cache_dict, filepath):
    if not TYPE_CHECKING:
        cast = smart_import("typing.cast")
        asyncio = smart_import("asyncio")
        threading = smart_import("threading")
    else:
        import asyncio
    asyncio.run(make_cache_tree(cache_dict, filepath))


class ParentT:
    __class_getitem__ = classmethod(GenericAlias)


class FuncP(Protocol[P, R_co]):
    def __call__(self: FuncP[P,R], *args: P.args, **kwargs: P.kwargs) -> R: ...


class AFuncP(Protocol[P, R_co]):
    async def __call__(self: AFuncP[P,AR[R] | R], *args: P.args, **kwargs: P.kwargs) -> AR[R] | R: ...


FuncT = TypeVar("FuncT", bound=FuncP | AFuncP)


class cache(defaultdict, Generic[P, R]):
    if not TYPE_CHECKING:
        cast = smart_import("typing.cast")
        asyncio = smart_import("asyncio")
        weakref = smart_import("weakref")
    else:
        import asyncio
        import weakref
        from typing import cast
    _info: FunctionCacheInfo = FunctionCacheInfo()
    _pending: Queue[Callable[[Type[cache], _HashedSeq], Type[cache]]] = Queue()
    _cache: dict[_HashedSeq, CacheEntry] = {}
    lock = RLock()

    def __contains__(self, key):
        return _cache.__contains__(key)

    def __getitem__(self, key):
        entry = _cache.__getitem__(key)
        current_time = time.time()
        if current_time - entry.last_updated > entry.ttl:
            del _cache[key]
            raise KeyError(key)
        new_entry = CacheEntry(
            value=entry.value,
            ttl=entry.ttl,
            last_accessed=current_time,
            last_updated=entry.last_updated,
            last_missed=entry.last_missed
        )
        _cache[key] = new_entry
        return entry.value

    def __setitem__(self, key, value):
        entry = CacheEntry(
            value=value,
            ttl=TTL,
            last_accessed=time.time(),
            last_updated=time.time(),
            last_missed=0.0
        )
        return _cache.__setitem__(key, entry)

    def __delitem__(self, key):
        return _cache.__delitem__(key)

    update = _cache.update
    clear = _cache.clear
    keys = _cache.keys
    values = _cache.values
    items = _cache.items
    pop = _cache.pop
    popitem = _cache.popitem
    setdefault = _cache.setdefault
    get = _cache.get
    __len__ = _cache.__len__
    __iter__ = _cache.__iter__

    def hit(self, key: _HashedSeq) -> Self:
        """Record that a key was accessed."""
        self._info.by_key.setdefault(key, CacheInfo()).hits += 1
        self._info.total.hits += 1

    def miss(self, key: _HashedSeq) -> "Self":
        """Record that a key was missed."""
        self._info.by_key.setdefault(key, CacheInfo()).misses += 1
        self._info.total.misses += 1
        return self

    def record(self, action: "Literal[hit, miss]") -> Self:
        """Record a cache key and value."""
        if action == "hit":
            self._pending.put_nowait(self.hit)
        elif action == "miss":
            self._pending.put_nowait(self.miss)
        return self

    def on(self, key: _HashedSeq) -> Type[cache]:
        """Record that a key was accessed."""
        fn, k = self._pending.get_nowait()
        fn(self, k)  # Call the method with self and key
        return self

    def cache_info(self, key: _HashedSeq|None=None) -> dict[_HashedSeq, CacheInfo]:
        if key is not None:
            return self._info.by_key.get(key)
        return self._info

    @overload
    def __new__(cls, func: Callable[P, R]) -> cache[P, R]: ...
    @overload
    def __new__(cls, func: Callable[P,Generator[None,R]]) -> cache[P,Generator[None,R]]: ...
    def __new__(
        cls, func: Callable[P, R] | Callable[P, AR[R]] | Callable[P, CR[R]] | Callable[P, GR[R]],
    ) -> cache[P, R] | cache[P, GR[R]]:
        new_cls = new_class("cache", (cls,), {}, lambda ns: ns.update(cls.__dict__))
        instance = super().__new__(new_cls)
        instance.__init__(func)
        instance.__doc__ = func.__doc__
        return instance



    if not TYPE_CHECKING:
        @overload
        def __init__(self, func: Callable[P, R]) -> None: ...
        @overload
        def __init__(self, func: Callable[P, AR[R]]) -> None: ...
        @overload
        def __init__(self, func: Callable[P, CR[R]]) -> None: ...
        @overload
        def __init__(self, func: Callable[P, GR[R]]) -> None: ...
        def __init__(self, func: FuncTs) -> None:

            self.func = func
            self._info = FunctionCacheInfo()
            self._pending = Queue()

    @overload
    def __call__(self: Callable[P,R], *args: P.args, **kwargs: P.kwargs) -> R: ...
    @overload
    def __call__(self: Callable[P,AR], *args: P.args, **kwargs: P.kwargs) -> AR[R]: ...
    @overload
    def __call__(self: Callable[P,CR], *args: P.args, **kwargs: P.kwargs) -> R: ...
    @overload
    def __call__(self: Callable[P,GR], *args: P.args, **kwargs: P.kwargs) -> GR[R]: ...

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R | AR[R] | GR[R]:
        key = _make_key(args, kwargs, False, func=self.func)
        if key in self:
            self.hit(key)
            return self[key]

        result = self.func(*args, **kwargs)
        self[key] = result
        self.miss(key)  # Direct call
        return result

    @classmethod
    def clear_cache(cls) -> None:
        import shutil

        try:
            with cls.lock:
                _cache.clear()

            if Path(MB_CACHE_PATH).exists():
                if Path(MB_CACHE_PATH).is_dir():
                    children = list(Path(MB_CACHE_PATH).iterdir())
                    for child in children:
                        if child.is_dir():
                            print(f"Removing {child}")
                            shutil.rmtree(child)
                        else:
                            print(f"Removing {child}")
                            os.remove(child)
                    shutil.rmtree(MB_CACHE_PATH)
                else:
                    os.remove(MB_CACHE_PATH)

        except Exception as e:
            import traceback
            traceback.print_exc()

    @classmethod
    def clear_all(cls) -> None:
        """Clear the cache registry."""
        cls._cache.clear()
        cls._pending = Queue()
        cls.clear_cache()

    @classmethod
    def load(cls, path: Path | str = MB_CACHE_PATH) -> None:
        if not isinstance(path, Path):
            path = Path(path)
        if path.exists():
            with open(path, 'rb') as f:
                loaded = pickle.load(f)
                cls._cache.update(loaded)


class acache(cache[P, R]):
    @overload
    async def __call__(self: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R: ...
    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R | AR[R] | GR[R]:
        key = _make_key(args, kwargs, False, func=self.func)
        if key in _cache:
            self.hit(key)
            return _cache[key].value
        

            
        result = self.func(*args, **kwargs)
        if hasattr(result, '__await__'):
            result = await result
        if hasattr(result, '__aiter__'):
            
            _cache[key] = CacheEntry(result, TTL, time.time(), time.time(), 0.0)
            self.miss(key)
            return result
            
        if hasattr(result, '__await__'):
            result = await result
        _cache[key] = CacheEntry(result, TTL, time.time(), time.time(), 0.0)
        self.miss(key)
        return result

        
atexit.register(make_cache_trees, _cache, MB_CACHE_PATH)

from rich.pretty import pprint
cache.load(MB_CACHE_PATH)

@cache
def fib(n: int) -> int:
    """info: Calculate the nth Fibonacci number"""
    sleep(0.01)
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


@acache
async def afib(n: int) -> int:
    if n < 2:
        return n
    return (await afib(n - 1)) + (await afib(n - 2))


@acache
async def ret_tup():
    yield 1
    yield 2
    yield 3
    return


async def unpack_tup():
    result = list([x async for x in ret_tup()])

    a, b, c = result
    return a, b, c
from more_itertools import take
if __name__ == "__main__":
    import asyncio
    from time import sleep
    from time import time as now

    a, b, c = asyncio.run(unpack_tup())
    print(a, b, c)
    tic = now()
    print(fib(100))

    a, b, c = asyncio.run(unpack_tup())
    print(a, b, c)
    tic = now()
    print(fib(100))
    print(f"execution time: {now() - tic:.5f}s")
    tic = now()
    print(fib(100))
    print(f"execution time: {now() - tic:.5f}s")
    tic = now()
    print(asyncio.run(afib(100)))
    print(f"Execution time: {now() - tic:.5f}s")
    tic = now()
    print(asyncio.run(afib(100)))

    print(f"Execution time: {now() - tic:.5f}s")
    print(fib.cache_info().total)
    print(afib.cache_info().total)
    # print(_cache)

