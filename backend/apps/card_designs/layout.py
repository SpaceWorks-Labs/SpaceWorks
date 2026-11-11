"""The closed CardDesignDocument v2 (SPEC §3.2): normalised on every write and read.

```
{version: 2, stock, page_width_mm?, page_height_mm? (custom only), back_enabled, mono,
 watermark: {kind: none|text|image, text, asset_id, opacity_pct 4-30, angle_deg -60..60, colour},
 front: Side, back: Side}
Side {page_width_mm, page_height_mm, background, layers: [0..40]}   (z-order = list order)
```

A document never carries an object key, a URL or a person's data: images are owned
`CardDesignAsset` ids, logos are typed slots, and text is literal or a data field.
"""
from django.utils.translation import gettext
import json
from copy import deepcopy

from rest_framework.exceptions import ValidationError

from . import stocks
from .contrast import HEX, unreadable_layers
from .layout_layers import normalize_layer

VERSION = 2
MAX_BYTES = 256 * 1024
MAX_LAYERS = 40
WATERMARK_KINDS = ("none", "text", "image")
DEFAULT_WATERMARK = {"kind": "none", "text": "", "asset_id": None, "opacity_pct": 10,
                     "angle_deg": -30, "colour": "#006E63"}
KEYS = {"version", "stock", "page_width_mm", "page_height_mm", "back_enabled", "mono", "watermark",
        "front", "back", "source"}


def _colour(value, field):
    if not isinstance(value, str) or not HEX.match(value):
        raise ValidationError({field: gettext("Use a #RRGGBB colour.")})
    return value.upper()


def _background(value):
    if not isinstance(value, dict):
        raise ValidationError({"background": gettext("Choose a colour, gradient or image background.")})
    kind = value.get("kind")
    if kind == "colour":
        return {"kind": "colour", "colour": _colour(value.get("colour"), "background")}
    if kind == "gradient":
        stops = value.get("stops")
        if not isinstance(stops, list) or not 2 <= len(stops) <= 4:
            raise ValidationError({"background": gettext("A gradient has 2-4 colour stops.")})
        clean = []
        for stop in stops:
            at = stop.get("at") if isinstance(stop, dict) else None
            if type(at) not in (int, float) or not 0 <= at <= 100:
                raise ValidationError({"background": gettext("Gradient stops sit between 0 and 100 %.")})
            clean.append({"colour": _colour(stop.get("colour"), "background"), "at": float(at)})
        gradient_type = value.get("type", "linear")
        angle = value.get("angle_deg", 0)
        if gradient_type not in ("linear", "radial") or type(angle) not in (int, float) or not 0 <= angle <= 360:
            raise ValidationError({"background": gettext("Use a linear (0-360 degrees) or radial gradient.")})
        return {"kind": "gradient", "type": gradient_type, "angle_deg": float(angle),
                "stops": sorted(clean, key=lambda stop: stop["at"])}
    if kind == "image":
        from .layout_layers import asset_id
        dim = value.get("dim_pct", 0)
        if value.get("fit", "cover") not in ("cover", "contain") or type(dim) not in (int, float) or not 0 <= dim <= 60:
            raise ValidationError({"background": gettext("Image backgrounds cover or contain, dimmed 0-60 %.")})
        return {"kind": "image", "asset_id": asset_id(value.get("asset_id")), "fit": value.get("fit", "cover"),
                "dim_pct": float(dim), "fallback": _colour(value.get("fallback", "#FFFFFF"), "background")}
    raise ValidationError({"background": gettext("Choose a colour, gradient or image background.")})


def _watermark(value):
    result = {**DEFAULT_WATERMARK, **(value or {})}
    if set(result) - set(DEFAULT_WATERMARK) or result["kind"] not in WATERMARK_KINDS:
        raise ValidationError({"watermark": gettext("Use a none, text or image watermark.")})
    if not isinstance(result["text"], str) or len(result["text"]) > 32:
        raise ValidationError({"watermark": gettext("Watermark text is at most 32 characters.")})
    if type(result["opacity_pct"]) not in (int, float) or not 4 <= result["opacity_pct"] <= 30:
        raise ValidationError({"watermark": gettext("Watermark opacity is 4-30 %.")})
    if type(result["angle_deg"]) not in (int, float) or not -60 <= result["angle_deg"] <= 60:
        raise ValidationError({"watermark": gettext("Watermark angle is -60 to 60 degrees.")})
    result["colour"] = _colour(result["colour"], "watermark")
    if result["kind"] == "image":
        from .layout_layers import asset_id
        result["asset_id"] = asset_id(result["asset_id"])
    else:
        result["asset_id"] = None
    if result["kind"] == "text" and not result["text"].strip():
        raise ValidationError({"watermark": gettext("Type the watermark text.")})
    return result


def _side(value, width, height, stock, label):
    if not isinstance(value, dict) or set(value) - {"page_width_mm", "page_height_mm", "background", "layers"}:
        raise ValidationError({label: gettext("Each side has a background and layers.")})
    layers = value.get("layers", [])
    if not isinstance(layers, list) or len(layers) > MAX_LAYERS:
        raise ValidationError({label: gettext('Use at most {MAX_LAYERS} layers per side.').format(MAX_LAYERS=MAX_LAYERS)})
    clean = [normalize_layer(layer, width, height, stock) for layer in layers]
    if len({layer["id"] for layer in clean}) != len(clean):
        raise ValidationError({label: gettext("Layer ids must be unique.")})
    return {"page_width_mm": width, "page_height_mm": height,
            "background": _background(value.get("background", {"kind": "colour", "colour": "#FFFFFF"})),
            "layers": clean}


def upgrade(value):
    """Version 1 (the first SPEC draft: one side, no background) becomes a v2 front."""
    if isinstance(value, dict) and value.get("version") == 1:
        front = {"background": {"kind": "colour", "colour": value.get("background", "#FFFFFF")},
                 "layers": value.get("layers", [])}
        return {"version": VERSION, "stock": value.get("stock", stocks.DEFAULT_STOCK), "back_enabled": False,
                "mono": False, "front": front, "back": {"layers": []}}
    return value


def normalize_document(value, *, asset_colours=None, check_contrast=True):
    value = upgrade(deepcopy(value))
    if not isinstance(value, dict) or value.get("version") != VERSION or set(value) - KEYS:
        raise ValidationError({"document": gettext("Use a version 2 card design document.")})
    if len(json.dumps(value, separators=(",", ":"))) > MAX_BYTES:
        raise ValidationError({"document": gettext("The design is larger than 256 KB.")})
    if value.get("source") is not None:  # E-B1: a badge_v1 design's front is compiled from its settings
        from .badge_source import expand
        value = expand(value)
    stock = value.get("stock", stocks.DEFAULT_STOCK)
    width, height = stocks.dimensions(stock, value.get("page_width_mm"), value.get("page_height_mm"))
    for key in ("back_enabled", "mono"):
        if type(value.get(key, False)) is not bool:
            raise ValidationError({key: gettext("Use true or false.")})
    result = {"version": VERSION, "stock": stock, "back_enabled": value.get("back_enabled", False),
              "mono": value.get("mono", False), "watermark": _watermark(value.get("watermark")),
              "front": _side(value.get("front", {}), width, height, stock, "front"),
              "back": _side(value.get("back", {}), width, height, stock, "back")}
    if stock == stocks.CUSTOM:
        result["page_width_mm"], result["page_height_mm"] = width, height
    if value.get("source"):
        result["source"] = value["source"]
    if check_contrast and not result["mono"]:
        for side in ("front", "back"):
            if side == "back" and not result["back_enabled"]:
                continue
            failing = unreadable_layers(result[side], asset_colours)
            if failing:
                raise ValidationError({"contrast": gettext('Text is hard to read on the {side}: {value}. Use a colour with at least 4.5:1 contrast.').format(side=side, value=', '.join(failing))})
    return result


def asset_ids(document):
    ids = set()
    if document.get("watermark", {}).get("asset_id"):
        ids.add(document["watermark"]["asset_id"])
    for side in ("front", "back"):
        background = document[side]["background"]
        if background.get("kind") == "image":
            ids.add(background["asset_id"])
        ids.update(layer["asset_id"] for layer in document[side]["layers"] if layer["kind"] == "image")
    return ids


def sides(document):
    return ("front", "back") if document.get("back_enabled") else ("front",)
