"""The closed CardDesignDocument v2 (SPEC §3.2): normalised on every write and read.

```
{version: 3, kind?: certificate, guides?, stock, page_width_mm?, page_height_mm? (custom only), back_enabled, mono,
 watermark: {kind: none|text|image, text, asset_id, opacity_pct 4-30, angle_deg -60..60, colour},
 front: Side, back: Side}
Side {page_width_mm, page_height_mm, background, layers: [0..60]}   (z-order = list order)
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
from . import layout_studio as studio
from .layout_layers import normalize_layer

VERSION = 3  # 3 = Card Studio (decision 314): every addition is optional and sparse, so a v2 document is a valid v3 one
MAX_BYTES = 256 * 1024
MAX_LAYERS = 60
WATERMARK_KINDS = ("none", "text", "image")
DEFAULT_WATERMARK = {"kind": "none", "text": "", "asset_id": None, "opacity_pct": 10,
                     "angle_deg": -30, "colour": "#006E63"}
KEYS = {"version", "kind", "stock", "page_width_mm", "page_height_mm", "back_enabled", "mono", "watermark",
        "front", "back", "source", "guides"}
KINDS = ("card", "certificate")
DEFAULT_GUIDES = {"bleed_mm": 0.0, "safe_mm": 3.0, "margin_mm": 0.0, "punch_slot": None, "rulers": []}


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
        return {"kind": "gradient", **studio.gradient({key: item for key, item in value.items() if key != "kind"},
                                                       "background")}
    if kind == "image":
        from .layout_layers import asset_id
        studio.closed(value, {"kind", "asset_id", "fit", "zoom", "focal_x_pct", "focal_y_pct", "blur_mm", "dim_pct",
                              "fallback"}, "background")
        row = {"kind": "image", "asset_id": asset_id(value.get("asset_id")),
               "fallback": _colour(value.get("fallback", "#FFFFFF"), "background")}
        studio.background_image_extras(value, row)
        return row
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


def _side(value, width, height, stock, label, kind="card"):
    if not isinstance(value, dict) or set(value) - {"page_width_mm", "page_height_mm", "background", "layers",
                                                    "overlay", "groups"}:
        raise ValidationError({label: gettext("Each side has a background and layers.")})
    layers = value.get("layers", [])
    if not isinstance(layers, list) or len(layers) > MAX_LAYERS:
        raise ValidationError({label: gettext('Use at most {MAX_LAYERS} layers per side.').format(MAX_LAYERS=MAX_LAYERS)})
    clean = [normalize_layer(layer, width, height, stock, kind) for layer in layers]
    if len({layer["id"] for layer in clean}) != len(clean):
        raise ValidationError({label: gettext("Layer ids must be unique.")})
    result = {"page_width_mm": width, "page_height_mm": height,
              "background": _background(value.get("background", {"kind": "colour", "colour": "#FFFFFF"})),
              "layers": clean}
    if value.get("overlay") is not None:
        result["overlay"] = studio.overlay(value["overlay"])
    rows = studio.groups(value.get("groups"), clean)
    if rows:
        result["groups"] = rows
    return result


def upgrade(value):
    """v1 (the first SPEC draft: one side, no background) becomes a front; v2 becomes v3 (only the number moves)."""
    if isinstance(value, dict) and value.get("version") == 1:
        front = {"background": {"kind": "colour", "colour": value.get("background", "#FFFFFF")},
                 "layers": value.get("layers", [])}
        return {"version": VERSION, "stock": value.get("stock", stocks.DEFAULT_STOCK), "back_enabled": False,
                "mono": False, "front": front, "back": {"layers": []}}
    if isinstance(value, dict) and value.get("version") == 2:
        return {**value, "version": VERSION}
    return value


def normalize_document(value, *, asset_colours=None, check_contrast=True):
    from .data_fields import document_kind
    kind = value.get("kind", "card") if isinstance(value, dict) else "card"
    with document_kind(kind if kind in KINDS else "card"):  # certificate tags are valid only in a certificate
        return _normalize(value, asset_colours, check_contrast)


def _normalize(value, asset_colours, check_contrast):
    value = upgrade(deepcopy(value))
    if not isinstance(value, dict) or value.get("version") != VERSION or set(value) - KEYS:
        raise ValidationError({"document": gettext("Use a version 3 card design document.")})
    if len(json.dumps(value, separators=(",", ":"))) > MAX_BYTES:
        raise ValidationError({"document": gettext("The design is larger than 256 KB.")})
    if value.get("source") is not None:  # E-B1: a badge_v1 design's front is compiled from its settings
        from .badge_source import expand
        value = expand(value)
    stock = value.get("stock", stocks.DEFAULT_STOCK)
    kind = value.get("kind", "card")
    if kind not in KINDS:
        raise ValidationError({"kind": gettext("A design is a card or a certificate.")})
    width, height = stocks.dimensions(stock, value.get("page_width_mm"), value.get("page_height_mm"), kind)
    for key in ("back_enabled", "mono"):
        if type(value.get(key, False)) is not bool:
            raise ValidationError({key: gettext("Use true or false.")})
    result = {"version": VERSION, "stock": stock, "back_enabled": value.get("back_enabled", False),
              "mono": value.get("mono", False), "watermark": _watermark(value.get("watermark")),
              "front": _side(value.get("front", {}), width, height, stock, "front", kind),
              "back": _side(value.get("back", {}), width, height, stock, "back", kind)}
    if kind != "card":
        result["kind"] = kind
    clean_guides = studio.guides(value.get("guides"), width, height)
    if clean_guides != DEFAULT_GUIDES:
        result["guides"] = clean_guides
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
        # A badge_v1 / source-only document has no sides until normalize compiles it: nothing to look up yet.
        block = document.get(side)
        if not isinstance(block, dict):
            continue
        background = block.get("background") or {}
        if background.get("kind") == "image":
            ids.add(background["asset_id"])
        ids.update(layer["asset_id"] for layer in block.get("layers", ()) if layer.get("kind") == "image")
    return ids


def sides(document):
    return ("front", "back") if document.get("back_enabled") else ("front",)
