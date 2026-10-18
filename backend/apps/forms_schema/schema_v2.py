"""Closed form-v2 editor schema, independent of any admission workflow."""
import math
import re
from copy import deepcopy
from django.core.exceptions import ValidationError
from .conditions import validate_condition
from .profile_fields import ProfileValueError, compatible_question

QUESTION_TYPES = (
    "short_text", "long_text", "number", "date", "date_of_birth", "single_choice",
    "multi_choice", "yes_no", "email", "phone", "url", "asset_reference",
    "age_at_event", "emergency_contact",
)
CHOICES = {"single_choice", "multi_choice"}
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_KEYS = {"id", "type", "label", "required", "help", "placeholder", "options", "bounds",
         "show_if", "disclosure", "profile_field_key", "visibility"}
_BOUNDS = {"min_length", "max_length", "min", "max", "min_selections", "max_selections", "other_max_length"}


def fail(message, code="invalid_form_schema"):
    raise ValidationError(message, code=code)


def label(value, maximum=200, *, blank=False):
    if not isinstance(value, str) or len(value.strip()) > maximum or (not blank and not value.strip()):
        fail(f"Use {'0' if blank else '1'}–{maximum} characters.")
    return value.strip()


def _bounds(raw, kind):
    if not isinstance(raw, dict) or set(raw) - _BOUNDS:
        fail("Unknown bounds.")
    allowed = {"number": {"min", "max"}, "multi_choice": {"min_selections", "max_selections", "other_max_length"},
               "single_choice": {"other_max_length"}, "short_text": {"min_length", "max_length"},
               "long_text": {"min_length", "max_length"}, "email": {"max_length"}, "phone": {"max_length"},
               "url": {"max_length"}}.get(kind, set())
    if raw and kind in {"age_at_event", "date_of_birth"}:
        fail("Age limits are not supported.", "age_gating_forbidden")
    if set(raw) - allowed:
        fail("Bounds do not apply to this question type.")
    for key, value in raw.items():
        if key in {"min", "max"}:
            try:
                finite = type(value) in (int, float) and math.isfinite(value)
            except OverflowError:
                finite = False
            if not finite:
                fail("Number bounds must be finite.")
        elif type(value) is not int or value < 0 or value > (50 if "selections" in key else 5000):
            fail("Invalid question bound.")
    for low, high in (("min", "max"), ("min_length", "max_length"), ("min_selections", "max_selections")):
        if low in raw and high in raw and raw[low] > raw[high]:
            fail("Minimum exceeds maximum.")
    return dict(raw)


def _options(raw, kind):
    if not isinstance(raw, list):
        fail("Options must be an array.")
    if kind not in CHOICES:
        if raw:
            fail("Only choice questions have options.")
        return []
    if not isinstance(raw, list) or not 1 <= len(raw) <= 50:
        fail("Use 1–50 options.")
    seen, result, other = set(), [], False
    for option in raw:
        if not isinstance(option, dict) or not {"id", "label"} <= set(option) or set(option) - {"id", "label", "other"}:
            fail("An option needs an ID and label.")
        oid = option["id"]
        if not isinstance(oid, str) or not _ID.fullmatch(oid) or oid in seen:
            fail("Use unique stable option IDs.")
        if "other" in option and type(option["other"]) is not bool:
            fail("other must be boolean.")
        if option.get("other") and other:
            fail("Only one Other option is allowed.")
        other |= option.get("other", False)
        seen.add(oid)
        result.append({**option, "label": label(option["label"])})
    return result


def _question(raw, earlier):
    if not isinstance(raw, dict) or set(raw) - _KEYS or not {"id", "type", "label", "required"} <= set(raw):
        fail("Unknown or missing question keys.")
    qid, kind = raw["id"], raw["type"]
    if not isinstance(qid, str) or not _ID.fullmatch(qid) or qid in earlier:
        fail("Use unique stable question IDs.")
    if not isinstance(kind, str) or kind not in QUESTION_TYPES or type(raw["required"]) is not bool:
        fail("Invalid question type or required flag.")
    result = {**deepcopy(raw), "label": label(raw["label"])}
    for key in ("help", "placeholder"):
        if key in raw:
            result[key] = label(raw[key], 1000 if key == "help" else 200, blank=True)
    result["bounds"] = _bounds(raw.get("bounds", {}), kind)
    options = _options(raw.get("options", []), kind)
    if kind in CHOICES:
        result["options"] = options
        if result["bounds"].get("max_selections", len(options)) > len(options):
            fail("Selection count exceeds available options.")
        if result["bounds"].get("min_selections", 0) > len(options):
            fail("Selection count exceeds available options.")
    if "show_if" in raw:
        result["show_if"] = validate_condition(raw["show_if"], earlier)
    disclosure = raw.get("disclosure", {"organizer": True, "reviewer": False, "judge": False})
    if (not isinstance(disclosure, dict) or set(disclosure) != {"organizer", "reviewer", "judge"}
            or any(type(value) is not bool for value in disclosure.values())):
        fail("Use explicit organizer/reviewer/judge disclosure flags.")
    result["disclosure"] = dict(disclosure)
    if not isinstance(raw.get("visibility", "member"), str) or raw.get("visibility", "member") not in {"member", "server"}:
        fail("Unsupported question visibility.")
    if "profile_field_key" in raw:
        try:
            compatible = compatible_question(raw["profile_field_key"], kind)
        except ProfileValueError:
            compatible = False
        if not compatible or raw.get("visibility") == "server":
            fail("Incompatible profile key mapping.", "invalid_profile_mapping")
    if kind == "age_at_event" and raw.get("profile_field_key", "age_at_event") != "age_at_event":
        fail("Derived age cannot map to a stored profile value.", "invalid_profile_mapping")
    return result


def validate_schema(raw):
    if not isinstance(raw, dict) or set(raw) - {"schema_version", "form_id", "revision", "questions", "event_context"}:
        fail("Unknown form keys.")
    if type(raw.get("schema_version")) is not int or raw["schema_version"] != 2:
        fail("Use schema_version 2.")
    if not isinstance(raw.get("form_id"), str) or not _ID.fullmatch(raw["form_id"]):
        fail("Invalid form ID.")
    if type(raw.get("revision")) is not int or raw["revision"] < 1:
        fail("Use a positive form revision.")
    questions = raw.get("questions")
    if not isinstance(questions, list) or len(questions) > 50:
        fail("Use at most 50 questions.")
    earlier = {}
    for question in questions:
        canonical = _question(question, earlier)
        earlier[canonical["id"]] = canonical
    result = {**deepcopy(raw), "questions": list(earlier.values())}
    # event_context is descriptive. Domain providers load and bind current values.
    if "event_context" in raw:
        ctx = raw["event_context"]
        if not isinstance(ctx, dict) or set(ctx) != {"event_id", "event_date_revision", "timezone_name", "as_of_date"}:
            fail("Invalid event context.")
        if any(type(ctx[key]) is not int or ctx[key] < 1 for key in ("event_id", "event_date_revision")):
            fail("Invalid event context revision.")
        from datetime import date
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            date.fromisoformat(ctx["as_of_date"])
            ZoneInfo(ctx["timezone_name"])
        except (TypeError, ValueError, ZoneInfoNotFoundError):
            fail("Invalid event-local date or timezone.")
    return result
