"""One free-canvas layer: geometry, kind-specific properties and their bounds."""
from django.utils.translation import gettext
import math
from uuid import UUID

from rest_framework.exceptions import ValidationError

from . import stocks
from .contrast import HEX
from . import layout_certificate as certificate
from . import layout_studio as studio
from . import studio_icons
from .studio_geometry import POLYGON_SHAPES
from .data_fields import valid_tag, validate_text

KINDS = ("text", "data_field", "image", "logo", "photo", "desk_qr", "verify_qr", "checkin_qr", "barcode", "shape", "band",
         "perforation", "icon", *certificate.CERTIFICATE_KINDS)
QR_KINDS = ("desk_qr", "verify_qr", "checkin_qr")
COMMON = {"id", "kind", "name", "x_mm", "y_mm", "w_mm", "h_mm", "rotation", "opacity", "locked", "hidden", "group"}
TEXT = {"text", "field", "font_family", "font_weight", "font_size_pt", "align", "valign", "colour",
        "uppercase", "tracking_pt", "line_height", "shrink_to_fit",
        # Card Studio (decision 314): rich text, effects, translations.
        "spans", "stroke", "shadow", "highlight", "underline", "translations", "decorative"}
FRAME = {"zoom", "focal_x_pct", "focal_y_pct", "flip_x", "flip_y", "radius_mm", "outline", "shadow"}
EXTRA = {
    "text": TEXT, "data_field": TEXT,
    "image": {"asset_id", "fit", "mask"} | FRAME,
    "logo": {"source", "tile"},
    "photo": {"shape", "filter", "duotone_dark", "duotone_light", "variant"} | FRAME,
    "desk_qr": set(), "verify_qr": set(), "checkin_qr": set(),
    "barcode": {"source", "show_text", "symbology"},
    "shape": {"shape", "fill", "stroke", "stroke_mm", "radius_mm", "fill_gradient", "flip_x", "flip_y", "shadow"},
    "band": {"fill", "radius_mm", "shadow"},
    "perforation": {"colour", "orientation"},
    "icon": studio_icons.ICON_KEYS,  # decision 344(b): a key into the vendored icon library, never path data
    **certificate.EXTRA,  # certificate documents only (decision 315)
}
LOGO_SOURCES = ("space", "organisation", "event", "symbol", *(f"sponsor_{n}" for n in range(1, 7)))
PHOTO_FILTERS = ("none", "grey", "duotone")
PHOTO_VARIANTS = ("original", "cutout", "auto")  # auto = the holder's own use-cut-out choice
SHAPES = ("rect", "rounded", "circle", "ellipse", "arch", "line", *POLYGON_SHAPES)
BARCODE_SOURCES = ("number", "desk")
# Code128 at a 0.19 mm module: the 32-character desk code needs ~75 mm, a short number ~30 mm.
BARCODE_MIN_WIDTH_MM = {"number": 30.0, "desk": 75.0}
BARCODE_MIN_HEIGHT_MM = 6.0
TEXT_DEFAULTS = {"font_family": "Outfit", "font_weight": 400, "font_size_pt": 10, "align": "left",
                 "valign": "top", "colour": "#142C2A", "uppercase": False, "tracking_pt": 0,
                 "line_height": 1.2, "shrink_to_fit": True}


def asset_id(value):
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError({"layers": gettext("Images use an uploaded design asset.")}) from None


def _number(value, minimum, maximum, field):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValidationError({field: gettext('Use a number from {minimum:g} to {maximum:g}.').format(minimum=minimum, maximum=maximum)})
    return round(float(value), 2)


def _hex(value, field, *, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not HEX.match(value):
        raise ValidationError({field: gettext("Use a #RRGGBB colour.")})
    return value.upper()


def _bool(row, key, default=False):
    value = row.get(key, default)
    if type(value) is not bool:
        raise ValidationError({key: gettext("Use true or false.")})
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
        raise ValidationError({"layers": gettext('“{value}” extends beyond the card edge.').format(value=row['name'] or row['kind'])})


def _text(value, row):
    from .fonts import canonical, family_weights
    for key, default in TEXT_DEFAULTS.items():
        row[key] = value.get(key, default)
    row["font_family"] = canonical(row["font_family"])  # a legacy "Gilroy" layer saves as Outfit
    if row["kind"] == "data_field":
        field = value.get("field")
        if not isinstance(field, str) or not valid_tag(field):
            raise ValidationError({"layers": gettext("Choose a data field for this layer.")})
        row["field"] = field
        row["text"] = "{{" + field + "}}"
    else:
        row["text"] = validate_text(value.get("text", ""))
    weights = family_weights(row["font_family"])
    if not weights:
        raise ValidationError({"layers": gettext('“{value}” is not in the card font library.').format(value=row['font_family'])})
    if type(row["font_weight"]) is not int or row["font_weight"] not in weights:
        raise ValidationError({"layers": gettext('{value} ships weights {value2}.').format(value=row['font_family'], value2=', '.join(map(str, weights)))})
    row["font_size_pt"] = _number(row["font_size_pt"], 6, 96, "font_size_pt")
    row["tracking_pt"] = _number(row["tracking_pt"], -2, 10, "tracking_pt")
    row["line_height"] = _number(row["line_height"], 0.8, 3, "line_height")
    if row["align"] not in ("left", "center", "right") or row["valign"] not in ("top", "middle", "bottom"):
        raise ValidationError({"layers": gettext("Align text left, centre or right, and top, middle or bottom.")})
    row["colour"] = _hex(row["colour"], "colour")
    row["uppercase"] = _bool(row, "uppercase")
    row["shrink_to_fit"] = _bool(row, "shrink_to_fit", True)


def _check_face(family, weight):
    """A span's face must be in the library; a bare weight is checked against the layer's own family later."""
    from .fonts import canonical, family_weights
    if family is None:
        return
    weights = family_weights(canonical(family))
    if not weights:
        raise ValidationError({"spans": gettext('“{value}” is not in the card font library.').format(value=family)})
    if weight is not None and weight not in weights:
        raise ValidationError({"spans": gettext('{value} ships weights {value2}.').format(value=family, value2=', '.join(map(str, weights)))})


def _photo_filter(value, row):
    row["filter"] = value.get("filter", "none")
    if row["filter"] not in PHOTO_FILTERS:
        raise ValidationError({"layers": gettext("Photo filters are none, greyscale or duotone.")})
    row["duotone_dark"] = _hex(value.get("duotone_dark", "#142C2A"), "duotone_dark")
    row["duotone_light"] = _hex(value.get("duotone_light", "#DFFF8F"), "duotone_light")


def _barcode(value, row):
    """A barcode of the printed number, or of the desk code (the same staff-only payload as the desk QR, for USB
    scanners at the desk; never the check token). `symbology` (decision 345(c), default Code 128 and then omitted)."""
    from .barcode_symbols import SYMBOLOGIES, minimum
    row["source"] = value.get("source", "number")
    row["show_text"] = _bool(value, "show_text", True)
    if row["source"] not in BARCODE_SOURCES:
        raise ValidationError({"layers": gettext("A barcode carries the card number or the desk code.")})
    symbology = value.get("symbology", "code128")
    if symbology not in SYMBOLOGIES:
        raise ValidationError({"layers": gettext("Barcodes are Code 128, Code 39, EAN-13, UPC-A, PDF417, Data Matrix or Aztec.")})
    if symbology != "code128":
        row["symbology"] = symbology
    min_w, min_h = minimum(symbology, row["source"])
    if row["w_mm"] < min_w - 0.01 or row["h_mm"] < min_h - 0.01 or row["opacity"] != 100 or row["rotation"] % 90:
        raise ValidationError({"layers": gettext('This barcode needs {minimum:g} x {BARCODE_MIN_HEIGHT_MM:g} mm, full opacity and a right-angle turn so scanners can read it.').format(minimum=min_w, BARCODE_MIN_HEIGHT_MM=min_h)})


def normalize_layer(value, width, height, stock, document_kind="card"):
    if not isinstance(value, dict) or value.get("kind") not in KINDS:
        raise ValidationError({"layers": gettext("Unknown layer kind.")})
    kind = value["kind"]
    certificate.check_allowed(kind, document_kind)
    if kind == "band":  # early drafts stored shape keys on bands; they carry no meaning there
        value = {key: item for key, item in value.items() if key not in ("shape", "stroke", "stroke_mm")}
    if set(value) - (COMMON | EXTRA[kind]):
        raise ValidationError({"layers": gettext('Unknown properties on a {kind} layer.').format(kind=kind)})
    name = value.get("name", "")
    if not isinstance(name, str) or len(name) > 40:
        raise ValidationError({"layers": gettext("Layer names are at most 40 characters.")})
    row = {"id": asset_id(value.get("id")), "kind": kind, "name": name}
    row["locked"] = _bool(value, "locked")
    row["hidden"] = _bool(value, "hidden")
    row["group"] = asset_id(value["group"]) if value.get("group") else None
    if row["hidden"] and document_kind == "certificate" and kind in certificate.ALWAYS_PRESENT:
        raise ValidationError({"layers": gettext("The verification QR and certificate number cannot be hidden.")})
    _geometry(value, row, width, height)
    if kind == "data_field" and "spans" in value:
        raise ValidationError({"layers": gettext("Only text layers take spans.")})
    if kind == "text" and value.get("spans") is not None:
        clean, joined = studio.spans(value["spans"], _check_face)
        value = {**value, "text": joined}
    if kind in ("text", "data_field"):
        _text(value, row)
        if kind == "text" and value.get("spans") is not None:
            row["spans"] = clean
        studio.text_extras(value, row)
        if value.get("decorative"):  # background lettering: exempt from the 4.5:1 text check, never read aloud
            row["decorative"] = studio.flag(value["decorative"], "decorative")
    elif kind == "image":
        row["asset_id"] = asset_id(value.get("asset_id"))
        row["fit"] = value.get("fit", "contain")
        if row["fit"] not in studio.FITS:
            raise ValidationError({"layers": gettext("Images cover, contain or stretch their box.")})
        studio.frame(value, row)
    elif kind == "logo":
        row["source"] = value.get("source", "space")
        row["tile"] = _bool(value, "tile")
        if row["source"] not in LOGO_SOURCES:
            raise ValidationError({"layers": gettext("Logos come from the space, organisation, event or symbol.")})
        if document_kind == "certificate" and row["source"] != "symbol":
            raise ValidationError({"layers": gettext("On a certificate, upload a logo as an image layer; only the Space Works symbol is a logo slot.")})
    elif kind == "photo":
        row["shape"] = value.get("shape", "rounded")
        if row["shape"] not in ("circle", "rounded", "square", "arch"):
            raise ValidationError({"layers": gettext("Photos are circle, rounded, square or arch.")})
        _photo_filter(value, row)
        if value.get("variant", "original") not in PHOTO_VARIANTS:
            raise ValidationError({"layers": gettext("A photo shows the original, the cut-out or the holder's choice.")})
        if value.get("variant", "original") != "original":
            row["variant"] = value["variant"]
        studio.frame(value, row, allow_mask=False)
    elif kind in QR_KINDS:
        minimum = stocks.qr_minimum_mm(stock)
        if min(row["w_mm"], row["h_mm"]) < minimum - 0.01 or row["opacity"] != 100 or row["rotation"] % 90:
            raise ValidationError({"layers": gettext('QR codes need {minimum:g} mm, full opacity and a right-angle turn.').format(minimum=minimum)})
    elif kind == "barcode":
        _barcode(value, row)
    elif kind in ("shape", "band"):
        # A band carries only its own keys (fill, radius), so a normalised band normalises again.
        row["fill"] = _hex(value.get("fill", "#006E63" if kind == "band" else None), "fill", nullable=True)
        row["radius_mm"] = _number(value.get("radius_mm", 0), 0, 20, "radius_mm")
        if kind == "shape":
            row["shape"] = value.get("shape", "rect")
            if row["shape"] not in SHAPES:
                raise ValidationError({"layers": gettext("Shapes are rectangles, rounded, circles, ellipses, arches, lines, triangles, diamonds, hexagons or stars.")})
            if value.get("fill_gradient") is not None:
                row["fill_gradient"] = studio.gradient(value["fill_gradient"], "fill_gradient", alpha=True)
            for key in ("flip_x", "flip_y"):
                if key in value and studio.flag(value[key], key):
                    row[key] = True
            row["stroke"] = _hex(value.get("stroke"), "stroke", nullable=True)
            row["stroke_mm"] = _number(value.get("stroke_mm", 0.3), 0, 5, "stroke_mm")
        if value.get("shadow") is not None:
            row["shadow"] = studio.shadow(value["shadow"])
        if row["fill"] is None and row.get("stroke") is None and "fill_gradient" not in row:
            raise ValidationError({"layers": gettext("A shape needs a fill or an outline.")})
    elif kind == "icon":
        studio_icons.normalize(value, row, _hex, studio.flag)
    elif kind in certificate.CERTIFICATE_KINDS:
        certificate.normalize(kind, value, row, _text)
    elif kind == "perforation":
        row["colour"] = _hex(value.get("colour", "#D5D0C6"), "colour")
        row["orientation"] = value.get("orientation", "vertical")
        if row["orientation"] not in ("vertical", "horizontal"):
            raise ValidationError({"layers": gettext("Perforations run vertically or horizontally.")})
    return row
