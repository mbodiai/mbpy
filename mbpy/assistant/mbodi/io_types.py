
from typing import Any, Mapping, Type, TypeAlias, TypeVar, Generic
import typing
from pydantic import FilePath, computed_field
import typing_extensions
from pydantic._internal._repr import Representation

from pydantic.main import BaseModel

class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any]



T = TypeVar("T")
MappingIntStrAny: TypeAlias = typing.Mapping[int, Any] | typing.Mapping[str, Any]
AbstractSetIntStr: TypeAlias = typing.AbstractSet[int] | typing.AbstractSet[str]
if typing.TYPE_CHECKING:
    ReprArgs: typing_extensions.TypeAlias = "typing.Iterable[tuple[str | None, Any]]"
    RichReprResult: typing_extensions.TypeAlias = (
        "typing.Iterable[Any | tuple[Any] | tuple[str, Any] | tuple[str, Any, Any]]"
    )
else:
    ReprArgs = Any
    RichReprResult = Any



class ValueItems(Representation):
    """Class for more convenient calculation of excluded or included fields on values."""

    __slots__ = ("_items", "_type")

    def __init__(self, value: Any, items: AbstractSetIntStr | MappingIntStrAny) -> None:
        items = self._coerce_items(items)

        if isinstance(value, (list, tuple)):
            items = self._normalize_indexes(items, len(value))  # type: ignore

        self._items: MappingIntStrAny = items  # type: ignore

    def is_excluded(self, item: Any) -> bool:
        """Check if item is fully excluded.

        :param item: key or index of a value
        """
        return self.is_true(self._items.get(item))

    def is_included(self, item: Any) -> bool:
        """Check if value is contained in self._items.

        :param item: key or index of value
        """
        return item in self._items

    def for_element(self, e: int | str) -> AbstractSetIntStr | MappingIntStrAny | None:
        """:param e: key or index of element on value
        :return: raw values for element if self._items is dict and contain needed element
        """  # noqa: D205
        item = self._items.get(e)  # type: ignore
        return item if not self.is_true(item) else None

    def _normalize_indexes(
        self, items: MappingIntStrAny, v_length: int
    ) -> dict[int | str, Any]:
        """:param items: dict or set of indexes which will be normalized
        :param v_length: length of sequence indexes of which will be

        >>> self._normalize_indexes({0: True, -2: True, -1: True}, 4)
        {0: True, 2: True, 3: True}
        >>> self._normalize_indexes({"__all__": True}, 4)
        {0: True, 1: True, 2: True, 3: True}
        """  # noqa: D205
        normalized_items: dict[int | str, Any] = {}
        all_items = None
        for i, v in items.items():
            if not (
                isinstance(v, typing.Mapping | typing.AbstractSet) or self.is_true(v)
            ):
                raise TypeError(
                    f'Unexpected type of exclude value for index "{i}" {v.__class__}'
                )
            if i == "__all__":
                all_items = self._coerce_value(v)
                continue
            if not isinstance(i, int):
                raise TypeError(
                    "Excluding fields from a sequence of sub-models or dicts must be performed index-wise: "
                    'expected integer keys or keyword "__all__"'
                )
            normalized_i = v_length + i if i < 0 else i
            normalized_items[normalized_i] = self.merge(
                v, normalized_items.get(normalized_i)
            )

        if not all_items:
            return normalized_items
        if self.is_true(all_items):
            for i in range(v_length):
                normalized_items.setdefault(i, ...)
            return normalized_items
        for i in range(v_length):
            normalized_item = normalized_items.setdefault(i, {})
            if not self.is_true(normalized_item):
                normalized_items[i] = self.merge(all_items, normalized_item)
        return normalized_items

    @staticmethod
    def _coerce_items(items: AbstractSetIntStr | MappingIntStrAny) -> MappingIntStrAny:
        if isinstance(items, typing.Mapping):
            pass
        elif isinstance(items, typing.AbstractSet):
            items = dict.fromkeys(items, ...)  # type: ignore
        else:
            class_name = getattr(items, "__class__", "???")
            raise TypeError(f"Unexpected type of exclude value {class_name}")
        return items  # type: ignore

    @classmethod
    def _coerce_value(cls, value: Any) -> Any:
        if value is None or cls.is_true(value):
            return value
        return cls._coerce_items(value)

    @staticmethod
    def is_true(v: Any) -> bool:
        return v is True or v is ...

    def __repr_args__(self) -> ReprArgs:
        return [(None, self._items)]

    @classmethod
    def merge(cls, base: Any, override: Any, intersect: bool = False) -> Any:
        """Merge a `base` item with an `override` item.

        Both `base` and `override` are converted to dictionaries if possible.
        Sets are converted to dictionaries with the sets entries as keys and
        Ellipsis as values.

        Each key-value pair existing in `base` is merged with `override`,
        while the rest of the key-value pairs are updated recursively with this function.

        Merging takes place based on the "union" of keys if `intersect` is
        set to `False` (default) and on the intersection of keys if
        `intersect` is set to `True`.
        """
        override = cls._coerce_value(override)
        base = cls._coerce_value(base)
        if override is None:
            return base
        if cls.is_true(base) or base is None:
            return override
        if cls.is_true(override):
            return base if intersect else override

        # intersection or union of keys while preserving ordering:
        if intersect:
            merge_keys = [k for k in base if k in override] + [
                k for k in override if k in base
            ]
        else:
            merge_keys = list(base) + [k for k in override if k not in base]

        merged: dict[int | str, Any] = {}
        for k in merge_keys:
            merged_item = cls.merge(base.get(k), override.get(k), intersect=intersect)
            if merged_item is not None:
                merged[k] = merged_item

        return merged


ArgsKwargs = Mapping[str, T]


class Base(BaseModel, Generic[T]):
    @computed_field
    def ArgsKwargs(
        self,
        exclude_unset: bool = True,
        include: Mapping[str, Any] | None = None,
        update: Mapping[str, Any] | None = None,
        exclude: Mapping[str, Any] | None = None,
    ) -> Mapping[str, T]:
        keys = set()
        args = {}
        if exclude_unset:
            keys = self.__pydantic_fields_set__.copy()
            args.update(self.model_fields)
        else:
            keys = set(self.__dict__.keys())
            keys = keys | (self.__pydantic_extra__ or {}).keys()
            args.update(
                {k: self.model_fields[k] for k in keys if k in self.model_fields}
            )

        if include is not None:
            keys &= include.keys()
            args.update(include)

        if update:
            keys -= update.keys()
            args.update(update)

        if exclude:
            keys -= {k for k, v in exclude.items() if ValueItems.is_true(v)}
            args.update({k: v for k, v in exclude.items() if not ValueItems.is_true(v)})
        return {k: self.__dict__[k] for k in keys}

    def __init__(self, **data: T) -> None:
        super().__init__(**data)


class ContentItem(Base[Type[str | None | ToolCall | FilePath]]):
    text: str | None = None
    image: FilePath | str | None = None
    tool_call: ToolCall | None = None



class Message(BaseModel, Generic[T]):
    role: str
    content: T
    timestamp: str
    num_error_outputs: int