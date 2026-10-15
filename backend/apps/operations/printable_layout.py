"""Bounded, domain-neutral print geometry. Coordinates are top-left millimetres."""

import math
import re

from rest_framework.exceptions import ValidationError

FONTS = ("sans", "serif")
ELEMENT_KEYS = {"field", "x_mm", "y_mm", "width_mm", "height_mm", "font_size_pt",
                "font", "bold", "align", "colour"}


def number(value, minimum, maximum, field):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or not minimum <= value <= maximum):
        raise ValidationError({field: f"Use a finite number from {minimum} to {maximum}."})
    return float(value)


def normalize_element(value, *, width, height, fields, grid_mm=1):
    if not isinstance(value, dict) or set(value) - ELEMENT_KEYS:
        raise ValidationError({"elements": "Unknown positioned element properties."})
    if not isinstance(value.get("field"), str) or value["field"] not in fields:
        raise ValidationError({"elements": "Unknown or forbidden field binding."})
    result = {"font": "sans", "font_size_pt": 12, "bold": False,
              "align": "left", "colour": "#0F172A", **value}
    for key, maximum in (("x_mm", width), ("y_mm", height),
                         ("width_mm", width), ("height_mm", height)):
        minimum = grid_mm if key in ("width_mm", "height_mm") else 0
        result[key] = number(result.get(key), minimum, maximum, key)
        result[key] = round(round(result[key] / grid_mm) * grid_mm, 3)
    if (result["x_mm"] + result["width_mm"] > width
            or result["y_mm"] + result["height_mm"] > height):
        raise ValidationError({"elements": "An element extends outside its printable area."})
    result["font_size_pt"] = number(result["font_size_pt"], 6, 48, "font_size_pt")
    if result["font"] not in FONTS or type(result["bold"]) is not bool:
        raise ValidationError({"elements": "Choose a bundled font and boolean bold value."})
    if result["align"] not in ("left", "center", "right"):
        raise ValidationError({"align": "Use left, center or right."})
    if not isinstance(result["colour"], str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", result["colour"]):
        raise ValidationError({"colour": "Use a six-digit hexadecimal colour."})
    return result


def normalize_elements(values, *, width, height, fields, grid_mm=1):
    grid_mm = number(grid_mm, 0.5, 10, "grid_mm")
    if not isinstance(values, list) or not 1 <= len(values) <= 12:
        raise ValidationError({"elements": "Choose between 1 and 12 elements."})
    result = [normalize_element(value, width=width, height=height, fields=fields,
                                grid_mm=grid_mm) for value in values]
    if len({item["field"] for item in result}) != len(result):
        raise ValidationError({"elements": "Field bindings must be unique."})
    return result


def page_dimensions(template):
    sizes = {"A4": (210.0, 297.0), "LETTER": (215.9, 279.4)}
    dimensions = ((template["page_width_mm"], template["page_height_mm"])
                  if template["paper_size"] == "custom" else sizes[template["paper_size"]])
    return dimensions[::-1] if template["orientation"] == "landscape" else dimensions


def page_layout(template):
    width, height = page_dimensions(template)
    gap, margin = template["gap_mm"], template["margin_mm"]
    columns = math.floor((width - 2 * margin + gap) / (template["card_width_mm"] + gap))
    rows = math.floor((height - 2 * margin + gap) / (template["card_height_mm"] + gap))
    if columns < 1 or rows < 1:
        raise ValidationError({"template": "No card fits on the configured page."})
    return width, height, columns, rows
