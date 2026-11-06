"""Closed v2 layout shared with the frozen E/ARTWORK seed schema."""

from copy import deepcopy
import math
import re
from uuid import UUID, uuid5, NAMESPACE_URL

from rest_framework.exceptions import ValidationError
from apps.operations.printable_layout import number

TAGS = frozenset(("name", "event", "eventDate", "organisation", "issueDate", "crewRole",
                  "kind", "award", "role", "place"))
# Kind/award/role/place are frozen at certificate issuance; badges have no such labels.
BADGE_TAGS = TAGS - {"kind", "award", "role", "place"}
COLOURS = {"ink": "#142C2A", "teal": "#006E63", "orange": "#FF7447", "citron": "#DFFF8F",
           "sky": "#B5CDFF", "yellow": "#FFD447", "cream": "#FFF4E8"}
SLOTS = {"logo": "logo", "photo": "selected_member_photo", "certificate_qr": "certificate_verification_qr",
         "event_credential_qr": "event_credential_qr"}
COMMON = {"id", "order", "type", "x_mm", "y_mm", "width_mm", "height_mm", "rotation", "opacity",
          "locked", "hidden"}
TEXT = {"text", "font_family", "font_weight", "font_size_pt", "align", "shrink_to_fit", "italic",
        "uppercase", "tracking_pt", "line_height", "colour_token", "colour"}
# A signature prints a signatory's image, name and title; the slot names signatory 1-3 (C4).
SIGNATURE = (TEXT - {"text"}) | {"signature_slot"}
HEX = re.compile(r"#[0-9A-Fa-f]{6}")
STOCKS = {"a6-portrait": (105, 148), "4x6": (101.6, 152.4), "3x4": (76.2, 101.6),
          "4x3": (101.6, 76.2), "cr80-portrait": (53.98, 85.6), "cr80-landscape": (85.6, 53.98)}
# The six above have packaged default designs (the frozen artwork contract). A badge may also
# use A6 landscape or a custom size (40-300 mm each side, 0.1 mm steps; SPEC §3.1, G13); those
# start from a blank or imported design.
DESIGN_STOCKS = {**STOCKS, "a6-landscape": (148, 105)}
CUSTOM_STOCK = "custom"
CUSTOM_RANGE_MM = (40, 300)
DESIGN_STOCK_CHOICES = (*DESIGN_STOCKS, CUSTOM_STOCK)


def _uuid(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError({"layers": "Use stable UUID layer/resource IDs."}) from exc


def normalize_document(value, *, badge=False):
    if (not isinstance(value, dict) or set(value) != {"version", "page_width_mm", "page_height_mm", "layers"}
            or type(value["version"]) is not int or value["version"] != 2):
        raise ValidationError({"parameters": "Use the closed version 2 layout document."})
    result = deepcopy(value)
    width = number(value["page_width_mm"], 30 if badge else 100, 420, "page_width_mm")
    height = number(value["page_height_mm"], 30 if badge else 100, 420, "page_height_mm")
    layers = value["layers"]
    if not isinstance(layers, list) or not 1 <= len(layers) <= 20:
        raise ValidationError({"layers": "Choose 1–20 layers."})
    normalized = [_layer(layer, width, height, badge) for layer in layers]
    if (len({row["id"] for row in normalized}) != len(layers)
            or sorted(row["order"] for row in normalized) != list(range(len(layers)))):
        raise ValidationError({"layers": "Layer IDs must be unique and order must be contiguous from zero."})
    if sum(row.get("font_family") == "Unbounded" for row in normalized) > 1:
        raise ValidationError({"layers": "Use at most one Unbounded accent."})
    result.update(page_width_mm=width, page_height_mm=height, layers=sorted(normalized, key=lambda row: row["order"]))
    return result


def _layer(value, width, height, badge):
    if not isinstance(value, dict):
        raise ValidationError({"layers": "Expected layer objects."})
    kind = value.get("type")
    kinds = {"text", "image", "logo", "certificate_id", "certificate_qr", "signature"}
    if badge:
        kinds = {"text", "image", "logo", "photo", "event_credential_qr"}
    extra = (TEXT if kind in ("text", "certificate_id") else SIGNATURE if kind == "signature"
             else {"resource_id", "resource_slot"})
    if kind not in kinds or set(value) - (COMMON | extra):
        raise ValidationError({"layers": "Unknown layer type or properties."})
    row = deepcopy(value)
    row["id"] = _uuid(value.get("id"))
    if type(value.get("order")) is not int or not 0 <= value["order"] < 20:
        raise ValidationError({"layers": "Invalid layer order."})
    for key, maximum in (("x_mm", width), ("y_mm", height), ("width_mm", width), ("height_mm", height)):
        row[key] = number(value.get(key), 0.1 if key.startswith(("width", "height")) else 0, maximum, key)
    row["rotation"] = number(value.get("rotation", 0), -360, 360, "rotation")
    row["opacity"] = number(value.get("opacity", 1), 0, 1, "opacity")
    for key in ("locked", "hidden"):
        if key in row and type(row[key]) is not bool:
            raise ValidationError({"layers": f"{key} must be boolean."})
    if row.get("hidden") and kind in ("certificate_qr", "certificate_id", "event_credential_qr"):
        raise ValidationError({"layers": "The verification QR and certificate ID cannot be hidden."})
    theta = math.radians(row["rotation"])
    half_w = (abs(math.cos(theta)) * row["width_mm"] + abs(math.sin(theta)) * row["height_mm"]) / 2
    half_h = (abs(math.sin(theta)) * row["width_mm"] + abs(math.cos(theta)) * row["height_mm"]) / 2
    cx, cy = row["x_mm"] + row["width_mm"] / 2, row["y_mm"] + row["height_mm"] / 2
    if min(cx-half_w, cy-half_h) < -1e-6 or cx+half_w > width+1e-6 or cy+half_h > height+1e-6:
        raise ValidationError({"layers": "A rotated layer extends beyond the page."})
    if kind in ("text", "certificate_id"):
        _text_style(row, badge)
    elif kind == "signature":
        if type(value.get("signature_slot")) is not int or value["signature_slot"] not in (1, 2, 3):
            raise ValidationError({"layers": "A signature names signatory 1, 2 or 3."})
        _text_style(row, badge)
        row.pop("text", None)
        if min(row["width_mm"], row["height_mm"]) < 10:
            raise ValidationError({"layers": "A signature needs at least 10 mm for its image, name and title."})
    elif kind == "image":
        row["resource_id"] = _uuid(value.get("resource_id"))
        if "resource_slot" in value:
            raise ValidationError({"layers": "Images use owned resource IDs."})
    else:
        if value.get("resource_slot") != SLOTS[kind] or "resource_id" in value:
            raise ValidationError({"layers": "Use the typed resource slot for this layer."})
        if kind.endswith("qr") and (min(row["width_mm"], row["height_mm"]) < 20
                or row["opacity"] != 1 or row["rotation"] % 90):
            raise ValidationError({"layers": "QR slots need 20 mm, full opacity and right-angle rotation."})
    return row


def _text_style(row, badge=False):
    defaults = dict(font_family="Gilroy", font_weight=400, font_size_pt=12, align="left",
                    shrink_to_fit=True, italic=False, uppercase=False, tracking_pt=0,
                    line_height=1.3, colour_token="ink", text="")
    for key, value in defaults.items():
        row.setdefault(key, value)
    if (row["font_family"] not in ("Gilroy", "Unbounded")
            or type(row["font_weight"]) is not int or row["font_weight"] not in (400, 500, 600, 700)
            or row["align"] not in ("left", "center", "right") or row["colour_token"] not in COLOURS):
        raise ValidationError({"layers": "Use approved brand type and colour tokens."})
    if "colour" in row and (not isinstance(row["colour"], str) or not HEX.fullmatch(row["colour"])):
        raise ValidationError({"layers": "Use a #RRGGBB colour."})
    for key in ("shrink_to_fit", "uppercase", "italic"):
        if type(row[key]) is not bool:
            raise ValidationError({"layers": f"{key} must be boolean."})
    if row["italic"]:
        # Neither bundled family (Gilroy, Unbounded) ships a true italic face; a slanted
        # regular face is not italic, so it is refused rather than faked.
        raise ValidationError({"italic": f"{row['font_family']} has no italic face in the approved font kit. "
                                         "Use weight or size for emphasis instead."})
    row["font_size_pt"] = number(row["font_size_pt"], 6, 96, "font_size_pt")
    row["tracking_pt"] = number(row["tracking_pt"], -1, 8, "tracking_pt")
    row["line_height"] = number(row["line_height"], 1, 3, "line_height")
    text = row["text"]
    if not isinstance(text, str) or len(text) > 500:
        raise ValidationError({"text": "Use at most 500 characters."})
    if "SWEC2." in text:
        raise ValidationError({"text": "Live event credentials cannot be stored in design text."})
    if any(tag not in (BADGE_TAGS if badge else TAGS) for tag in re.findall(r"{{(.*?)}}", text)) or re.search(r"[{}]", re.sub(r"{{[A-Za-z]+}}", "", text)):
        raise ValidationError({"text": "Unknown merge tag. Contact and arbitrary object fields are forbidden."})


def upgrade_legacy(value, *, include_labels=True):
    """Lossless geometry/name binding; old stored revisions are not rewritten."""
    box = value["name_box"]
    result = {"version": 2, "page_width_mm": value["page_width_mm"], "page_height_mm": value["page_height_mm"],
            "layers": [{"id": str(uuid5(NAMESPACE_URL, "spaceworks:certificate:legacy-name")), "order": 0,
                        "type": "text", "rotation": 0, "text": "{{name}}", "font_family": "Gilroy",
                        "font_weight": 700 if box["bold"] else 400, "align": box["align"],
                        "font_size_pt": box["font_size_pt"], "shrink_to_fit": True,
                        **{key: box[key] for key in ("x_mm", "y_mm", "width_mm", "height_mm")}}]}
    if include_labels:
        width, height = value["page_width_mm"], value["page_height_mm"]
        for index, (text, y, size, weight) in enumerate((
                ("Certificate of Attendance", 34, 28, 700), ("This certifies that", 57, 14, 400),
                ("attended", 101, 14, 400), ("{{event}}", 117, 20, 700),
                ("{{eventDate}}", 138, 13, 400), ("{{organisation}}", 167, 12, 400))):
            result["layers"].append({"id": str(uuid5(NAMESPACE_URL, f"spaceworks:certificate:legacy-label:{index}")),
                "order": index+1, "type": "text", "rotation": 0, "text": text,
                "x_mm": width*.075, "y_mm": y*height/210, "width_mm": width*.85, "height_mm": height*.07,
                "font_family": "Gilroy", "font_weight": weight, "font_size_pt": size,
                "align": "center", "shrink_to_fit": True})
    return result
