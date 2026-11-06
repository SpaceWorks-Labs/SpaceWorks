"""Design files: export a design to JSON and import it elsewhere (parity item G13).

Format `{kind: "spaceworks-card-design", version: 2, domain, document}`. Two older
badge-designer formats (`swe-id-card-design` and `yuyu-id-card-design`) are accepted
as FILE FORMATS only and converted to a v2 document. Imported files are untrusted:
the result is normalised like any save, and uploaded artwork never travels (asset
ids from another space are dropped, with a note of what was removed).
"""
from django.utils.translation import gettext
import json
from uuid import uuid4

from rest_framework.exceptions import ValidationError

from .stocks import CR80

KIND = "spaceworks-card-design"
LEGACY_KINDS = ("swe-id-card-design", "yuyu-id-card-design")
MAX_FILE_BYTES = 300_000
_LEGACY_TEXT = {"header": "heading", "name": None, "idNumber": None, "validUntil": None, "footer": "footerText"}
_LEGACY_FIELDS = {"name": "name", "idNumber": "number", "validUntil": "valid_until"}


def export(design):
    return {"kind": KIND, "version": 2, "domain": design.domain, "document": design.document}


def _legacy_layers(settings):
    width = float(settings.get("widthMm") or CR80[0])
    height = float(settings.get("heightMm") or CR80[1])
    positions = settings.get("elementPositions") or {}
    sizes = settings.get("elementSizes") or {}
    text_sizes = settings.get("elementTextSizes") or {}
    bold = settings.get("elementBold") or {}
    layers = []

    def place(element, kind, **extra):
        spot = positions.get(element) or {}
        size = float(sizes.get(element) or 20)
        x, y = float(spot.get("xMm", 3)), float(spot.get("yMm", 3))
        square = kind in ("photo", "logo", "desk_qr", "verify_qr")
        w = min(size, width - x) if size else 20
        h = min(size if square else max(4.0, float(text_sizes.get(element, 9)) * 0.3528 * 1.6), height - y)
        if w <= 0.5 or h <= 0.3:
            return
        layers.append({"id": str(uuid4()), "kind": kind, "name": element, "x_mm": x, "y_mm": y, "w_mm": w,
                       "h_mm": h, "rotation": 0, "opacity": 100, "locked": False, "hidden": False, **extra})

    text = {"font_family": "Gilroy", "colour": "#142C2A", "align": "left", "valign": "top", "uppercase": False,
            "tracking_pt": 0, "line_height": 1.2, "shrink_to_fit": True}
    for element, key in _LEGACY_TEXT.items():
        if element in _LEGACY_FIELDS:
            if settings.get({"name": "showName", "idNumber": "showIdNumber", "validUntil": "showValidUntil"}[element],
                            element == "name"):
                place(element, "data_field", field=_LEGACY_FIELDS[element], font_weight=700 if bold.get(element) else 400,
                      font_size_pt=max(6, min(96, float(text_sizes.get(element, 10)))), **text)
        elif isinstance(settings.get(key), str) and settings[key].strip():
            place(element, "text", text=settings[key].replace("{", "").replace("}", "")[:500],
                  font_weight=700 if bold.get(element) else 400,
                  font_size_pt=max(6, min(96, float(text_sizes.get(element, 9)))), **text)
    if settings.get("showPhoto"):
        place("photo", "photo", shape="circle" if settings.get("photoShape") == "circle" else "rounded")
    if settings.get("showLogo", True):
        place("logo", "logo", source="space", tile=True)
    if settings.get("showQr", True):
        place("qr", "verify_qr")
    return width, height, layers


def from_legacy(settings):
    if not isinstance(settings, dict):
        raise ValidationError({"file": gettext("This design file has no settings.")})
    width, height, layers = _legacy_layers(settings)
    stock = "cr80-landscape" if (round(width, 1), round(height, 1)) == (85.6, 54.0) else "custom"
    from .default_templates.builders import document
    result = document(stock, width, height, layers, background="#FFFFFF")
    if stock == "custom":
        result["page_width_mm"], result["page_height_mm"] = round(width, 1), round(height, 1)
    return result


def parse(raw):
    """Bytes or text from an uploaded file -> (document, notes). Raises ValidationError."""
    if isinstance(raw, (bytes, bytearray)):
        if len(raw) > MAX_FILE_BYTES:
            raise ValidationError({"file": gettext("That file is too large to be a card design.")})
        raw = raw.decode("utf-8", errors="replace")
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        raise ValidationError({"file": gettext("That file isn't a card design. Choose a .json design file.")}) from None
    if not isinstance(value, dict):
        raise ValidationError({"file": gettext("That file isn't a card design.")})
    kind = value.get("kind")
    if kind == KIND:
        if value.get("version") != 2 or not isinstance(value.get("document"), dict):
            raise ValidationError({"file": gettext("This design file is from a newer or unknown version.")})
        return value["document"], []
    if kind in LEGACY_KINDS:
        return from_legacy(value.get("settings")), ["Converted from an older badge design; check the layout."]
    raise ValidationError({"file": gettext("That file isn't a card design. Choose a .json design file.")})


def strip_foreign_assets(document, owned_ids):
    """Remove images that point at artwork this space does not own; return notes."""
    notes = []
    mark = document.get("watermark") or {}
    if mark.get("kind") == "image" and mark.get("asset_id") not in owned_ids:
        document["watermark"] = {**mark, "kind": "none", "asset_id": None}
        notes.append("The image watermark was not imported; upload it again.")
    for side in ("front", "back"):
        part = document.get(side) or {}
        background = part.get("background") or {}
        if background.get("kind") == "image" and background.get("asset_id") not in owned_ids:
            part["background"] = {"kind": "colour", "colour": background.get("fallback", "#FFFFFF")}
            notes.append(f"The {side} background image was not imported.")
        kept = [layer for layer in part.get("layers", ())
                if layer.get("kind") != "image" or layer.get("asset_id") in owned_ids]
        if len(kept) != len(part.get("layers", ())):
            notes.append(f"Uploaded images on the {side} were not imported.")
        if part:
            part["layers"] = kept
    return notes
