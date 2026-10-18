"""Closed request schemas shared by spectacular and lane contract fixtures."""
from copy import deepcopy
from .profile_fields import PROFILE_FIELDS
from .schema_v2 import QUESTION_TYPES

_ID = {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,64}$"}


def obj(properties, required=()):
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(required)}


def condition(depth=1):
    primitive = {"oneOf": [{"type": "string", "maxLength": 5000}, {"type": "number"}, {"type": "boolean"}]}
    leaf = obj({"field_id": _ID, "op": {"enum": ["eq", "ne", "in", "contains", "is_set"]},
                "value": {"oneOf": [primitive, {"type": "array", "minItems": 1,
                    "maxItems": 50, "items": primitive}]}}, ("field_id", "op"))
    choices = [leaf]
    if depth < 3:
        children = {"type": "array", "minItems": 1, "maxItems": 20, "items": condition(depth + 1)}
        choices += [obj({key: children}, (key,)) for key in ("all", "any")]
    return {"oneOf": choices}


BOUNDS = obj({**{key: {"type": "integer", "minimum": 0, "maximum": 5000}
    for key in ("min_length", "max_length", "other_max_length")},
    **{key: {"type": "integer", "minimum": 0, "maximum": 50} for key in ("min_selections", "max_selections")},
    "min": {"type": "number"}, "max": {"type": "number"}})
QUESTION = obj({
    "id": _ID, "label": {"type": "string", "minLength": 1, "maxLength": 200},
    "type": {"type": "string", "enum": list(QUESTION_TYPES)}, "required": {"type": "boolean"},
    "help": {"type": "string", "maxLength": 1000}, "placeholder": {"type": "string", "maxLength": 200},
    "options": {"type": "array", "maxItems": 50, "items": obj({"id": _ID,
        "label": {"type": "string", "minLength": 1, "maxLength": 200}, "other": {"type": "boolean"}}, ("id", "label"))},
    "bounds": BOUNDS, "show_if": condition(), "profile_field_key": {"type": "string", "enum": list(PROFILE_FIELDS)},
    "visibility": {"type": "string", "enum": ["member", "server"]},
    "disclosure": obj({key: {"type": "boolean"} for key in ("organizer", "reviewer", "judge")},
                      ("organizer", "reviewer", "judge")),
}, ("id", "label", "type", "required"))
FORM_V2_SCHEMA = obj({
    "schema_version": {"type": "integer", "enum": [2]}, "form_id": _ID,
    "revision": {"type": "integer", "minimum": 1},
    "questions": {"type": "array", "maxItems": 50, "items": QUESTION},
    "event_context": obj({"event_id": {"type": "integer", "minimum": 1},
        "event_date_revision": {"type": "integer", "minimum": 1},
        "timezone_name": {"type": "string", "maxLength": 64}, "as_of_date": {"type": "string", "format": "date"}},
        ("event_id", "event_date_revision", "timezone_name", "as_of_date")),
}, ("schema_version", "form_id", "revision", "questions"))
FORM_V1_SCHEMA = {"type": "array", "maxItems": 50, "items": obj({
    "id": _ID, "label": {"type": "string", "maxLength": 200},
    "type": {"type": "string", "enum": ["short_text", "paragraph", "number", "date", "single_choice", "multi_choice", "dropdown", "yes_no"]},
    "required": {"type": "boolean"}, "options": {"type": "array", "maxItems": 50,
        "items": {"type": "string", "minLength": 1, "maxLength": 200}},
}, ("id", "label", "type", "required", "options"))}
VERSIONED_FORM_SCHEMA = {"oneOf": [FORM_V1_SCHEMA, FORM_V2_SCHEMA], "nullable": True}
FORM_V2_EDITOR_SCHEMA = deepcopy(FORM_V2_SCHEMA)
del FORM_V2_EDITOR_SCHEMA["properties"]["event_context"]
EDITOR_FORM_SCHEMA = {"oneOf": [FORM_V1_SCHEMA, FORM_V2_EDITOR_SCHEMA], "nullable": True}


def versioned_form_schema():
    return deepcopy(VERSIONED_FORM_SCHEMA)
