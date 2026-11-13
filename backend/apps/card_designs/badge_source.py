"""The `source` block of a card design document: where `badge_v1` meets the card engine (E-B1).

A design document may carry `source: {"format": "badge_v1", "settings": {...}}`. `layout.normalize_document`
calls `expand` first: the settings are re-normalised and the FRONT layers are recompiled from them, so the
compiled layers are the only truth and a client cannot smuggle layers in. While `source` is present the
design is locked to the structured designer: saving a document without it is refused with
`badge_format_locked`; the explicit, audited "convert to free canvas" action drops it for good.
The `badge_v1` source and the `checkin_qr` layer kind exist only in the `event_card` domain.
"""
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from . import badge_format, stocks
from .badge_compile import compile_front

FORMAT = "badge_v1"
EVENT_DOMAIN = "event_card"


class BadgeFormatLocked(ValidationError):
    status_code = 409
    default_code = "badge_format_locked"


def expand(value):
    """The document with its front side compiled from `source.settings` (used by `normalize_document`)."""
    source = value["source"]
    if not isinstance(source, dict) or set(source) - {"format", "settings"} or source.get("format") != FORMAT:
        raise ValidationError({"source": gettext("Use a badge_v1 source.")})
    settings = badge_format.normalize(source.get("settings") or {}, strict=True)
    compiled = compile_front(settings)
    result = {key: item for key, item in value.items() if key not in ("source", "front", "back", "page_width_mm",
                                                                       "page_height_mm")}
    background = {"kind": "colour", "colour": compiled["background"]}
    result.update(version=2, stock=compiled["stock"], mono=compiled["mono"], watermark=compiled["watermark"],
                  back_enabled=False, source={"format": FORMAT, "settings": settings},
                  front={"background": background, "layers": compiled["layers"]},
                  back={"background": background, "layers": []})
    if compiled["stock"] == stocks.CUSTOM:
        result["page_width_mm"], result["page_height_mm"] = compiled["page_width_mm"], compiled["page_height_mm"]
    return result


def is_locked(document):
    return isinstance(document, dict) and bool(document.get("source"))


def ensure_unlocked(current, incoming):
    """Refuse a free-canvas document over a structured badge design."""
    if is_locked(current) and not is_locked(incoming):
        raise BadgeFormatLocked({"source": gettext(
            "This badge is edited in the badge designer. Convert it to a free canvas to edit its layers.")})


def check_domain(document, domain):
    """`badge_v1` and `checkin_qr` are event-card only."""
    if domain == EVENT_DOMAIN or domain is None:
        return
    uses_qr = any(layer["kind"] == "checkin_qr" for side in ("front", "back") for layer in document[side]["layers"])
    if document.get("source") or uses_qr:
        raise ValidationError({"source": gettext("Badge designs and check-in QR codes belong to event ID cards.")},
                              code="checkin_qr_event_card_only")


def without_source(document):
    return {key: item for key, item in document.items() if key != "source"}
