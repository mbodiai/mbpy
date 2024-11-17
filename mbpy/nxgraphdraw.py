import sys
from typing import NamedTuple, TypeAlias, dataclass_transform, Annotated, NotRequired, Optional, List, Dict, Required, Tuple, Literal,_TypedDictMeta, Generic, get_args, get_origin, TypedDict as _TypedDict
import typing
from types import SimpleNamespace as Namespace
from typing_extensions import ReadOnly
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import os
RGB = Tuple[float, float, float]
RGBA = Tuple[float, float, float, float]

def _caller(depth=1, default="__main__"):
    try:
        return sys._getframemodulename(depth + 1) or default
    except AttributeError:  # For platforms without _getframemodulename()
        pass
    try:
        return sys._getframe(depth + 1).f_globals.get("__name__", default)
    except (AttributeError, ValueError):  # For platforms without _getframe()
        pass
    return None

class _Sentinel:
    __slots__ = ()

    def __repr__(self):
        return "<sentinel>"


_sentinel = _Sentinel()

class attrdict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.__dict__ = self

    def __getattr__(self, name):
        return self[name]

    def __setattr__(self, name, value):
        self[name] = value

def _get_typeddict_qualifiers(annotation_type):
    while True:
        annotation_origin = get_origin(annotation_type)
        if annotation_origin is Annotated:
            annotation_args = get_args(annotation_type)
            if annotation_args:
                annotation_type = annotation_args[0]
            else:
                break
        elif annotation_origin is Required:
            yield Required
            (annotation_type,) = get_args(annotation_type)
        elif annotation_origin is NotRequired:
            yield NotRequired
            (annotation_type,) = get_args(annotation_type)
        elif annotation_origin is ReadOnly:
            yield ReadOnly
            (annotation_type,) = get_args(annotation_type)
        else:
            break
class TypedDictMeta(_TypedDictMeta):
    def __new__(cls, name, bases, ns, total=True):
        """Create a new typed dict class object.

        This method is called when TypedDict is subclassed,
        or when TypedDict is instantiated. This way
        TypedDict supports all three syntax forms described in its docstring.
        Subclasses and instances of TypedDict return actual dictionaries.
        """
        if any(issubclass(b, Generic) for b in bases):
            generic_base = (Generic,)
        else:
            generic_base = ()

        tp_dict = type.__new__(_TypedDictMeta, name, (*generic_base, dict), ns)

        if not hasattr(tp_dict, "__orig_bases__"):
            tp_dict.__orig_bases__ = bases

        annotations = {}
        own_annotations = ns.get("__annotations__", {})
        required_keys = set()
        optional_keys = set()
        readonly_keys = set()
        mutable_keys = set()

        for base in bases:
            annotations.update(base.__dict__.get("__annotations__", {}))

            base_required = base.__dict__.get("__required_keys__", set())
            required_keys |= base_required
            optional_keys -= base_required

            base_optional = base.__dict__.get("__optional_keys__", set())
            required_keys -= base_optional
            optional_keys |= base_optional

            readonly_keys.update(base.__dict__.get("__readonly_keys__", ()))
            mutable_keys.update(base.__dict__.get("__mutable_keys__", ()))

        annotations.update(own_annotations)
        for annotation_key, annotation_type in own_annotations.items():
            qualifiers = set(_get_typeddict_qualifiers(annotation_type))
            if Required in qualifiers:
                is_required = True
            elif NotRequired in qualifiers:
                is_required = False
            else:
                is_required = total

            if is_required:
                required_keys.add(annotation_key)
                optional_keys.discard(annotation_key)
            else:
                optional_keys.add(annotation_key)
                required_keys.discard(annotation_key)

            if ReadOnly in qualifiers:
                if annotation_key in mutable_keys:
                    raise TypeError(
                        f"Cannot override mutable key {annotation_key!r}"
                        " with read-only key"
                    )
                readonly_keys.add(annotation_key)
            else:
                mutable_keys.add(annotation_key)
                readonly_keys.discard(annotation_key)

        assert required_keys.isdisjoint(optional_keys), (
            f"Required keys overlap with optional keys in {name}:"
            f" {required_keys=}, {optional_keys=}"
        )
        tp_dict.__annotations__ = annotations
        tp_dict.__required_keys__ = frozenset(required_keys)
        tp_dict.__optional_keys__ = frozenset(optional_keys)
        tp_dict.__readonly_keys__ = frozenset(readonly_keys)
        tp_dict.__mutable_keys__ = frozenset(mutable_keys)
        tp_dict.__total__ = total
        return tp_dict

    __call__ = attrdict.__call__

    def __subclasscheck__(cls, other):
        # Typed dicts are only for static structural subtyping.
        return cls in other.__mro_entries__

    __instancecheck__ = __subclasscheck__
    
def TypedDictInit(typename, fields=_sentinel, /, *, total=True):
    """A simple typed namespace."""
    if fields is _sentinel or fields is None:
        import warnings

        if fields is _sentinel:
            deprecated_thing = "Failing to pass a value for the 'fields' parameter"
        else:
            deprecated_thing = "Passing `None` as the 'fields' parameter"

        example = f"`{typename} = TypedDict({typename!r}, {{{{}}}})`"
        deprecation_msg = (
            (
                "{name} is deprecated and will be disallowed in Python {remove}. "
                "To create a TypedDict class with 0 fields "
                "using the functional syntax, "
                "pass an empty dictionary, e.g. "
            )
            + example
            + "."
        )
        warnings._deprecated(deprecated_thing, message=deprecation_msg, remove=(3, 15))
        fields = {}

    ns = {"__annotations__": dict(fields)}
    module = _caller()
    if module is not None:
        # Setting correct module is necessary to make typed dict classes pickleable.
        ns["__module__"] = module

    td = _TypedDictMeta(typename, (), ns, total=total)
    td.__orig_bases__ = (TypedDict,)
    return td


_TypedDictMro = type.__new__(_TypedDictMeta, "TypedDict", (), {})
TypedDictInit.__mro_entries__ = lambda bases: (_TypedDictMro,)

@dataclass_transform()
class TypedDict(_TypedDict, metaclass=TypedDictMeta,total=False):
    pass
    # __init_subclass__ = _TypedDict.__init_subclass__

class Coords2D(TypedDict, total=True):
    x: float
    y: float
@dataclass_transform()
class GraphicSettings(NamedTuple):
    class Kwargs(TypedDict, total=False):
        label: str
        size: int
        color: Literal[
            "orange",
            "lightcoral",
            "violet",
            "lightgreen",
            "lightblue",
            "red",
            "blue",
            "yellow",
        ] | RGB | RGBA
        shape: Literal["o", "s", "^", "v", "D"]
        icon: str
        pos: Coords2D

    label: str = "Node"
    size: int = 100
    color: Literal[
        "orange",
        "lightcoral",
        "violet",
        "lightgreen",
        "lightblue",
        "red",
        "blue",
        "yellow",
    ] | RGB | RGBA = "orange"
    shape: Literal["o", "s", "^", "v", "D"] = "o"
    icon: str = ""
    pos: Coords2D = {"x": 0, "y": 0}
    kwargs: Kwargs = {}


a: GraphicSettings.Kwargs = {"label": "Foundation Models"}

b = GraphicSettings(**a)

d,e, *f = b



def draw_graph(
    node_array: List[List[GraphicSettings]], edge_list: List[Tuple[str, str]]
) -> None:
    G = nx.DiGraph()


    for y, row in enumerate(node_array):
        for x, node_attr in enumerate(row):
            label = node_attr["label"]
            G.add_node(label, **node_attr)

    G.add_edges_from(edge_list)
    plt.figure(figsize=(14, 10))
    ax = plt.gca()


    for shape in unique_shapes:
        shape_nodes = [node for node in G.nodes() if node_shapes[node] == shape]
        nx.draw_networkx_nodes(
            G,
            pos,
            nodelist=shape_nodes,
            node_color=[node_colors[node] for node in shape_nodes],
            node_size=[node_sizes[node] for node in shape_nodes],
            node_shape=shape,
            alpha=0.9,
            edgecolors="black",
            linewidths=2,
            ax=ax,
        )

    nx.draw_networkx_edges(
        G,
        pos,
        edge_color="black",
        arrowsize=30,
        width=3,
        arrowstyle="-|>",
        connectionstyle="arc3,rad=0",
        min_source_margin=20,
        min_target_margin=30,
        ax=ax,
    )

    nx.draw_networkx_labels(
        G,
        pos,
        labels={node: node for node in G.nodes()},
        font_size=12,
        font_weight="bold",
        bbox=dict(facecolor="white", edgecolor="black", boxstyle="round,pad=0.5"),
        ax=ax,
    )

    for node in G.nodes():
        icon_path = node_icons[node]
        if icon_path and os.path.exists(icon_path):
            image = plt.imread(icon_path)
            imagebox = OffsetImage(image, zoom=0.15)
            ab = AnnotationBbox(
                imagebox, pos[node], frameon=False, box_alignment=(0.5, 0.5)
            )
            ax.add_artist(ab)

    plt.title("Custom Graph with Shapes and Icons", fontsize=18, fontweight="bold")
    plt.axis("off")
    plt.show()


# Example usage:

node_array: List[List[NodeAttributes]] = [
    [
        {
            "label": "Foundation Models",
            "size": 3000,
            "color": "orange",
            "shape": "s",
        },
        {
            "label": "Networking and AI Infrastructure",
            "size": 3000,
            "color": "lightcoral",
            "shape": "^",
        },
        {
            "label": "SDKs",
            "size": 3000,
            "color": "violet",
            "shape": "D",
            "icon": "icons/sdk.png",
        },
        {
            "label": "Hardware Manufacturers",
            "size": 3000,
            "color": "lightgreen",
            "shape": "o",
        },
    ],
    [
        {
            "label": "Integrators",
            "size": 5000,
            "color": "lightblue",
            "shape": "o",
        }
    ],
]

edge_list = [
    ("Foundation Models", "Networking and AI Infrastructure"),
    ("Foundation Models", "SDKs"),
    ("Hardware Manufacturers", "Integrators"),
    ("Networking and AI Infrastructure", "Integrators"),
    ("SDKs", "Integrators"),
]

draw_graph(node_array, edge_list)
