"""Badge design files (E-B1): export, and import with the SpaceWorks-Events kinds accepted as-is.

A file is `{"kind", "version", "settings"}`. SpaceWorks writes `spaceworks-event-badge` v1; it reads that,
`swe-id-card-design` (Events, any version) and `yuyu-id-card-design` (the Events name before its rename)
exactly as Events wrote them: the settings are the same `IdCardPrintSettings`, so nothing is translated, only
normalised. A file is never trusted: unknown keys are dropped, values are clamped, and `notes` list every
thing that did not survive (the import is lossy only where the card engine is smaller than Events).
"""
import json

from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from . import badge_format

KIND = "spaceworks-event-badge"
EVENTS_KINDS = ("swe-id-card-design", "yuyu-id-card-design")
MAX_FILE_BYTES = 200_000


def export(settings):
    return {"kind": KIND, "version": 1, "settings": settings}


def parse(raw, *, event_title="", organisation_name=""):
    """Text, bytes or an already-parsed object -> (normalised settings, notes)."""
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    if isinstance(raw, str):
        if len(raw.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValidationError({"file": gettext("That file is too large to be a badge design.")})
        try:
            raw = json.loads(raw)
        except ValueError:
            raise ValidationError({"file": gettext("That file isn't a badge design. Choose a .json file exported "
                                                   "from the badge designer.")}) from None
    kind = raw.get("kind") if isinstance(raw, dict) else None
    if not (kind == KIND or kind in EVENTS_KINDS) or not isinstance(raw.get("settings"), dict):
        raise ValidationError({"file": gettext("That file isn't a badge design. Choose a .json file exported "
                                               "from the badge designer.")})
    if kind == KIND and raw.get("version") != 1:
        raise ValidationError({"file": gettext("This badge design file is from a newer version.")})
    given = raw["settings"]
    notes = []
    dropped = sorted(set(given) - badge_format.KEYS)
    if dropped:
        notes.append(gettext("Ignored settings this version does not use: {names}.").format(names=", ".join(map(str, dropped))[:200]))
    keys = given.get("printFieldKeys")
    if isinstance(keys, list) and len([key for key in keys if isinstance(key, str) and key.strip()]) > badge_format.PRINT_FIELD_MAX:
        notes.append(gettext("Only the first {count} registration answers are kept.").format(count=badge_format.PRINT_FIELD_MAX))
    if isinstance(given.get("watermark"), dict) and given["watermark"].get("kind") == "image":
        notes.append(gettext("The image watermark was not imported; badges carry a text watermark only."))
    settings = badge_format.normalize({key: value for key, value in given.items() if key in badge_format.KEYS},
                                      event_title=event_title, organisation_name=organisation_name)
    if settings["watermark"]["kind"] == "image":
        settings["watermark"] = {**settings["watermark"], "kind": "none"}
    return settings, notes
