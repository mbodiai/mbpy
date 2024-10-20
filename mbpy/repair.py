# Updated metaclass to handle both single dimensions and tuples of dimensions

# Metaclass for ndarray to automatically wrap shapes in Literal[]
import contextlib
import inspect
import os
import tempfile
from abc import ABCMeta
from collections.abc import Sequence
from tempfile import NamedTemporaryFile
from types import SimpleNamespace, new_class
from typing import Final, NamedTuple, Self, Tuple, TypeAlias, TypeVarTuple, Union, Unpack, cast, final, overload

import numpy as np
from einops import rearrange, reduce
from numpy._typing import _NestedSequence as NestedSequence
from numpy._typing import _SupportsArray as ArrayLike
from numpy.array_api import asarray, empty, ones, ones_like, zeros, zeros_like
from numpy.typing import NDArray
from rich.console import Console
from rich.pretty import Pretty, pprint, pretty_repr
from rich.traceback import Traceback, install
from typing_extensions import (
    Any,
    Generic,
    Literal,
    Tuple,
    Type,
    TypeVar,
    _SpecialForm,
    get_args,
    get_type_hints,
    reveal_type,
)

install(show_locals=True)
globals()["console"] = Console()


def print(*args, **kwargs):
    globals()["console"].print(*args, **kwargs)


ReductionType: TypeAlias = Literal["min", "max", "sum", "mean", "prod", "any", "all"]


class Error(BaseException):
    __name__ = "Exception"

    def __init__(self, e: Exception, msg: str = "", console: Console | None = None):
        self.e = e
        self.msg = msg
        self.console = console or globals().get("console", Console())
        self.console.print(f"[bold red]Error: {msg}[/bold red] {e}") if msg else None
        self.console.print(Traceback.from_exception(type(e), e, e.__traceback__))
        type(self).__name__ = type(e).__name__


def get_dtype(data: np.ndarray | list | ArrayLike) -> type:
    if isinstance(data, np.ndarray):
        return data.dtype
    if isinstance(data, Sequence):
        return get_dtype(data[0])
    return type(data)


def get_shape(data: np.ndarray | list | ArrayLike) -> Tuple[int, ...]:
    print(data)
    from rich import inspect
    inspect(data,all=True)
    print(f"get_shape {data}")
    if isinstance(data, np.ndarray) or hasattr(data, "shape"):
        return data.shape
    if isinstance(data, Sequence):
        s = (len(data),)
        for i in data:
            if isinstance(i, Sequence):
                s = s + (len(i),)
        return s
    msg = f"Data must be a numpy array or array-like object, not {type(data)}"
    raise Error(TypeError(msg))


def display(self: "ndarray"):
    if os.getenv("NO_RICH"):
        return np.array_str(self.data)
    from io import StringIO

    strio = StringIO()
    c = Console(record=True, soft_wrap=True, file=strio)
    c.print(
        Pretty(
            self.data,
            max_length=50,
            max_string=100,
            indent_guides=True,
            overflow="ellipsis",
        )
    )
    return c.export_text(styles=True)


T = TypeVar("T")
_Ts = TypeVarTuple("_Ts")
_DType = TypeVar("_DType")
p = np.ndarray([1, 2, 3])

Ts = TypeVarTuple("Ts")
DT = TypeVar("DT")
T = TypeVar("T")
U = TypeVar("U")

SupportedArrayTypes: Final = (np.ndarray, list, ArrayLike, NestedSequence)

def setup_shape_dtype_data(
    self: "ndarray",
    shape: Tuple[*Ts] | None = None,
    dtype: DT | None = None,
    data: np.ndarray | None = None,
):
    if isinstance(data, SupportedArrayTypes):
        with contextlib.suppress(Warning):
            data_shape = get_shape(data) if data is not None else shape if shape is not None else type(self).shape
            class_shape = type(self).shape = type(self).shape or shape or data_shape
            arg_shape = shape = shape or data_shape or type(self).shape
            if (
                data is not None
                and len(data_shape) != len(class_shape)
                or len(data_shape) != len(arg_shape)
                or not all(d == s and s == ts for d, s, ts in zip(data_shape, shape, type(self).shape, strict=False))
            ):
                msg = f"Shape {class_shape} and data {str(data)[:50]}'s shape {data_shape} do not match"
                raise Error(TypeError(msg))

        self.shape = get_shape(data) if data is not None else shape
        self.dtype = get_dtype(data) if data is not None else dtype
        self.data = (
            data
            if isinstance(data, np.ndarray)
            else np.asarray(data)
            if data is not None
            else np.zeros(shape, dtype=dtype)
            if shape is not None
            else np.empty(0, dtype=dtype)
        )

        return self.shape, self.dtype, self.data
    return (), None, None
def np_init(
    self,
    shape: Tuple[*Ts] | None = None,
    dtype: DT | None = None,
    data: np.ndarray | None = None,
):
    if not isinstance(shape, tuple) and isinstance(shape, Sequence):
        data = np.asarray(shape)
        shape = data.shape
        dtype = data.dtype
    setup_shape_dtype_data(self, shape, dtype, data)

def np_getitem(cls: "Type[ndarray]", shape: Tuple[*Ts] | None = None, dtype: DT | None = None):
    cls.shape = shape if isinstance(shape, tuple) else (shape,)
    cls.shape = cls.shape[:-1] if cls.shape and isinstance(cls.shape[-1], type) else cls.shape
    cls.dtype = cls.shape[-1] if cls.shape and isinstance(cls.shape[-1], type) else dtype
    return cls


# class NDArrayMeta(type):
#     shape: Tuple[*Ts] | None
#     data: np.ndarray | None
#     dtype: DT | None

#     def __new__(
#         cls,
#         name: str | None = None,
#         bases: Tuple[type, ...] | None = None,
#         namespace: dict[str, Union[*_Ts, T]] | None = None,
#         **kwargs,
#     ):
#         print("NDArrayMeta")
#         print(cls, name, bases)
#         name = name or "ndarray"
#         bases = bases or (NDArray,)
#         namespace = namespace or {}
#         # namespace.update({"__init__": np_init, "__getitem__": np_getitem, "__class_getitem__": classmethod(np_getitem), "__call__": np_init})
#         print(namespace)
#         # cls = new_class(name, bases,  kwargs,exec_body=lambda ns: ns.update(namespace))

#         cls = super().__new__(cls, name, bases, namespace, **kwargs)
#         # cls.__init__ = np_init
#         # cls.__call__ = np_init
#         # cls.__getitem__ = np_getitem
#         # cls.__class_getitem__ = classmethod(np_getitem)
#         return cls()

#     # __getitem__ = classmethod(np_getitem)
#     # __class_getitem__ = classmethod(np_getitem)

#     def __call__(cls, *args, **kwargs):
#         cls.__init__ = np_init
#         # cls.__init__(cls, *args, **kwargs)
#         return cls
#         print("NDArrayMeta __call__")
#         print(cls, args, kwargs)
#         # cls.__init__ = np_init
#         # cls.__init__(cls, *args, **kwargs)
#         # return np_init(cls, *args, **kwargs)

#     # __init__ = np_init

class TypedDict(dict):
    shape: Tuple[*Ts] | None
    dtype: DT | None
    def __init__(self, *args, **kwargs):
        shape, dtype, data = setup_shape_dtype_data(self, *args, **kwargs)
        type(self).shape = shape
        type(self).dtype = dtype
        type(self).data = data
        super().__init__(*args, **kwargs)
        self.__dict__ = self
    
    def __getattr__(self, name):
        if name in self and not name.startswith("__"):
            return self[name]
        return super().__getattr__(name)
    
    def __setattr__(self, name, value):
        if name in self and not name.startswith("__"):
            self[name] = value
        else:
            super().__setattr__(name, value)

    __class_getitem__ = classmethod(np_getitem)
        
class ndarray(Generic[*Ts, DT], NDArray[Any]):
    shape: Tuple[*Ts] | None
    data: np.ndarray | None
    dtype: DT | None

    def __new__(cls, *args, **kwargs):
        print("ndarray __new__")
        print(cls, args, kwargs)
        print(cls.shape, cls.dtype, cls.data)

        ns = TypedDict[cls.shape, cls.dtype](shape=cls.shape, dtype=cls.dtype, data=cls.data)
        # cls.shape = 
        shape, dtype, data = setup_shape_dtype_data(ns, *args, **kwargs)
        cls = super().__new__(cls, shape, dtype, data)
        # cls.__init__(cls, *args, **kwargs)
        return cls

    __init__ = np_init

    # __call__ = np_init

    # __class_getitem__ = classmethod(np_getitem)

    def transpose(self: "ndarray[U,T, DT]"):
        a = rearrange(tensor=np.asarray(self), pattern="n ... -> ... n")
        return cast(ndarray[T, U, DT], a)

    __class_getitem__ = classmethod(np_getitem)

    # Permute the axes of the array (general axis manipulation)
    def permute(self, axes: Tuple[int, ...]) -> "ndarray":
        new_shape = tuple(self.shape[axis] for axis in axes)
        return ndarray(data=(), shape=new_shape)

    # Reshape the array
    def reshape(self, new_shape: Tuple[int, ...]) -> "ndarray":
        return ndarray(data=(), shape=new_shape)

    # Reduce operation along a specified axis (e.g., sum, mean)
    @overload
    def reduce(self: "ndarray[U, T, DT]", axis: Literal[0], reduction="mean") -> "ndarray[T, DT]": ...
    @overload
    def reduce(self: "ndarray[U,T, DT]", axis: Literal[1], reduction="mean") -> "ndarray[U, DT]": ...
    def reduce(
        self: "ndarray[U, T, DT]",
        axis: Literal[0] | Literal[1],
        reduction: Literal["min", "max", "sum", "mean", "prod", "any", "all"] = "mean",
    ):
        if axis == 0:
            return cast(ndarray[T, DT], reduce(np.asarray(self), "m n -> n", reduction))
        if axis == 1:
            return cast(ndarray[U, DT], reduce(np.asarray(self), "n m -> m", reduction))

        msg = f"Axis must be 0 or 1, not {axis}"
        raise Error(TypeError(msg))

    def __str__(self):
        return display(self)


arr = ndarray[1, 2, float]
b: ndarray[1, 3, float] = ndarray[1, 3, float](data=[[1, 2, 3]])
print(b)
from mypy import api

# Extracting type hints for the functions to simulate reveal_type
transpose_type = reveal_type(b)
reshape_type = b.transpose()
reduce_type = b.reduce(1)
