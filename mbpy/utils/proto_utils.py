# Copyright 2024 Mbodi AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import collections
import collections.abc
import os
import sys
from collections.abc import (
    Awaitable,
    Callable,
    Container,
    Iterable,
    Iterator,
    MutableMapping,
    MutableSequence,
    Sequence,
)
from os import PathLike
from types import FrameType, TracebackType
from typing import (
    AbstractSet,
    Any,
    AnyStr,
    ClassVar,
    Generic,
    List,
    LiteralString,
    NewType,
    Sized,
    SupportsAbs,
    SupportsFloat,
    SupportsInt,
    cast,
    overload,
)

from more_itertools import SequenceView, first_true, islice_extended, nth, seekable
from typing_extensions import (
    TYPE_CHECKING,
    Annotated,
    Final,
    Literal,
    Protocol,
    SupportsIndex,
    TypeAlias,
    TypeVar,
    final,
    runtime_checkable,
)
from typing_extensions import ItemsView as _ItemsView
from typing_extensions import KeysView as _KeysView
from typing_extensions import ValuesView as _ValuesView

OneDimensional = Annotated[Literal["dict", "np", "pt", "list", "sample"], "Numpy, PyTorch, list, sample, or dict"]

logged_recurse = False

if TYPE_CHECKING:
    from _operator import _K, _P, _R, _SupportsComparison, _SupportsInversion
    from dataclasses import Field
    lists = Any
    dicts = Any
    pytorch = Any
    samples = Any
    pt = Any
    sample = Any
    ignore = Any
    forbid = Any
    allow = Any
    descriptions = Any
    exclude = Any
    recurse = Any
    info = Any
    simple = Any
    tensor = Any
    longest = Any
    truncate = Any
    shallow = Any
    python = Any
    json = Any


_KT = TypeVar("_KT")
_KT_co = TypeVar("_KT_co", covariant=True)
_KT_contra = TypeVar("_KT_contra", contravariant=True)
_VT = TypeVar("_VT")
_VT_co = TypeVar("_VT_co", covariant=True)
_T = TypeVar("_T")
_T_co = TypeVar("_T_co", covariant=True)
_T_contra = TypeVar("_T_contra", contravariant=True)
Self = TypeVar("Self")

# covariant version of typing.AnyStr, useful for protocols
AnyStr_co = TypeVar("AnyStr_co", str, bytes, covariant=True)

# For partially known annotations. Usually, fields where type annotations
# haven't been added are left unannotated, but in some situations this
# isn't possible or a type is already partially known. In cases like these,
# use Incomplete instead of Any as a marker. For example, use
# "Incomplete | None" instead of "Any | None".
Incomplete: TypeAlias = Any  # stable

# To describe a function parameter that is unused and will work with anything.
Unused: TypeAlias = object  # stable
MaybeNone: TypeAlias = Any


Sentinal = NewType("Sentinal", object)
sentinel: Any


# stable
class IdentityFunc(Protocol):
    def __call__(self, x: _T, /) -> _T: ...


# stable
class SupportsNext(Protocol[_T_co]):
    def __next__(self) -> _T_co: ...


# stable
class SupportsAnext(Protocol[_T_co]):
    def __anext__(self) -> Awaitable[_T_co]: ...


# Comparison protocols


class SupportsDunderLT(Protocol[_T_contra]):
    def __lt__(self, other: _T_contra, /) -> bool: ...


class SupportsDunderGT(Protocol[_T_contra]):
    def __gt__(self, other: _T_contra, /) -> bool: ...


class SupportsDunderLE(Protocol[_T_contra]):
    def __le__(self, other: _T_contra, /) -> bool: ...


class SupportsDunderGE(Protocol[_T_contra]):
    def __ge__(self, other: _T_contra, /) -> bool: ...


class SupportsAllComparisons(
    SupportsDunderLT[Any], SupportsDunderGT[Any], SupportsDunderLE[Any], SupportsDunderGE[Any], Protocol,
): ...


SupportsRichComparison: TypeAlias = SupportsDunderLT[Any] | SupportsDunderGT[Any]
SupportsRichComparisonT = TypeVar("SupportsRichComparisonT", bound=SupportsRichComparison)  # noqa: Y001

# Dunder protocols


class SupportsAdd(Protocol[_T_contra, _T_co]):
    def __add__(self, x: _T_contra, /) -> _T_co: ...


class SupportsRAdd(Protocol[_T_contra, _T_co]):
    def __radd__(self, x: _T_contra, /) -> _T_co: ...


class SupportsSub(Protocol[_T_contra, _T_co]):
    def __sub__(self, x: _T_contra, /) -> _T_co: ...


class SupportsRSub(Protocol[_T_contra, _T_co]):
    def __rsub__(self, x: _T_contra, /) -> _T_co: ...


class SupportsDivMod(Protocol[_T_contra, _T_co]):
    def __divmod__(self, other: _T_contra, /) -> _T_co: ...


class SupportsRDivMod(Protocol[_T_contra, _T_co]):
    def __rdivmod__(self, other: _T_contra, /) -> _T_co: ...


# This protocol is generic over the iterator type, while Iterable is
# generic over the type that is iterated over.
@runtime_checkable
class SupportsIter(Protocol[_T_co]):
    def __iter__(self) -> _T_co: ...


# This protocol is generic over the iterator type, while AsyncIterable is
# generic over the type that is iterated over.
class SupportsAiter(Protocol[_T_co]):
    def __aiter__(self) -> _T_co: ...


class SupportsLenAndGetItem(Protocol[_T_co]):
    def __len__(self) -> int: ...
    def __getitem__(self, k: int, /) -> _T_co: ...


class SupportsTrunc(Protocol):
    def __trunc__(self) -> int: ...


# Mapping-like protocols


# stable
class SupportsItems(Protocol[_KT_co, _VT_co]):
    def items(self) -> AbstractSet[tuple[_KT_co, _VT_co]]: ...


# stable
class SupportsKeysAndGetItem(Protocol[_KT_co, _VT_co]):
    def keys(self: SupportsKeysAndGetItem[_KT, _VT], /) -> AbstractSet[_KT]: ...
    def __getitem__(self: SupportsKeysAndGetItem[_KT, _VT], key: _KT, /) -> _VT: ...
    def update(self: SupportsKeysAndGetItem[_KT, _VT], other: dict[_KT, _VT], /) -> None: ...
    def get(self: SupportsKeysAndGetItem[_KT, _VT], key: _KT, default: _VT, /) -> _VT: ...


class SupportsKeysItems(SupportsKeysAndGetItem[str, _VT_co], Protocol):
# This protocol is currently under discussion. Use SupportsContainsAndGetItem
# instead, if you require the __contains__ method.
    def items(self)->_ItemsView[str,_VT_co]:...
    def values(self)->_ValuesView[_VT_co]:...
    def __iter__(self)->_KeysView[str]:...
    def __contains__(self, x: Any, /) -> bool: ...
    def __getitem__(self, key: str, /) -> _VT_co: ...
# See https://github.com/python/typeshed/issues/11822.
class SupportsGetItem(Protocol[_KT_contra, _VT_co]):
    def __contains__(self, x: Any, /) -> bool: ...
    def __getitem__(self, key: _KT_contra, /) -> _VT_co: ...


# stable
class SupportsContainsAndGetItem(Protocol[_KT_contra, _VT_co]):
    def __contains__(self, x: Any, /) -> bool: ...
    def __getitem__(self, key: _KT_contra, /) -> _VT_co: ...


# stable
class SupportsItemAccess(Protocol[_KT_contra, _VT]):
    def __contains__(self, x: Any, /) -> bool: ...
    def __getitem__(self, key: _KT_contra, /) -> _VT: ...
    def __setitem__(self, key: _KT_contra, value: _VT, /) -> None: ...
    def __delitem__(self, key: _KT_contra, /) -> None: ...


StrPath: TypeAlias = str | PathLike[str]  # stable
BytesPath: TypeAlias = bytes | PathLike[bytes]  # stable
GenericPath: TypeAlias = AnyStr | PathLike[AnyStr]
StrOrBytesPath: TypeAlias = str | bytes | PathLike[str] | PathLike[bytes]  # stable

OpenTextModeUpdating: TypeAlias = Literal[
    "r+",
    "+r",
    "rt+",
    "r+t",
    "+rt",
    "tr+",
    "t+r",
    "+tr",
    "w+",
    "+w",
    "wt+",
    "w+t",
    "+wt",
    "tw+",
    "t+w",
    "+tw",
    "a+",
    "+a",
    "at+",
    "a+t",
    "+at",
    "ta+",
    "t+a",
    "+ta",
    "x+",
    "+x",
    "xt+",
    "x+t",
    "+xt",
    "tx+",
    "t+x",
    "+tx",
]
OpenTextModeWriting: TypeAlias = Literal["w", "wt", "tw", "a", "at", "ta", "x", "xt", "tx"]
OpenTextModeReading: TypeAlias = Literal["r", "rt", "tr", "U", "rU", "Ur", "rtU", "rUt", "Urt", "trU", "tUr", "Utr"]
OpenTextMode: TypeAlias = OpenTextModeUpdating | OpenTextModeWriting | OpenTextModeReading
OpenBinaryModeUpdating: TypeAlias = Literal[
    "rb+",
    "r+b",
    "+rb",
    "br+",
    "b+r",
    "+br",
    "wb+",
    "w+b",
    "+wb",
    "bw+",
    "b+w",
    "+bw",
    "ab+",
    "a+b",
    "+ab",
    "ba+",
    "b+a",
    "+ba",
    "xb+",
    "x+b",
    "+xb",
    "bx+",
    "b+x",
    "+bx",
]
OpenBinaryModeWriting: TypeAlias = Literal["wb", "bw", "ab", "ba", "xb", "bx"]
OpenBinaryModeReading: TypeAlias = Literal["rb", "br", "rbU", "rUb", "Urb", "brU", "bUr", "Ubr"]
OpenBinaryMode: TypeAlias = OpenBinaryModeUpdating | OpenBinaryModeReading | OpenBinaryModeWriting


# stable
class HasFileno(Protocol):
    def fileno(self) -> int: ...


FileDescriptor: TypeAlias = int  # stable
FileDescriptorLike: TypeAlias = int | HasFileno  # stable
FileDescriptorOrPath: TypeAlias = int | StrOrBytesPath


# stable
class SupportsRead(Protocol[_T_co]):
    def read(self, length: int = ..., /) -> _T_co: ...


# stable
class SupportsReadline(Protocol[_T_co]):
    def readline(self, length: int = ..., /) -> _T_co: ...


# stable
class SupportsNoArgReadline(Protocol[_T_co]):
    def readline(self) -> _T_co: ...


# stable
class SupportsWrite(Protocol[_T_contra]):
    def write(self, s: _T_contra, /) -> object: ...


# stable
class SupportsFlush(Protocol):
    def flush(self) -> object: ...


if hasattr(collections.abc, "Buffer"):
    Buffer = collections.abc.Buffer
else:

    class Buffer(Protocol):  # noqa: B024
        """Base class for classes that implement the buffer protocol.

        The buffer protocol allows Python objects to expose a low-level
        memory buffer interface. Before Python 3.12, it is not possible
        to implement the buffer protocol in pure Python code, or even
        to check whether a class implements the buffer protocol. In
        Python 3.12 and higher, the ``__buffer__`` method allows access
        to the buffer protocol from Python code, and the
        ``collections.abc.Buffer`` ABC allows checking whether a class
        implements the buffer protocol.

        To indicate support for the buffer protocol in earlier versions,
        inherit from this ABC, either in a stub file or at runtime,
        or use ABC registration. This ABC provides no methods, because
        there is no Python-accessible methods shared by pre-3.12 buffer
        classes. It is useful primarily for static checks.

        """

    # As a courtesy, register the most common stdlib buffer classes.
    Buffer.register(memoryview)
    Buffer.register(bytearray)
    Buffer.register(bytes)


# Unfortunately PEP 688 does not allow us to distinguish read-only
# from writable buffers. We use these aliases for readability for now.
# Perhaps a future extension of the buffer protocol will allow us to
# distinguish these cases in the type system.
ReadOnlyBuffer: TypeAlias = Buffer  # stable
# Anything that implements the read-write buffer interface.
WriteableBuffer: TypeAlias = Buffer
# Same as WriteableBuffer, but also includes read-only buffer types (like bytes).
ReadableBuffer: TypeAlias = Buffer  # stable


class SliceableBuffer(Buffer, Protocol):
    def __getitem__(self, slice: slice, /) -> Sequence[int]: ...


class IndexableBuffer(Buffer, Protocol):
    def __getitem__(self, i: int, /) -> int: ...


class SupportsGetItemBuffer(SliceableBuffer, IndexableBuffer, Protocol):
    def __contains__(self, x: Any, /) -> bool: ...
    @overload
    def __getitem__(self, slice: slice, /) -> Sequence[int]: ...
    @overload
    def __getitem__(self, i: int, /) -> int: ...


class SizedBuffer(Sized, Buffer, Protocol): ...


# for compatibility with third-party stubs that may use this
_BufferWithLen: TypeAlias = SizedBuffer  # not stable  # noqa: Y047

ExcInfo: TypeAlias = tuple[type[BaseException], BaseException, TracebackType]
OptExcInfo: TypeAlias = ExcInfo | tuple[None, None, None]

# stable
from types import NoneType as NoneType


# This is an internal CPython type that is like, but subtly different from, a NamedTuple
# Subclasses of this type are found in multiple modules.
# In typeshed, `structseq` is only ever used as a mixin in combination with a fixed-length `Tuple`
# See discussion at #6546 & #6560
# `structseq` classes are unsubclassable, so are all decorated with `@final`.
class structseq(Generic[_T_co]):
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


# Superset of typing.AnyStr that also includes LiteralString
AnyOrLiteralStr = TypeVar("AnyOrLiteralStr", str, bytes, LiteralString)  # noqa: Y001

# Represents when str or LiteralStr is acceptable. Useful for string processing
# APIs where literalness of return value depends on literalness of inputs
StrOrLiteralStr = TypeVar("StrOrLiteralStr", LiteralString, str)  # noqa: Y001

# Objects suitable to be passed to sys.setprofile, threading.setprofile, and similar
ProfileFunction: TypeAlias = Callable[[FrameType, str, Any], object]

# Objects suitable to be passed to sys.settrace, threading.settrace, and similar


# experimental
# Might not work as expected for pyright, see
#   https://github.com/python/typeshed/pull/9362
#   https://github.com/microsoft/pyright/issues/4339
class DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Field[Any]]]


# Anything that can be passed to the int/float constructors
ConvertibleToInt: TypeAlias = str | ReadableBuffer | SupportsInt | SupportsIndex | SupportsTrunc
ConvertibleToFloat: TypeAlias = str | ReadableBuffer | SupportsFloat | SupportsIndex

# A few classes updated from Foo(str, Enum) to Foo(StrEnum). This is a convenience so these
# can be accurate on all python versions without getting too wordy


class _SupportsInversion(Protocol[_T_co]):
    def __invert__(self) -> _T_co: ...

class _SupportsNeg(Protocol[_T_co]):
    def __neg__(self) -> _T_co: ...

class _SupportsPos(Protocol[_T_co]):
    def __pos__(self) -> _T_co: ...


# All four comparison functions must have the same signature, or we get false-positive errors
def lt(a: _SupportsComparison, b: _SupportsComparison, /) -> Any: ...
def le(a: _SupportsComparison, b: _SupportsComparison, /) -> Any: ...
def eq(a: object, b: object, /) -> Any: ...
def ne(a: object, b: object, /) -> Any: ...
def ge(a: _SupportsComparison, b: _SupportsComparison, /) -> Any: ...
def gt(a: _SupportsComparison, b: _SupportsComparison, /) -> Any: ...
def not_(a: object, /) -> bool: ...
def truth(a: object, /) -> bool: ...
def is_(a: object, b: object, /) -> bool: ...
def is_not(a: object, b: object, /) -> bool: ...
def abs(a: SupportsAbs[_T], /) -> _T: ...
def add(a: Any, b: Any, /) -> Any: ...
def and_(a: Any, b: Any, /) -> Any: ...
def floordiv(a: Any, b: Any, /) -> Any: ...
def index(a: SupportsIndex, /) -> int: ...
def inv(a: _SupportsInversion[_T_co], /) -> _T_co: ...
def invert(a: _SupportsInversion[_T_co], /) -> _T_co: ...
def lshift(a: Any, b: Any, /) -> Any: ...
def mod(a: Any, b: Any, /) -> Any: ...
def mul(a: Any, b: Any, /) -> Any: ...
def matmul(a: Any, b: Any, /) -> Any: ...
def neg(a: _SupportsNeg[_T_co], /) -> _T_co: ...
def or_(a: Any, b: Any, /) -> Any: ...
def pos(a: _SupportsPos[_T_co], /) -> _T_co: ...
def pow(a: Any, b: Any, /) -> Any: ...
def rshift(a: Any, b: Any, /) -> Any: ...
def sub(a: Any, b: Any, /) -> Any: ...
def truediv(a: Any, b: Any, /) -> Any: ...
def xor(a: Any, b: Any, /) -> Any: ...
def concat(a: Sequence[_T], b: Sequence[_T], /) -> Sequence[_T]: ...
def contains(a: Container[object], b: object, /) -> bool: ...
def countOf(a: Iterable[object], b: object, /) -> int: ...
@overload
def delitem(a: MutableSequence[Any], b: SupportsIndex, /) -> None: ...
@overload
def delitem(a: MutableSequence[Any], b: slice, /) -> None: ...
@overload
def delitem(a: MutableMapping[_K, Any], b: _K, /) -> None: ...
@overload
def getitem(a: Sequence[_T], b: slice, /) -> Sequence[_T]: ...
@overload
def getitem(a: SupportsGetItem[_K, _V], b: _K, /) -> _V: ...
def indexOf(a: Iterable[_T], b: _T, /) -> int: ...
@overload
def setitem(a: MutableSequence[_T], b: SupportsIndex, c: _T, /) -> None: ...
@overload
def setitem(a: MutableSequence[_T], b: slice, c: Sequence[_T], /) -> None: ...
@overload
def setitem(a: MutableMapping[_K, _V], b: _K, c: _V, /) -> None: ...
def length_hint(obj: object, default: int = 0, /) -> int: ...
@final
class attrgetter(Generic[_T_co]):
    @overload
    def __new__(cls, attr: str, /) -> attrgetter[Any]: ...
    @overload
    def __new__(cls, attr: str, attr2: str, /) -> attrgetter[tuple[Any, Any]]: ...
    @overload
    def __new__(cls, attr: str, attr2: str, attr3: str, /) -> attrgetter[tuple[Any, Any, Any]]: ...
    @overload
    def __new__(cls, attr: str, attr2: str, attr3: str, attr4: str, /) -> attrgetter[tuple[Any, Any, Any, Any]]: ...
    @overload
    def __new__(cls, attr: str, /, *attrs: str) -> attrgetter[tuple[Any, ...]]: ...
    def __call__(self, obj: Any, /) -> _T_co: ...

@final
class itemgetter(Generic[_T_co]):
    @overload
    def __new__(cls, item: _T, /) -> itemgetter[_T]: ...
    @overload
    def __new__(cls, item1: _T1, item2: _T2, /, *items: Unpack[_Ts]) -> itemgetter[tuple[_T1, _T2, Unpack[_Ts]]]: ...
    # __key: _KT_contra in SupportsGetItem seems to be causing variance issues, ie:
    # TypeVar "_KT_contra@SupportsGetItem" is contravariant
    #   "tuple[int, int]" is incompatible with protocol "SupportsIndex"
    # preventing [_T_co, ...] instead of [Any, ...]
    #
    # A suspected mypy issue prevents using [..., _T] instead of [..., Any] here.
    # https://github.com/python/mypy/issues/14032
    def __call__(self, obj: SupportsGetItem[Any, Any]) -> Any: ...

@final
class methodcaller:
    def __init__(self, name: str, /, *args: Any, **kwargs: Any) -> None: ...
    def __call__(self, obj: Any) -> Any: ...

def iadd(a: Any, b: Any, /) -> Any: ...
def iand(a: Any, b: Any, /) -> Any: ...
def iconcat(a: Any, b: Any, /) -> Any: ...
def ifloordiv(a: Any, b: Any, /) -> Any: ...
def ilshift(a: Any, b: Any, /) -> Any: ...
def imod(a: Any, b: Any, /) -> Any: ...
def imul(a: Any, b: Any, /) -> Any: ...
def imatmul(a: Any, b: Any, /) -> Any: ...
def ior(a: Any, b: Any, /) -> Any: ...
def ipow(a: Any, b: Any, /) -> Any: ...
def irshift(a: Any, b: Any, /) -> Any: ...
def isub(a: Any, b: Any, /) -> Any: ...
def itruediv(a: Any, b: Any, /) -> Any: ...
def ixor(a: Any, b: Any, /) -> Any: ...

def call(obj: Callable[_P, _R], /, *args: _P.args, **kwargs: _P.kwargs) -> _R: ...

def _compare_digest(a: AnyStr, b: AnyStr, /) -> bool: ...

if sys.version_info >= (3, 14):
    def is_none(a: object, /) -> TypeIs[None]: ...
    def is_not_none(a: _T | None, /) -> TypeIs[_T]: ...


def passthrough(*args, class_target: type | None = None, **kwargs) -> Any:
    if args and len(args) == 1 and not kwargs:
        return args[0]
    if args and not kwargs:
        return args
    if kwargs and not args and class_target:
        return class_target(**kwargs)
    return args, kwargs




@runtime_checkable
class ListLike(SupportsLenAndGetItem[_T_co], Protocol):
    def __extends__(self) -> List[object]: ...

@runtime_checkable
class DictLike(SupportsKeysAndGetItem[_KT, _VT], Protocol):
    def update(self, other: dict[_KT, _VT], /) -> None: ...

SampleT = TypeVar("SampleT", bound=ListLike | DictLike | Iterable[Any])


class View:
    MAX_REPR_LENGTH = int(os.getenv("MAX_REPR_LENGTH", "100"))

    def __init__(self, data) -> None:
        self.data = SequenceView(cast(Sequence, data)) if isinstance(data, ListLike) else data

    def __repr__(self) -> str:
        return f"sample_view({list(self.data)})"[: self.MAX_REPR_LENGTH]

    def __getitem__(self, i: int | slice | str) -> Any:  # noqa: PLR0911
        if isinstance(self.data, DictLike):
            return (
                self.data[i]
                if isinstance(i, str)
                else islice_extended(self.data.items(), i.start, i.stop, i.step)
                if isinstance(i, slice)
                else nth(self.data.items(), i)
            )
        if isinstance(i, str) and isinstance(self.data, DictLike):
            return self.data[i]
        if isinstance(i, int):
            return nth(self.data, i)
        if isinstance(i, slice):
            return islice_extended(self.data, i.start, i.stop, i.step)
        if isinstance(i, int):
            return seekable(self.data).seek(i)
        if isinstance(i, str):
            return first_true(enumerate(self.data), pred=lambda x: x[1] == i)
        return None

    def __iter__(self):
        return iter(self.data)

    def _mapping(self):
        return self.data

    def __call__(self):
        return self


class KeysView(View, _KeysView):
    def __repr__(self) -> str:
        return f"sample_keys({list(self.data)})"[: self.MAX_REPR_LENGTH]


class ValuesView(View, _ValuesView):
    def __repr__(self) -> str:
        return f"sample_values({list(self.data)})"[: self.MAX_REPR_LENGTH]


class ItemsView(View, _ItemsView,Generic[_KT_co, _VT_co]):
    def __repr__(self) -> str:
        return f"sample_items({list(self.data)})"[: self.MAX_REPR_LENGTH]

    def __str__(self) -> str:
        return f"sample_items({list(self.data)})"[: self.MAX_REPR_LENGTH]

from typing import Tuple, TypeVarTuple

Ts = TypeVarTuple("Ts")
Us = TypeVarTuple("Us")
T = TypeVar("T")
U = TypeVar("U")
T_co = TypeVar("T_co", covariant=True)
U_contra = TypeVar("U_contra", contravariant=True)
U_co = TypeVar("U_co", covariant=True)
class ShapeHolder(Protocol[*Ts]):...
    # types: Tuple[*Ts]

    # @property
    # def first(self):
    #     return self.types[0]
    
    # @property
    # def last(self):
    #     return self.types[-1]
    

class ShapeDTypeHolder(Protocol[*Ts, U_co]):
    _shape: Tuple[*Ts]
    _dtype: U_co
    
    @property
    def dtype(self):
        return self._dtype
    @property
    def shape(self):
        return self._shape
_PositiveInteger: TypeAlias = Literal[
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    23,
    24,
    25,
]
_NegativeInteger: TypeAlias = Literal[
    -1,
    -2,
    -3,
    -4,
    -5,
    -6,
    -7,
    -8,
    -9,
    -10,
    -11,
    -12,
    -13,
    -14,
    -15,
    -16,
    -17,
    -18,
    -19,
    -20,
]
_LiteralInteger: TypeAlias = _PositiveInteger | _NegativeInteger | Literal[0]  # noqa: Y026  # TODO: Use TypeAlias once mypy bugs are fixed
    
        
    

@runtime_checkable
class IndexLike(Protocol):
    def __index__(self) -> int: ...
@runtime_checkable
class CoordsLike(Protocol[*Ts]):
    def __getitem__(self, key: int | slice | str) -> Any: ...
    def __iter__(self):...



@runtime_checkable
class ArrayLike(Protocol):
    """Arrays, tensors, numeric lists. Not strings, dicts, or sets."""
    def __iter__(self) -> Iterator[Any]: ...
    def __len__(self) -> int: ...
    def __getitem__(self, key: int | slice) -> Any: ... 
    def index(self, value: Any) -> int: ... 
    def count(self, value: Any) -> int: ... 