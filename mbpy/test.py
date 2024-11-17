from typing import Any, get_type_hints, Dict, Tuple, Type
from inspect import Signature, Parameter


class TypedDataClassMeta(type):
    def __new__(metacls, name, bases, namespace):
        # Create the class as usual
        cls = super().__new__(metacls, name, bases, namespace)

        # Skip base class
        if name == "TypedDataClass":
            return cls

        # Get type hints from the class
        type_hints = get_type_hints(cls)

        # Build parameters for the __init__ method
        params = []

        for field_name, field_type in type_hints.items():
            default = namespace.get(field_name, Parameter.empty)
            params.append(
                Parameter(
                    field_name,
                    Parameter.POSITIONAL_OR_KEYWORD,
                    default=default,
                    annotation=field_type,
                )
            )

        # Create the signature
        sig = Signature(params)

        # Define the __init__ method
        def __init__(self, *args, **kwargs):
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            for name, value in bound.arguments.items():
                setattr(self, name, value)

        # Assign the signature to __init__
        __init__.__signature__ = sig
        __init__.__annotations__ = {k: v.annotation for k, v in sig.parameters.items()}
        cls.__init__ = __init__

        return cls


class TypedDataClass(metaclass=TypedDataClassMeta):
    pass


# User-defined class
class GraphicSettings(TypedDataClass):
    label: str = "Node"
    size: int = 100
    color: str = "orange"
    shape: str = "o"
    icon: str = ""
    pos: Dict[str, int] = {"x": 0, "y": 0}


# Example usage with positional arguments
settings_positional = GraphicSettings(
    "Custom Node", 150, "blue", "s", "star", {"x": 10, "y": 20}
)

# Example usage with keyword arguments
settings_keyword = GraphicSettings(
    label="Custom Node",
    size=150,
    color="blue",
    shape="s",
    icon="star",
    pos={"x": 10, "y": 20},
)

print(settings_positional)
print(settings_keyword)
