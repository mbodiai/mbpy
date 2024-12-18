import json
import traceback
from pathlib import Path
from typing import Any, Dict, Set, Tuple

BASIC_TYPES = {"str", "int", "float", "bool", "Any"}

def camel_case(name: str) -> str:
    return "".join(word.title() for word in name.replace('-', '_').split("_"))

def resolve_ref(ref: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    parts = ref.lstrip("#/").split("/")
    ref_schema = schema
    for part in parts:
        ref_schema = ref_schema.get(part, {})
    return ref_schema

def parse_schema(name: str, schema: Dict[str, Any], models: Dict[str, Dict[str, Any]], processed: Set[str], root_schema: Dict[str, Any]) -> None:
    model_name = camel_case(name)
    if model_name in processed:
        return
    processed.add(model_name)

    properties = schema.get("properties", {})
    required = schema.get("required", [])
    fields = {}
    for prop, details in properties.items():
        field_name = prop
        field_required = prop in required
        field_type, imports = get_field_type(prop, details, models, processed, root_schema)
        fields[field_name] = {"type": field_type, "required": field_required, "imports": imports}
    models[model_name] = fields

def get_field_type(prop: str, details: Dict[str, Any], models: Dict[str, Dict[str, Any]], processed: Set[str], root_schema: Dict[str, Any]) -> Tuple[str, Set[str]]:
    imports = set()
    if "$ref" in details:
        ref = details["$ref"]
        ref_schema = resolve_ref(ref, root_schema)
        ref_name = ref.split("/")[-1]
        type_name = camel_case(ref_name)
        imports.add(type_name)
        parse_schema(ref_name, ref_schema, models, processed, root_schema)
        return type_name, imports

    json_type = details.get("type", "Any")

    if json_type == "array":
        items = details.get("items", {})
        item_type, item_imports = get_field_type(prop, items, models, processed, root_schema)
        imports.update(item_imports)
        imports.add("List")
        return f"List[{item_type}]", imports

    if json_type == "object":
        type_name = camel_case(prop)
        parse_schema(prop, details, models, processed, root_schema)
        imports.add(type_name)
        return type_name, imports

    type_mapping = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "object": "Dict[str, Any]",
        "any": "Any",
    }
    python_type = type_mapping.get(json_type, "Any")
    return python_type, imports

def generate_model_code(models: Dict[str, Dict[str, Any]]) -> str:
    all_imports = {"from pydantic import BaseModel", "from typing import List, Optional, Any, Dict"}
    for fields in models.values():
        for field in fields.values():
            all_imports.update(field["imports"])

    import_lines = sorted(all_imports)
    lines = import_lines + ["", ""]
    
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

def main() -> None:
    schema_path = Path("mbpy/store/schema/hatch.json")
    output_path = Path("generated_models.py")

    if not schema_path.exists():
        return

    try:
        schema_text = schema_path.read_text()
    except Exception:
        traceback.print_exc()
        return

    try:
        schema = json.loads(schema_text)
    except json.JSONDecodeError:
        traceback.print_exc()
        return
    except Exception:
        traceback.print_exc()
        return

    models = {}
    processed = set()

    try:
        for _prop, details in schema.get("properties", {}).items():
            if "$ref" in details:
                ref = details["$ref"]
                ref_schema = resolve_ref(ref, schema)
                ref_name = ref.split("/")[-1]
                parse_schema(ref_name, ref_schema, models, processed, schema)
    except Exception:
        traceback.print_exc()

    try:
        model_code = generate_model_code(models)
    except Exception:
        traceback.print_exc()
        return

    try:
        with output_path.open("w") as f:
            f.write(model_code)
    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    main()