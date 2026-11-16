"""Closed event-specific travel values, never Saved details."""
import re
from datetime import datetime, timezone
from .profile_fields import ProfileValueError, text

MODES = ("rail", "air", "bus", "car", "other")


def itinerary_schema(raw):
    if (not isinstance(raw, dict) or set(raw) != {"modes"} or not isinstance(raw["modes"], list)
            or not raw["modes"] or any(not isinstance(mode, str) or mode not in MODES for mode in raw["modes"])
            or len(raw["modes"]) != len(set(raw["modes"]))):
        raise ProfileValueError("Select unique supported travel modes.")
    return {"modes": list(raw["modes"])}


def _instant(value):
    if not isinstance(value, str) or len(value) > 40 or not re.match(r"^\d{4}-\d{2}-\d{2}T", value):
        raise ProfileValueError("Use an ISO datetime with a timezone offset.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise ProfileValueError("Use an ISO datetime with a timezone offset.") from None


def normalize_itinerary(question, value):
    keys = {"mode", "origin", "destination", "depart_at", "arrive_at"}
    if not isinstance(value, dict) or set(value) - keys or "mode" not in value:
        raise ProfileValueError("Use the configured itinerary fields.")
    if not isinstance(value["mode"], str) or value["mode"] not in question["itinerary"]["modes"]:
        raise ProfileValueError("Select a configured travel mode.")
    result, instants, errors = {"mode": value["mode"]}, {}, {}
    # Missing or null optional fields mean unknown; blank strings are invalid.
    for key in keys - {"mode"}:
        item = value.get(key)
        try:
            if item is None:
                result[key] = None
            elif key in {"origin", "destination"}:
                result[key] = text(item, 200)
            else:
                instants[key] = _instant(item)
                result[key] = instants[key].isoformat().replace("+00:00", "Z")
        except ProfileValueError as exc:
            errors[key] = [str(exc)]
    if len(instants) == 2 and instants["arrive_at"] < instants["depart_at"]:
        errors["arrive_at"] = ["Arrival must be on or after departure."]
    if errors:
        raise ProfileValueError("Check the journey details.", fields=errors)
    return result
