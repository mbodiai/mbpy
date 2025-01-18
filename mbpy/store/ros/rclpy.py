import importlib
import inspect
import json
import pkgutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Type, get_type_hints

import rclpy
from typing_extensions import get_args, get_origin


@dataclass
class SchemaContext:
    """Context for schema generation to track dependencies and references"""

    processed_types: set
    type_references: dict
    message_types: dict
    service_types: dict
    action_types: dict


def get_type_info(typ: Type, context: SchemaContext) -> Dict[str, Any]:
    """Enhanced type information extraction"""
    if typ in context.processed_types:
        return {"$ref": f"#/types/{typ.__name__}"}

    context.processed_types.add(typ)

    # Handle ROS special types
    if hasattr(typ, "_fields_and_field_types"):
        return get_message_info(typ, context)

    # Handle enums
    if isinstance(typ, type) and issubclass(typ, Enum):
        return {"type": "enum", "values": {e.name: e.value for e in typ}}

    # Handle generic types
    origin = get_origin(typ)
    if origin is not None:
        args = get_args(typ)
        return {"type": str(origin), "arguments": [get_type_info(arg, context) for arg in args]}

    # Basic type
    return {"type": typ.__name__}


def get_message_info(msg_type, context: SchemaContext) -> Dict[str, Any]:
    """Enhanced message definition extraction"""
    fields_and_types = msg_type.get_fields_and_field_types()

    return {
        "type": "message",
        "package": msg_type.__module__.split(".")[0],
        "fields": {
            field: {"type": get_type_info(field_type, context), "default": getattr(msg_type(), field)}
            for field, field_type in fields_and_types.items()
        },
        "constants": {name: value for name, value in msg_type.__dict__.items() if name.isupper()},
    }


def get_class_info(cls: Type, context: SchemaContext) -> Dict[str, Any]:
    """Enhanced class information extraction"""
    class_info = {
        "type": "class",
        "bases": [base.__name__ for base in cls.__bases__],
        "methods": {},
        "properties": {},
        "doc": cls.__doc__,
        "type_hints": {},
    }

    # Get type hints
    try:
        hints = get_type_hints(cls)
        class_info["type_hints"] = {name: get_type_info(typ, context) for name, typ in hints.items()}
    except Exception:
        pass

    # Get methods with enhanced signature info
    for name, member in inspect.getmembers(cls):
        if name.startswith("_"):
            continue

        if inspect.isfunction(member) or inspect.ismethod(member):
            try:
                sig = inspect.signature(member)
                class_info["methods"][name] = {
                    "signature": str(sig),
                    "parameters": {
                        param.name: {
                            "kind": str(param.kind),
                            "default": str(param.default) if param.default is not inspect.Parameter.empty else None,
                            "annotation": str(param.annotation)
                            if param.annotation is not inspect.Parameter.empty
                            else None,
                        }
                        for param in sig.parameters.values()
                    },
                    "return_annotation": str(sig.return_annotation)
                    if sig.return_annotation is not inspect.Parameter.empty
                    else None,
                    "doc": member.__doc__,
                }
            except ValueError:
                continue

        elif isinstance(member, property):
            class_info["properties"][name] = {
                "doc": member.__doc__,
                "type": get_type_info(member.fget.__annotations__.get("return", Any), context)
                if hasattr(member.fget, "__annotations__")
                else None,
            }

    return class_info


def get_module_info(module, context: SchemaContext) -> Dict[str, Any]:
    """Enhanced module information extraction"""
    module_info = {"type": "module", "classes": {}, "submodules": {}, "constants": {}, "doc": module.__doc__}

    # Get constants
    for name, member in inspect.getmembers(module):
        if name.isupper() and not inspect.ismodule(member) and not inspect.isclass(member):
            module_info["constants"][name] = str(member)

    # Get classes with inheritance
    for name, member in inspect.getmembers(module):
        if name.startswith("_"):
            continue

        if inspect.isclass(member) and member.__module__ == module.__name__:
            module_info["classes"][name] = get_class_info(member, context)

    return module_info


def generate_schema():
    """Generate enhanced schema for rclpy"""
    context = SchemaContext(
        processed_types=set(), type_references={}, message_types={}, service_types={}, action_types={}
    )

    schema = {
        "name": "rclpy",
        "version": rclpy.__version__,
        "modules": {},
        "types": context.type_references,
        "messages": context.message_types,
        "services": context.service_types,
        "actions": context.action_types,
    }

    # Process all submodules
    package = rclpy
    for _, name, _ in pkgutil.iter_modules(package.__path__):
        full_name = f"{package.__name__}.{name}"
        try:
            module = importlib.import_module(full_name)
            schema["modules"][name] = get_module_info(module, context)
        except ImportError as e:
            print(f"Could not import {full_name}: {e}")

    # Add core module info
    schema["modules"]["core"] = get_module_info(rclpy, context)

    return schema


if __name__ == "__main__":
    schema = generate_schema()

    # Save schema with pretty printing
    output_path = Path("rclpy_schema.json")
    with output_path.open("w") as f:
        json.dump(schema, f, indent=2)

    print(f"Enhanced schema generated at: {output_path.absolute()}")
