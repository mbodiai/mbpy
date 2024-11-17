# generate_pydantic_models.py

from importlib.resources import files
import json
import os
from pathlib import Path
import re
import traceback
from typing import Any, Dict, List, Optional, Set, Tuple, Type


from pydantic import BaseModel, create_model

from mbpy.context import suppress


# Mapping from JSON Schema types/formats to Python/Pydantic types
FORMAT_TYPE_MAPPING = {
    "email": "EmailStr",
    "uri": "AnyUrl",
    "date-time": "datetime",
    "uuid": "UUID",
    "ipv4": "IPv4Address",
    "ipv6": "IPv6Address",
    # Add more format mappings as needed
}

TYPE_IMPORTS = {
    "EmailStr": "from pydantic import EmailStr",
    "AnyUrl": "from pydantic import AnyUrl",
    "datetime": "from datetime import datetime",
    "UUID": "from uuid import UUID",
    "IPv4Address": "from ipaddress import IPv4Address",
    "IPv6Address": "from ipaddress import IPv6Address",
    "List": "from typing import List",
    "Optional": "from typing import Optional",
    "Dict": "from typing import Dict",
    "Union": "from typing import Union",
    "Any": "from typing import Any",
}

# Set of basic types that don't require imports
BASIC_TYPES = {"str", "int", "float", "bool", "Any"}


def camel_case(name: str) -> str:
    """Convert snake_case to CamelCase."""
    return "".join(word.title() for word in name.split("_"))

def snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    return "".join(["_" + c.lower() if c.isupper() else c for c in name]).lstrip("_")

def parse_schema(name: str, schema: Dict[str, Any], models: Dict[str, Dict[str, Any]], processed: list[str]) -> None:
    """
    Recursively parse JSON Schema and populate models dictionary.
    """
    model_name = camel_case(name)
    if model_name in processed:
        return
    processed.append(model_name)

    properties = schema.get("properties", {})
    required = schema.get("required", [])
    fields = {}
    for prop, details in properties.items():
        field_name = prop
        field_required = prop in required
        field_type, imports = get_field_type(prop, details, models, processed)
        fields[field_name] = {"type": field_type, "required": field_required, "imports": imports}
    models[model_name] = fields

import json
import traceback
from pathlib import Path
from contextlib import suppress
from typing import Any, Dict, Set, Tuple

# Set of basic types that don't require imports
BASIC_TYPES = {"str", "int", "float", "bool", "Any"}


def camel_case(name: str) -> str:
    """Convert snake_case to CamelCase."""
    return "".join(word.title() for word in name.split("_"))


def snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    return "".join(["_" + c.lower() if c.isupper() else c for c in name]).lstrip("_")


def parse_schema(name: str, schema: Dict[str, Any], models: Dict[str, Dict[str, Any]], processed: list[str]) -> None:
    """
    Recursively parse JSON Schema and populate models dictionary.
    """
    model_name = camel_case(name)
    if model_name in processed:
        return
    processed.append(model_name)

    properties = schema.get("properties", {})
    required = schema.get("required", [])
    fields = {}
    for prop, details in properties.items():
        field_name = prop
        field_required = prop in required
        field_type, imports = get_field_type(prop, details, models, processed)
        fields[field_name] = {"type": field_type, "required": field_required, "imports": imports}
    models[model_name] = fields


def get_field_type(
    prop: str, details: Dict[str, Any], models: Dict[str, Dict[str, Any]], processed: list[str]
) -> Tuple[str, Set[str]]:
    """Determine the Python type for a given JSON Schema property.
    Returns the type as a string and a set of required imports.
    """
    imports = set()
    json_type = details.get("type", "Any")
    if "$ref" in details:
        ref = details["$ref"]
        ref_name = ref.split("/")[-1]
        type_name = camel_case(ref_name)
        imports.add(type_name)
        parse_schema(ref_name, details, models, processed)
        return type_name, imports

    if json_type == "array":
        items = details.get("items", {})
        item_type, item_imports = get_field_type(prop, items, models, processed)
        imports.update(item_imports)
        imports.add("List")
        return f"List[{item_type}]", imports

    if json_type == "object":
        type_name = camel_case(prop)
        parse_schema(prop, details, models, processed)
        imports.add(type_name)
        return type_name, imports

    # Map JSON types to Python types
    type_mapping = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "object": "dict",
        "any": "Any",
    }
    python_type = type_mapping.get(json_type, "Any")
    return python_type, imports


def generate_model_code(models: Dict[str, Dict[str, Any]]) -> str:
    lines = ["from pydantic import BaseModel", "from typing import List, Optional, Any", ""]
    for model_name, fields in models.items():
        lines.append(f"class {model_name}(BaseModel):")
        if not fields:
            lines.append("    pass\n")
            continue
        for field_name, attributes in fields.items():
            field_type = attributes["type"]
            required = attributes["required"]
            if not required:
                field_type = f"Optional[{field_type}]"
                default = " = None"
            else:
                default = ""
            lines.append(f"    {field_name}: {field_type}{default}")
        lines.append("")
    return "\n".join(lines)


template = """"
{% for model in models %}
class {{ model.name }}(BaseModel):
    {% for field in model.fields %}
    {{ field.name }}: {{ field.type }}{% if field.optional %} = None{% endif %}
    {% endfor %}

{% endfor %}"""


def parse_schema(name: str, schema: Dict[str, Any], models: Dict[str, Dict[str, Any]], processed: list[str]) -> None:
    model_name = camel_case(name)
    if model_name in processed:
        return
    processed.append(model_name)

    properties = schema.get("properties", {})
    required = schema.get("required", [])
    fields = {}
    print(f"Parsing model: {model_name}")  # Debug statement
    for prop, details in properties.items():
        field_name = prop
        field_required = prop in required
        field_type, imports = get_field_type(prop, details, models, processed)
        print(f"  Field: {field_name}, Type: {field_type}, Required: {field_required}")  # Debug
        fields[field_name] = {"type": field_type, "required": field_required, "imports": imports}
    models[model_name] = fields
def main():
    schema_path = Path("mbpy/store/schema/hatch.json")
    output_path = Path("generated_models.py")

    if not schema_path.exists():
        print(f"Schema file {schema_path} does not exist.")
        return

    try:
        schema_text = schema_path.read_text()
    except Exception as e:
        print(f"Error reading schema file: {e}")
        traceback.print_exc()
        return

    try:
        schema = json.loads(schema_text)
    except json.JSONDecodeError as decode_error:
        print(f"JSONDecodeError: {decode_error}")
        traceback.print_exc()
        return
    except Exception as ex:
        print(f"Unexpected error: {ex}")
        traceback.print_exc()
        return

    models = {}
    processed = []

    try:
        for prop, details in schema.get("properties", {}).items():
            parse_schema(prop, details, models, processed)
    except Exception as e:
        print(f"Error parsing schema: {e}")
        traceback.print_exc()

    try:
        model_code = generate_model_code(models)
    except Exception as e:
        print(f"Error generating model code: {e}")
        traceback.print_exc()
        return

    try:
        with output_path.open("w") as f:
            f.write(model_code)
        print(f"Models successfully generated in {output_path}")
    except Exception as e:
        print(f"Error writing to output file: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()