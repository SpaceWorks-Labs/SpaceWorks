"""A tiny JSON Schema validator for the subset the adapter contract uses.

Supported keywords: type (object, array, string, integer, number, boolean, null or a list),
properties, required, additionalProperties (bool), items, enum, minimum, maximum, minLength,
maxLength, maxItems, minItems, format "uuid". The same dicts are exported as the published
``docs/device-adapters/schemas/*.json`` files, so the docs and the runtime cannot drift.
"""
import re
import uuid

_TYPES = {
    "object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str), "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool), "null": lambda v: v is None,
}
_CODE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,47}$")


def errors(schema, value, path="$"):
    """Every violation as ``"path: message"`` (empty list = valid). Messages never echo values."""
    out = []
    kinds = schema.get("type")
    if kinds is not None:
        kinds = [kinds] if isinstance(kinds, str) else kinds
        if not any(_TYPES[kind](value) for kind in kinds):
            return [f"{path}: expected {'/'.join(kinds)}"]
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{path}: not an allowed value")
    if isinstance(value, bool):
        return out
    if isinstance(value, (int, float)):
        if "minimum" in schema and value < schema["minimum"]:
            out.append(f"{path}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            out.append(f"{path}: above maximum")
    elif isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 10 ** 6):
            out.append(f"{path}: wrong length")
        if schema.get("format") == "uuid":
            try:
                uuid.UUID(value)
            except ValueError:
                out.append(f"{path}: not a uuid")
        if schema.get("format") == "code" and not _CODE.match(value):
            out.append(f"{path}: not a code")
    elif isinstance(value, list):
        if len(value) > schema.get("maxItems", 10 ** 6) or len(value) < schema.get("minItems", 0):
            out.append(f"{path}: wrong item count")
        if "items" in schema:
            for index, item in enumerate(value):
                out += errors(schema["items"], item, f"{path}[{index}]")
    elif isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", ()):
            if key not in value:
                out.append(f"{path}.{key}: required")
        for key, item in value.items():
            if key in props:
                out += errors(props[key], item, f"{path}.{key}")
            elif "additionalProperties" in schema and isinstance(schema["additionalProperties"], dict):
                out += errors(schema["additionalProperties"], item, f"{path}.{key}")
            elif schema.get("additionalProperties", True) is False:
                out.append(f"{path}.{key}: unknown field")
    return out


def obj(props, required=(), *, extra=False):
    return {"type": "object", "properties": props, "required": list(required), "additionalProperties": extra}


def text(limit=120, **extra):
    return {"type": "string", "maxLength": limit, **extra}


def num(minimum=None, maximum=None, kind="number"):
    out = {"type": kind}
    if minimum is not None:
        out["minimum"] = minimum
    if maximum is not None:
        out["maximum"] = maximum
    return out


UUID = {"type": "string", "format": "uuid", "maxLength": 36, "minLength": 36}
EPOCH = num(0, 4102444800, "integer")
PERCENT = num(0, 100, "integer")
CODE = {"type": "string", "format": "code", "maxLength": 48}
