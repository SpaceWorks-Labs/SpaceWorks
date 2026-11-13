"""The `badge_v1` settings document: the SpaceWorks-Events badge settings, normalised.

Stored in `CardDesign.document["source"] = {"format": "badge_v1", "settings": {...}}` and compiled to
free-canvas layers on every save (`badge_compile.py`), so the settings are exactly the Events
`IdCardPrintSettings` (same keys, same camelCase, same values) and an Events design file
imports as-is. A native port of `lib/idCardPrint/model.ts` and `normalize.ts`: anything unexpected is
replaced by a default, positions and sizes are clamped to the card, and the stored JSON is capped.

Two deliberate differences, both forced by the card engine: at most `PRINT_FIELD_MAX` (8) answers
print (a layer budget of 40), and heading/label/footer keep only the `{{team}}` merge tag.
"""
import json
import re
from copy import deepcopy

from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from . import badge_geometry as geo

KIND = "badge_v1"
MAX_BYTES = 32_000
MIN_DIMENSION_MM, MAX_DIMENSION_MM = 40.0, 300.0
FOOTER_MAX_LENGTH = 240
PRINT_FIELD_MAX = 8
SPONSOR_LIMIT_MAX = 6
TEAM_FIELD_KEY, CREW_KIND_FIELD_KEY = "attendee:team", "attendee:crew_kind"
GRID_SIZES = (1, 2, 5, 10)
BACKGROUND_KEYS = ("white", "cream", "ink", "teal", "citron", "sky", "event")
ACCENT_KEYS = ("event", "teal", "ink", "orange", "citron", "sky", "yellow")
TEXT_KEYS = ("auto", "ink", "teal", "cream", "white")
WATERMARK_KINDS = ("none", "text", "image")
WATERMARK_COLOURS = ("accent", "text")
# Portrait presets as the Events designer lists them; "Turn" swaps width and height.
PRESETS = (
    {"id": "a6", "width_mm": 105.0, "height_mm": 148.0},
    {"id": "4x6", "width_mm": 101.6, "height_mm": 152.4},
    {"id": "3x4", "width_mm": 76.2, "height_mm": 101.6},
    {"id": "4x3", "width_mm": 101.6, "height_mm": 76.2},
    {"id": "cr80", "width_mm": 85.6, "height_mm": 53.98},
)
_TEAM_TAG = re.compile(r"{{\s*team\s*}}")
_ANY_TAG = re.compile(r"{{[^{}]*}}")
DEFAULT_WATERMARK = {"kind": "none", "text": "", "opacityPct": 10, "colour": "accent", "angleDeg": -30}
KEYS = frozenset({
    "widthMm", "heightMm", "heading", "badgeLabel", "showEmail", "template", "footerText", "showLogo",
    "printFieldKeys", "printFieldLabels", "elementPositions", "elementSizes", "elementBold", "elementTextSizes",
    "gridSizeMm", "showGrid", "nameAutoFit", "showBadgeLabel", "showFooter", "colorMode", "backgroundColor",
    "accentColor", "textColor", "showEventLogo", "showSymbol", "showPhoto", "photoShape", "showSponsors",
    "sponsorLimit", "showName", "showQr", "showIdNumber", "idNumberLabel", "showValidUntil", "validUntilLabel",
    "watermark"})


def default_settings(event_title="", organisation_name=""):
    width, height = 105.0, 148.0
    layout = geo.layout_for_paper("classic", width, height)
    return {
        "widthMm": width, "heightMm": height,
        "heading": event_title.strip()[:120] or "Event attendee", "badgeLabel": "ATTENDEE", "showEmail": True,
        "template": "classic", "footerText": organisation_name.strip()[:80] or "Event check-in",
        "printFieldKeys": [], "printFieldLabels": {}, **layout, "gridSizeMm": 5, "showGrid": True,
        "nameAutoFit": True, "showBadgeLabel": True, "showFooter": True, "colorMode": "colour",
        "backgroundColor": "white", "accentColor": "event", "textColor": "auto", **geo.DEFAULT_FLAGS,
        "photoShape": "circle", "sponsorLimit": 4, "showName": True, "showQr": True, "showIdNumber": False,
        "idNumberLabel": "ID", "showValidUntil": False, "validUntilLabel": "Valid until",
        "watermark": dict(DEFAULT_WATERMARK)}


def _number(value, fallback=None):
    if isinstance(value, bool):
        return fallback
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if number == number and abs(number) != float("inf") else fallback


def _text(value, fallback, limit):
    return value.strip()[:limit] or fallback if isinstance(value, str) else fallback


def _merge_only(value):
    """Heading, label and footer carry the `{{team}}` tag and nothing else in braces."""
    cleaned = _ANY_TAG.sub(lambda m: m.group(0) if _TEAM_TAG.fullmatch(m.group(0)) else "", value)
    return "{{team}}".join(part.replace("{", "").replace("}", "") for part in _TEAM_TAG.split(cleaned))


def _bool(value, fallback):
    return value if isinstance(value, bool) else fallback


def _one_of(value, allowed, fallback):
    return value if isinstance(value, str) and value in allowed else fallback


def _record(value):
    return value if isinstance(value, dict) else {}


def _positions(value, fallback, width, height):
    result = {}
    for element in geo.ELEMENTS:
        item = _record(_record(value).get(element))
        x, y = _number(item.get("xMm")), _number(item.get("yMm"))
        result[element] = {
            "xMm": fallback[element]["xMm"] if x is None else min(width - 4, max(0.0, geo.r1(x))),
            "yMm": fallback[element]["yMm"] if y is None else min(height - 4, max(0.0, geo.r1(y)))}
    return result


def _sizes(value, fallback, width):
    result = {}
    for element in geo.ELEMENTS:
        size = _number(_record(value).get(element))
        low = geo.minimum_element_size(element)
        result[element] = fallback[element] if size is None else min(max(low, width - 4), max(low, geo.r1(size)))
    return result


def _fit_positions(positions, sizes, width, height):
    result = {}
    for element in geo.ELEMENTS:
        box = geo.element_box_height(element, sizes, width, height)
        result[element] = {
            "xMm": min(max(0.0, width - sizes[element] - 4), positions[element]["xMm"]),
            "yMm": min(max(0.0, height - box - 4), positions[element]["yMm"]) if box > 0 else positions[element]["yMm"]}
    return result


def _text_sizes(value, template, width, height):
    fallback = geo.default_text_sizes(template, width, height)
    result = {}
    for element in geo.ELEMENTS:
        size = _number(_record(value).get(element)) if geo.is_text(element) else None
        result[element] = 0.0 if not geo.is_text(element) else (
            fallback[element] if size is None else min(48.0, max(6.0, geo.r1(size))))
    return result


def _field_keys(value):
    if not isinstance(value, list):
        return []
    keys = []
    for item in value:
        item = item.strip() if isinstance(item, str) else ""
        if item and len(item) <= 160 and not item.startswith("system:") and item not in keys:
            keys.append(item)
    return keys[:PRINT_FIELD_MAX]


def _field_labels(value):
    if not isinstance(value, dict):
        return {}
    return {key: label.strip()[:60] for key, label in list(value.items())[:16]
            if isinstance(key, str) and len(key) <= 160 and isinstance(label, str)}


def _watermark(value):
    if not isinstance(value, dict):
        return dict(DEFAULT_WATERMARK)
    opacity, angle = _number(value.get("opacityPct")), _number(value.get("angleDeg"))
    return {"kind": _one_of(value.get("kind"), WATERMARK_KINDS, "none"),
            "text": value["text"].strip()[:32] if isinstance(value.get("text"), str) else "",
            "opacityPct": 10 if opacity is None else geo.clamp(geo.half_up(opacity), 4, 30),
            "colour": _one_of(value.get("colour"), WATERMARK_COLOURS, "accent"),
            "angleDeg": -30 if angle is None else geo.clamp(geo.half_up(angle), -90, 90)}


def normalize(value, *, event_title="", organisation_name="", strict=False):
    """Any value -> a complete, safe settings dict. `strict` rejects unknown keys and oversize JSON (saves)."""
    fallback = default_settings(event_title, organisation_name)
    if not isinstance(value, dict):
        if strict and value is not None:
            raise ValidationError({"source": gettext("Badge settings must be an object.")})
        return fallback
    if strict:
        if set(value) - KEYS:
            raise ValidationError({"source": gettext("Unknown badge setting: {name}.").format(
                name=sorted(set(value) - KEYS)[0])})
        if len(json.dumps(value, separators=(",", ":"))) > MAX_BYTES:
            raise ValidationError({"source": gettext("That badge design is too large to save.")})
    legacy = bool(value) and "colorMode" not in value
    width = geo.clamp(geo.r1(_number(value.get("widthMm"), fallback["widthMm"])), MIN_DIMENSION_MM, MAX_DIMENSION_MM)
    height = geo.clamp(geo.r1(_number(value.get("heightMm"), fallback["heightMm"])), MIN_DIMENSION_MM, MAX_DIMENSION_MM)
    template = _one_of(value.get("template"), geo.TEMPLATES, "classic")
    flags = {"showLogo": _bool(value.get("showLogo"), True)}
    for key in ("showEventLogo", "showSymbol", "showPhoto", "showSponsors"):
        flags[key] = _bool(value.get(key), False if legacy else fallback[key])
    flags["showIdNumber"] = _bool(value.get("showIdNumber"), False)
    flags["showValidUntil"] = _bool(value.get("showValidUntil"), False)
    positions, sizes = geo.geometry_with_optional_defaults(template, width, height, flags)
    sizes = _sizes(value.get("elementSizes"), sizes, width)
    positions = _positions(value.get("elementPositions"), positions, width, height)
    sponsor_limit = _number(value.get("sponsorLimit"))
    bold = geo.default_bold()
    given_bold = _record(value.get("elementBold"))
    result = {
        "widthMm": width, "heightMm": height,
        "heading": _merge_only(_text(value.get("heading"), fallback["heading"], 120)),
        "badgeLabel": _merge_only(_text(value.get("badgeLabel"), fallback["badgeLabel"], 40)),
        "showEmail": _bool(value.get("showEmail"), True), "template": template,
        "footerText": _merge_only(_text(value.get("footerText"), fallback["footerText"], FOOTER_MAX_LENGTH)),
        "printFieldKeys": _field_keys(value.get("printFieldKeys")),
        "printFieldLabels": _field_labels(value.get("printFieldLabels")),
        "elementPositions": _fit_positions(positions, sizes, width, height), "elementSizes": sizes,
        "elementBold": {key: given_bold[key] if geo.is_text(key) and isinstance(given_bold.get(key), bool) else bold[key]
                        for key in geo.ELEMENTS},
        "elementTextSizes": _text_sizes(value.get("elementTextSizes"), template, width, height),
        "gridSizeMm": next((size for size in GRID_SIZES if size == _number(value.get("gridSizeMm"))), 5),
        "showGrid": _bool(value.get("showGrid"), True), "nameAutoFit": _bool(value.get("nameAutoFit"), True),
        "showBadgeLabel": _bool(value.get("showBadgeLabel"), True), "showFooter": _bool(value.get("showFooter"), True),
        "colorMode": "mono" if legacy else _one_of(value.get("colorMode"), ("colour", "mono"), "colour"),
        "backgroundColor": _one_of(value.get("backgroundColor"), BACKGROUND_KEYS, "white"),
        "accentColor": _one_of(value.get("accentColor"), ACCENT_KEYS, "event"),
        "textColor": _one_of(value.get("textColor"), TEXT_KEYS, "auto"), **flags,
        "photoShape": _one_of(value.get("photoShape"), ("circle", "rounded"), "circle"),
        "sponsorLimit": 4 if sponsor_limit is None else geo.clamp(geo.half_up(sponsor_limit), 1, SPONSOR_LIMIT_MAX),
        "showName": _bool(value.get("showName"), True), "showQr": _bool(value.get("showQr"), True),
        "idNumberLabel": _label(value.get("idNumberLabel"), "ID"),
        "validUntilLabel": _label(value.get("validUntilLabel"), "Valid until"),
        "watermark": _watermark(value.get("watermark"))}
    return deepcopy(result)


def _label(value, fallback):
    return value.strip()[:30] if isinstance(value, str) else fallback
