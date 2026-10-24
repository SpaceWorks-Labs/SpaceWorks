"""Primitive answer normalization. No workflow, profile write or key access."""
import re
from datetime import date
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from .legacy import _canonical_number
from .profile_fields import (
    ProfileValueError, emergency_contact, https_url, normalize_dob,
    normalize_phone, normalize_profile_value, text,
)


def unanswered(value):
    return value is None or (isinstance(value, str) and not value.strip())


def choice_answer(question, raw):
    multi = question["type"] == "multi_choice"
    text_key = "other_text" if multi else "text"
    keys = {"option_ids", text_key} if multi else {"option_id", text_key}
    if not isinstance(raw, dict) or set(raw) - keys or ("option_ids" if multi else "option_id") not in raw:
        raise ProfileValueError("Use stable option IDs.")
    selected = raw["option_ids"] if multi else [raw["option_id"]]
    options = {item["id"]: item for item in question["options"]}
    if (not isinstance(selected, list) or any(not isinstance(item, str) for item in selected)
            or len(selected) != len(set(selected)) or any(item not in options for item in selected)):
        raise ProfileValueError("Select configured options without duplicates.")
    bounds = question["bounds"]
    if multi and not bounds.get("min_selections", 0) <= len(selected) <= bounds.get("max_selections", len(options)):
        raise ProfileValueError("Selection count is outside the allowed range.")
    other = any(options[item].get("other", False) for item in selected)
    result = {"option_ids": [key for key in options if key in selected]} if multi else {"option_id": selected[0]}
    if other:
        result[text_key] = text(raw.get(text_key), bounds.get("other_max_length", 300))
    elif text_key in raw:
        raise ProfileValueError("Other text needs the Other option.")
    return result


def normalize_answer(question, value):
    kind, bounds = question["type"], question["bounds"]
    if kind == "money":
        from .money_values import normalize_money
        return normalize_money(question, value)
    if kind == "file":
        from .file_values import normalize_files
        return normalize_files(question, value)
    if kind == "itinerary":
        from .itinerary_values import normalize_itinerary
        return normalize_itinerary(question, value)
    if kind in {"short_text", "long_text", "email", "phone", "url"}:
        maximum = {"short_text": 500, "long_text": 5000, "email": 254, "phone": 32, "url": 2048}[kind]
        value = text(value, min(maximum, bounds.get("max_length", maximum)))
        if len(value) < bounds.get("min_length", 0):
            raise ProfileValueError("Answer is too short.")
        if kind == "email":
            try:
                validate_email(value)
            except ValidationError:
                raise ProfileValueError("Enter a valid email.") from None
        if kind == "phone":
            value = normalize_phone(value)
        if kind == "url":
            value = https_url(value)
        return value
    if kind == "number":
        try:
            value = _canonical_number(value)
        except ValueError:
            raise ProfileValueError("Enter a finite number.") from None
        if ("min" in bounds and value < bounds["min"]) or ("max" in bounds and value > bounds["max"]):
            raise ProfileValueError("Number is outside the allowed range.")
        return value
    if kind in {"date", "date_of_birth"}:
        if kind == "date_of_birth":
            return normalize_dob(value)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ProfileValueError("Use YYYY-MM-DD.")
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            raise ProfileValueError("Enter a valid calendar date.") from None
    if kind == "yes_no":
        if type(value) is not bool:
            raise ProfileValueError("Use a JSON boolean.")
        return value
    if kind in {"single_choice", "multi_choice"}:
        return choice_answer(question, value)
    if kind == "emergency_contact":
        return emergency_contact(value)
    if kind == "asset_reference":
        return normalize_profile_value("resume", value)
    raise ProfileValueError("Derived values must use derivations.")
