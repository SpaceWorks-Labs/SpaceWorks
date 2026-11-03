"""One free-canvas layer: geometry, kind-specific properties and their bounds."""
import math
from uuid import UUID

from rest_framework.exceptions import ValidationError

from . import stocks
from .contrast import HEX
from .data_fields import valid_tag, validate_text

KINDS = ("text", "data_field", "image", "logo", "photo", "desk_qr", "verify_qr", "shape", "band", "perforation")
QR_KINDS = ("desk_qr", "verify_qr")
COMMON = {"id", "kind", "name", "x_mm", "y_mm", "w_mm", "h_mm", "rotation", "opacity", "locked", "hidden"}
TEXT = {"text", "field", "font_family", "font_weight", "font_size_pt", "align", "valign", "colour",
        "uppercase", "tracking_pt", "line_height", "shrink_to_fit"}
EXTRA = {
    "text": TEXT, "data_field": TEXT,
    "image": {"asset_id", "fit"},
    "logo": {"source", "tile"},
    "photo": {"shape"},
    "desk_qr": set(), "verify_qr": set(),
    "shape": {"shape", "fill", "stroke", "stroke_mm", "radius_mm"},
    "band": {"fill", "radius_mm"},
    "perforation": {"colour", "orientation"},
}
LOGO_SOURCES = ("space", "organisation", "event", "symbol")
TEXT_DEFAULTS = {"font_family": "Gilroy", "font_weight": 400, "font_size_pt": 10, "align": "left",
                 "valign": "top", "colour": "#142C2A", "uppercase": False, "tracking_pt": 0,
                 "line_height": 1.2, "shrink_to_fit": True}


def asset_id(value):
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError({"layers": "Images use an uploaded design asset."}) from None


def _number(value, minimum, maximum, field):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValidationError({field: f"Use a number from {minimum:g} to {maximum:g}."})
    return round(float(value), 2)


def _hex(value, field, *, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not HEX.match(value):
        raise ValidationError({field: "Use a #RRGGBB colour."})
    return value.upper()


def _bool(row, key, default=False):
    value = row.get(key, default)
    if type(value) is not bool:
        raise ValidationError({key: "Use true or false."})
    return value


def _geometry(value, row, width, height):
    row["x_mm"] = _number(value.get("x_mm"), -width, width, "x_mm")
    row["y_mm"] = _number(value.get("y_mm"), -height, height, "y_mm")
    row["w_mm"] = _number(value.get("w_mm"), 0.5, width * 2, "w_mm")
    row["h_mm"] = _number(value.get("h_mm"), 0.3, height * 2, "h_mm")
    row["rotation"] = _number(value.get("rotation", 0), -360, 360, "rotation")
    row["opacity"] = _number(value.get("opacity", 100), 0, 100, "opacity")
    theta = math.radians(row["rotation"])
    half_w = (abs(math.cos(theta)) * row["w_mm"] + abs(math.sin(theta)) * row["h_mm"]) / 2
    half_h = (abs(math.sin(theta)) * row["w_mm"] + abs(math.cos(theta)) * row["h_mm"]) / 2
    cx, cy = row["x_mm"] + row["w_mm"] / 2, row["y_mm"] + row["h_mm"] / 2
    if cx - half_w < -0.05 or cy - half_h < -0.05 or cx + half_w > width + 0.05 or cy + half_h > height + 0.05:
        raise ValidationError({"layers": f"“{row['name'] or row['kind']}” extends beyond the card edge."})


def _text(value, row):
    from .fonts import family_weights
    for key, default in TEXT_DEFAULTS.items():
        row[key] = value.get(key, default)
    if row["kind"] == "data_field":
        field = value.get("field")
        if not isinstance(field, str) or not valid_tag(field):
            raise ValidationError({"layers": "Choose a data field for this layer."})
        row["field"] = field
        row["text"] = "{{" + field + "}}"
    else:
        row["text"] = validate_text(value.get("text", ""))
    weights = family_weights(row["font_family"])
    if not weights:
        raise ValidationError({"layers": f"“{row['font_family']}” is not in the card font library."})
    if type(row["font_weight"]) is not int or row["font_weight"] not in weights:
        raise ValidationError({"layers": f"{row['font_family']} ships weights {', '.join(map(str, weights))}."})
    row["font_size_pt"] = _number(row["font_size_pt"], 6, 96, "font_size_pt")
    row["tracking_pt"] = _number(row["tracking_pt"], -2, 10, "tracking_pt")
    row["line_height"] = _number(row["line_height"], 0.8, 3, "line_height")
    if row["align"] not in ("left", "center", "right") or row["valign"] not in ("top", "middle", "bottom"):
        raise ValidationError({"layers": "Align text left, centre or right, and top, middle or bottom."})
    row["colour"] = _hex(row["colour"], "colour")
    row["uppercase"] = _bool(row, "uppercase")
    row["shrink_to_fit"] = _bool(row, "shrink_to_fit", True)


def normalize_layer(value, width, height, stock):
    if not isinstance(value, dict) or value.get("kind") not in KINDS:
        raise ValidationError({"layers": "Unknown layer kind."})
    kind = value["kind"]
    if kind == "band":  # early drafts stored shape keys on bands; they carry no meaning there
        value = {key: item for key, item in value.items() if key not in ("shape", "stroke", "stroke_mm")}
    if set(value) - (COMMON | EXTRA[kind]):
        raise ValidationError({"layers": f"Unknown properties on a {kind} layer."})
    name = value.get("name", "")
    if not isinstance(name, str) or len(name) > 40:
        raise ValidationError({"layers": "Layer names are at most 40 characters."})
    row = {"id": asset_id(value.get("id")), "kind": kind, "name": name}
    row["locked"] = _bool(value, "locked")
    row["hidden"] = _bool(value, "hidden")
    _geometry(value, row, width, height)
    if kind in ("text", "data_field"):
        _text(value, row)
    elif kind == "image":
        row["asset_id"] = asset_id(value.get("asset_id"))
        row["fit"] = value.get("fit", "contain")
        if row["fit"] not in ("cover", "contain"):
            raise ValidationError({"layers": "Images cover or contain their box."})
    elif kind == "logo":
        row["source"] = value.get("source", "space")
        row["tile"] = _bool(value, "tile")
        if row["source"] not in LOGO_SOURCES:
            raise ValidationError({"layers": "Logos come from the space, organisation, event or symbol."})
    elif kind == "photo":
        row["shape"] = value.get("shape", "rounded")
        if row["shape"] not in ("circle", "rounded", "square"):
            raise ValidationError({"layers": "Photos are circle, rounded or square."})
    elif kind in QR_KINDS:
        minimum = stocks.qr_minimum_mm(stock)
        if min(row["w_mm"], row["h_mm"]) < minimum - 0.01 or row["opacity"] != 100 or row["rotation"] % 90:
            raise ValidationError({"layers": f"QR codes need {minimum:g} mm, full opacity and a right-angle turn."})
    elif kind in ("shape", "band"):
        # A band carries only its own keys (fill, radius), so a normalised band normalises again.
        row["fill"] = _hex(value.get("fill", "#006E63" if kind == "band" else None), "fill", nullable=True)
        row["radius_mm"] = _number(value.get("radius_mm", 0), 0, 20, "radius_mm")
        if kind == "shape":
            row["shape"] = value.get("shape", "rect")
            if row["shape"] not in ("rect", "ellipse", "line"):
                raise ValidationError({"layers": "Shapes are rectangles, ellipses or lines."})
            row["stroke"] = _hex(value.get("stroke"), "stroke", nullable=True)
            row["stroke_mm"] = _number(value.get("stroke_mm", 0.3), 0, 5, "stroke_mm")
        if row["fill"] is None and row.get("stroke") is None:
            raise ValidationError({"layers": "A shape needs a fill or an outline."})
    elif kind == "perforation":
        row["colour"] = _hex(value.get("colour", "#D5D0C6"), "colour")
        row["orientation"] = value.get("orientation", "vertical")
        if row["orientation"] not in ("vertical", "horizontal"):
            raise ValidationError({"layers": "Perforations run vertically or horizontally."})
    return row
