"""Card Studio additions to the closed document (decision 314, SPEC `CARD-STUDIO-SPEC-0.12.0.md`).

Everything here is SPARSE: a property equal to its default is omitted from the normalised output, so a document
written before the Studio normalises to the same layers it always did (only `version` becomes 3), and the TS
twin treats an absent key as the default. Validators return plain dicts and raise `ValidationError`.
"""
import math
import re

from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from .contrast import HEX
from .data_fields import validate_text

LANG = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$")
MASKS = ("none", "rounded", "circle", "arch")
FITS = ("cover", "contain", "stretch")
MAX_SPANS = 20
MAX_TEXT = 500
MAX_RULERS = 20


def num(value, low, high, field):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValidationError({field: gettext('Use a number from {low:g} to {high:g}.').format(low=low, high=high)})
    return round(float(value), 2)


def hexc(value, field):
    if not isinstance(value, str) or not HEX.match(value):
        raise ValidationError({field: gettext("Use a #RRGGBB colour.")})
    return value.upper()


def flag(value, field):
    if type(value) is not bool:
        raise ValidationError({field: gettext("Use true or false.")})
    return value


def closed(value, allowed, field):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValidationError({field: gettext("Unknown properties.")})
    return value


def gradient(value, field, *, alpha=False):
    """{type, angle_deg, cx_pct, cy_pct, radius_pct, stops} -> sparse normalised dict (stops 2-6)."""
    closed(value, {"type", "angle_deg", "cx_pct", "cy_pct", "radius_pct", "stops"}, field)
    stops = value.get("stops")
    if not isinstance(stops, list) or not 2 <= len(stops) <= 6:
        raise ValidationError({field: gettext("A gradient has 2-6 colour stops.")})
    clean = []
    for stop in stops:
        closed(stop, {"colour", "at", "alpha_pct"} if alpha else {"colour", "at"}, field)
        row = {"colour": hexc(stop.get("colour"), field), "at": num(stop.get("at"), 0, 100, field)}
        if alpha:
            row["alpha_pct"] = num(stop.get("alpha_pct", 100), 0, 100, field)
        clean.append(row)
    kind = value.get("type", "linear")
    if kind not in ("linear", "radial"):
        raise ValidationError({field: gettext("Use a linear or radial gradient.")})
    result = {"type": kind, "angle_deg": num(value.get("angle_deg", 0), 0, 360, field),
              "stops": sorted(clean, key=lambda stop: stop["at"])}
    for key, low, high, default in (("cx_pct", 0, 100, 50), ("cy_pct", 0, 100, 50), ("radius_pct", 10, 300, 100)):
        number = num(value.get(key, default), low, high, field)
        if kind == "radial" and number != default:
            result[key] = number
    return result


def overlay(value):
    return None if value is None else gradient(value, "overlay", alpha=True)


def shadow(value):
    if value is None:
        return None
    closed(value, {"dx_mm", "dy_mm", "blur_mm", "colour", "opacity_pct"}, "shadow")
    return {"dx_mm": num(value.get("dx_mm", 0.6), -5, 5, "shadow"), "dy_mm": num(value.get("dy_mm", 0.8), -5, 5, "shadow"),
            "blur_mm": num(value.get("blur_mm", 1), 0, 6, "shadow"),
            "colour": hexc(value.get("colour", "#000000"), "shadow"),
            "opacity_pct": num(value.get("opacity_pct", 35), 0, 100, "shadow")}


def outline(value):
    if value is None:
        return None
    closed(value, {"width_mm", "colour"}, "outline")
    return {"width_mm": num(value.get("width_mm", 0.8), 0.1, 3, "outline"),
            "colour": hexc(value.get("colour", "#FFFFFF"), "outline")}


def frame(value, row, *, allow_mask=True):
    """Image-ish layers: zoom, focal point, flip, mask radius, outline, shadow; sparse."""
    zoom = num(value.get("zoom", 1), 1, 4, "zoom")
    if zoom != 1:
        row["zoom"] = zoom
    for key in ("focal_x_pct", "focal_y_pct"):
        number = num(value.get(key, 50), 0, 100, key)
        if number != 50:
            row[key] = number
    for key in ("flip_x", "flip_y"):
        if key in value and flag(value[key], key):
            row[key] = True
    if value.get("radius_mm") is not None:
        row["radius_mm"] = num(value["radius_mm"], 0, 40, "radius_mm")
    for key, check in (("outline", outline), ("shadow", shadow)):
        clean = check(value.get(key))
        if clean:
            row[key] = clean
    if allow_mask and value.get("mask", "none") != "none":
        if value["mask"] not in MASKS:
            raise ValidationError({"mask": gettext("Masks are rounded, circle or arch.")})
        row["mask"] = value["mask"]


def spans(value, check_face):
    """Validated spans and their joined text; `check_face(family, weight)` validates a face when named."""
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_SPANS:
        raise ValidationError({"spans": gettext('Use 1-{limit} text spans.').format(limit=MAX_SPANS)})
    clean, joined = [], ""
    for item in value:
        closed(item, {"text", "font_family", "font_weight", "colour", "size_pt", "size_scale", "tracking_pt",
                      "uppercase"}, "spans")
        row = {"text": validate_text(item.get("text", ""))}
        for key in ("font_family", "font_weight"):
            if item.get(key) is not None:
                row[key] = item[key]
        if row.get("font_family") is not None or row.get("font_weight") is not None:
            check_face(row.get("font_family"), row.get("font_weight"))
        if item.get("colour") is not None:
            row["colour"] = hexc(item["colour"], "spans")
        if item.get("size_pt") is not None:
            row["size_pt"] = num(item["size_pt"], 6, 200, "spans")
        if item.get("size_scale") is not None and item["size_scale"] != 1:
            row["size_scale"] = num(item["size_scale"], 0.3, 4, "spans")
        if item.get("tracking_pt") is not None:
            row["tracking_pt"] = num(item["tracking_pt"], -2, 10, "spans")
        if item.get("uppercase") is not None:
            row["uppercase"] = flag(item["uppercase"], "spans")
        clean.append(row)
        joined += row["text"]
    if len(joined) > MAX_TEXT:
        raise ValidationError({"spans": gettext('Use at most {limit} characters.').format(limit=MAX_TEXT)})
    return clean, joined


def text_extras(value, row):
    """stroke, shadow, highlight, underline, translations on a text layer; sparse."""
    if value.get("stroke") is not None:
        closed(value["stroke"], {"colour", "width_pt"}, "stroke")
        row["stroke"] = {"colour": hexc(value["stroke"].get("colour"), "stroke"),
                         "width_pt": num(value["stroke"].get("width_pt", 1), 0.1, 8, "stroke")}
    clean = shadow(value.get("shadow"))
    if clean:
        clean["blur_mm"] = min(clean["blur_mm"], 2.0)
        row["shadow"] = clean
    if value.get("highlight") is not None:
        item = closed(value["highlight"], {"colour", "pad_x_mm", "pad_y_mm", "radius_mm"}, "highlight")
        row["highlight"] = {"colour": hexc(item.get("colour", "#DFFF8F"), "highlight"),
                            "pad_x_mm": num(item.get("pad_x_mm", 1.5), 0, 10, "highlight"),
                            "pad_y_mm": num(item.get("pad_y_mm", 0.8), 0, 10, "highlight"),
                            "radius_mm": num(item.get("radius_mm", 0.8), 0, 10, "highlight")}
    if value.get("underline") is not None:
        item = closed(value["underline"], {"colour", "thickness_pt", "offset_pt"}, "underline")
        row["underline"] = {"colour": hexc(item.get("colour", row.get("colour", "#142C2A")), "underline"),
                            "thickness_pt": num(item.get("thickness_pt", 1.5), 0.5, 8, "underline"),
                            "offset_pt": num(item.get("offset_pt", 2), 0, 12, "underline")}
    translations = value.get("translations")
    if translations is not None:
        if not isinstance(translations, dict) or len(translations) > 8 or any(
                not isinstance(code, str) or not LANG.match(code) for code in translations):
            raise ValidationError({"translations": gettext("Use up to 8 language codes such as ml or hi.")})
        row["translations"] = {code: validate_text(text) for code, text in translations.items()}


def background_image_extras(value, row):
    fit = value.get("fit", "cover")
    if fit not in FITS:
        raise ValidationError({"background": gettext("Image backgrounds cover, contain or stretch.")})
    row["fit"] = fit
    zoom = num(value.get("zoom", 1), 1, 4, "background")
    if zoom != 1:
        row["zoom"] = zoom
    for key in ("focal_x_pct", "focal_y_pct"):
        number = num(value.get(key, 50), 0, 100, "background")
        if number != 50:
            row[key] = number
    blur = num(value.get("blur_mm", 0), 0, 8, "background")
    if blur:
        row["blur_mm"] = blur
    row["dim_pct"] = num(value.get("dim_pct", 0), 0, 80, "background")


def guides(value, width, height):
    value = {} if value is None else value
    closed(value, {"bleed_mm", "safe_mm", "margin_mm", "punch_slot", "rulers"}, "guides")
    result = {"bleed_mm": num(value.get("bleed_mm", 0), 0, 5, "guides"),
              "safe_mm": num(value.get("safe_mm", 3), 0, 15, "guides"),
              "margin_mm": num(value.get("margin_mm", 0), 0, 30, "guides"), "punch_slot": None, "rulers": []}
    punch = value.get("punch_slot")
    if punch is not None:
        closed(punch, {"shape", "x_mm", "y_mm", "w_mm", "h_mm", "side"}, "guides")
        if punch.get("shape", "slot") not in ("slot", "round") or punch.get("side", "front") not in ("front", "back", "both"):
            raise ValidationError({"guides": gettext("A punch slot is a slot or round, on the front, back or both.")})
        box = {"shape": punch.get("shape", "slot"), "side": punch.get("side", "front"),
               "x_mm": num(punch.get("x_mm"), 0, width, "guides"), "y_mm": num(punch.get("y_mm"), 0, height, "guides"),
               "w_mm": num(punch.get("w_mm", 12), 1, width, "guides"), "h_mm": num(punch.get("h_mm", 3), 1, height, "guides")}
        if box["x_mm"] + box["w_mm"] > width + 0.01 or box["y_mm"] + box["h_mm"] > height + 0.01:
            raise ValidationError({"guides": gettext("The punch slot must sit inside the card.")})
        result["punch_slot"] = box
    rulers = value.get("rulers", [])
    if not isinstance(rulers, list) or len(rulers) > MAX_RULERS:
        raise ValidationError({"guides": gettext('Use at most {limit} guide lines.').format(limit=MAX_RULERS)})
    for ruler in rulers:
        closed(ruler, {"axis", "at_mm"}, "guides")
        if ruler.get("axis") not in ("x", "y"):
            raise ValidationError({"guides": gettext("A guide line is on the x or y axis.")})
        result["rulers"].append({"axis": ruler["axis"], "at_mm": num(ruler.get("at_mm"), 0, 420, "guides")})
    return result


def groups(value, layers):
    """Group rows for a side: given rows validated, missing rows made for legacy ids, groups of < 2 dropped."""
    from .layout_layers import asset_id
    given = {}
    for item in value or []:
        closed(item, {"id", "name", "locked", "hidden"}, "groups")
        name = item.get("name", "")
        if not isinstance(name, str) or len(name) > 40:
            raise ValidationError({"groups": gettext("Group names are at most 40 characters.")})
        group_id = asset_id(item.get("id"))
        given[group_id] = {"id": group_id, "name": name, "locked": flag(item.get("locked", False), "groups"),
                           "hidden": flag(item.get("hidden", False), "groups")}
    counts = {}
    for layer in layers:
        if layer.get("group"):
            counts[layer["group"]] = counts.get(layer["group"], 0) + 1
    rows = [given.get(group_id) or {"id": group_id, "name": "", "locked": False, "hidden": False}
            for group_id, count in counts.items() if count >= 2]
    for layer in layers:
        if layer.get("group") and counts.get(layer["group"], 0) < 2:
            layer["group"] = None
    return rows
