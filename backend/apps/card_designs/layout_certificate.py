"""Certificate layer kinds on the shared engine (decision 315, SPEC section 12.2).

`signature`, `signature_row`, `seal` and `certificate_id` exist only in a `kind: "certificate"` document; a
certificate document in turn refuses the person-bound card kinds (photo, desk/check-in QR, barcode, perforation).
A signature is bound to a signatory SLOT (1-3), never to bytes: the image, name and title are resolved at render
time from the frozen issuance snapshot, and only for a signatory whose approval state allows it.
"""
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from . import layout_studio as studio
from .data_fields import validate_text

CERTIFICATE_KINDS = ("signature", "signature_row", "seal", "certificate_id")
CARD_ONLY_KINDS = ("photo", "desk_qr", "checkin_qr", "barcode", "perforation")
ALWAYS_PRESENT = ("verify_qr", "certificate_id")  # a certificate can always be verified: these are never hidden
SLOTS = (1, 2, 3)
SEAL_STYLES = ("ring", "scallop", "star")
ID_FORMATS = ("full", "short")
STYLE = {"font_family", "font_weight", "font_size_pt", "colour", "align", "uppercase", "tracking_pt"}
SIGNATURE_PARTS = {"show_image", "show_name", "show_title", "rule"}
SEAL_KEYS = {"style", "fill", "stroke", "stroke_mm", "label", "label_style", "ring_text", "ring_text_colour"}
ID_KEYS = {"format", "text", "font_family", "font_weight", "font_size_pt", "align", "valign", "colour", "uppercase",
           "tracking_pt", "line_height", "shrink_to_fit"}
EXTRA = {"signature": {"signatory_slot"} | SIGNATURE_PARTS | STYLE,
         "signature_row": {"slots", "gap_mm"} | SIGNATURE_PARTS | STYLE,
         "seal": SEAL_KEYS, "certificate_id": ID_KEYS}
STYLE_DEFAULTS = {"font_family": "Outfit", "font_weight": 600, "font_size_pt": 12, "colour": "#142C2A",
                  "align": "center", "uppercase": False, "tracking_pt": 0}
MIN_SIGNATURE_MM = 10.0


def check_allowed(kind, document_kind):
    """The kinds a document kind may carry; raises for a certificate kind on a card and a card-only kind on a certificate."""
    if kind in CERTIFICATE_KINDS and document_kind != "certificate":
        raise ValidationError({"layers": gettext("Signature, seal and certificate-number layers belong to certificate designs.")})
    if kind in CARD_ONLY_KINDS and document_kind == "certificate":
        raise ValidationError({"layers": gettext("Photos, desk and check-in codes, barcodes and perforations are for cards, not certificates.")})


def _style(value, row):
    """Text style shared by `signature` and `signature_row`, validated against the card font library."""
    from .fonts import canonical, family_weights
    for key, default in STYLE_DEFAULTS.items():
        row[key] = value.get(key, default)
    row["font_family"] = canonical(row["font_family"])
    weights = family_weights(row["font_family"])
    if not weights or type(row["font_weight"]) is not int or row["font_weight"] not in weights:
        raise ValidationError({"layers": gettext("Use a font and weight from the card font library.")})
    row["font_size_pt"] = studio.num(row["font_size_pt"], 6, 96, "font_size_pt")
    row["tracking_pt"] = studio.num(row["tracking_pt"], -2, 10, "tracking_pt")
    row["colour"] = studio.hexc(row["colour"], "colour")
    row["uppercase"] = studio.flag(row["uppercase"], "uppercase")
    if row["align"] not in ("left", "center", "right"):
        raise ValidationError({"layers": gettext("Align text left, centre or right.")})


def _parts(value, row):
    for key in ("show_image", "show_name", "show_title"):
        row[key] = studio.flag(value.get(key, True), key)
    rule = value.get("rule", {"colour": row["colour"], "width_pt": 0.6})
    if rule is None:
        row["rule"] = None
    else:
        studio.closed(rule, {"colour", "width_pt"}, "rule")
        row["rule"] = {"colour": studio.hexc(rule.get("colour", row["colour"]), "rule"),
                       "width_pt": studio.num(rule.get("width_pt", 0.6), 0.1, 4, "rule")}
    if min(row["w_mm"], row["h_mm"]) < MIN_SIGNATURE_MM:
        raise ValidationError({"layers": gettext("A signature needs at least 10 mm for its image, name and title.")})


def _signature(value, row):
    slot = value.get("signatory_slot")
    if type(slot) is not int or slot not in SLOTS:
        raise ValidationError({"layers": gettext("A signature names signatory 1, 2 or 3.")})
    row["signatory_slot"] = slot
    _style(value, row)
    _parts(value, row)


def _signature_row(value, row):
    slots = value.get("slots")
    if (not isinstance(slots, list) or not 1 <= len(slots) <= 3 or len(set(slots)) != len(slots)
            or any(type(slot) is not int or slot not in SLOTS for slot in slots)):
        raise ValidationError({"layers": gettext("A signature row names one to three different signatories (1, 2 or 3).")})
    row["slots"] = sorted(slots)
    row["gap_mm"] = studio.num(value.get("gap_mm", 8), 4, 40, "gap_mm")
    _style(value, row)
    _parts(value, row)


def _seal(value, row):
    row["style"] = value.get("style", "ring")
    if row["style"] not in SEAL_STYLES:
        raise ValidationError({"layers": gettext("A seal is a ring, a scalloped rosette or a star.")})
    row["fill"] = studio.hexc(value["fill"], "fill") if value.get("fill") is not None else None
    row["stroke"] = studio.hexc(value["stroke"], "stroke") if value.get("stroke") is not None else None
    row["stroke_mm"] = studio.num(value.get("stroke_mm", 0.6), 0, 5, "stroke_mm")
    if row["fill"] is None and row["stroke"] is None:
        raise ValidationError({"layers": gettext("A seal needs a fill or an outline.")})
    row["label"] = validate_text(value.get("label", ""), limit=24)
    style = studio.closed(value.get("label_style", {}), {"font_family", "font_weight", "font_size_pt", "colour"}, "label_style")
    clean = {}
    _style({"font_weight": 700, "font_size_pt": 14, **style}, clean)
    row["label_style"] = {key: clean[key] for key in ("font_family", "font_weight", "font_size_pt", "colour")}
    ring = value.get("ring_text", "")
    if not isinstance(ring, str) or len(ring) > 40 or "{" in ring or "}" in ring or any(ord(char) > 0x24F for char in ring):
        raise ValidationError({"layers": gettext("Ring text is plain Latin text of at most 40 characters.")})
    row["ring_text"] = ring
    row["ring_text_colour"] = studio.hexc(value.get("ring_text_colour", row["stroke"] or row["fill"] or "#142C2A"), "ring_text_colour")


def _certificate_id(value, row, text_style):
    row["format"] = value.get("format", "full")
    if row["format"] not in ID_FORMATS:
        raise ValidationError({"layers": gettext("The certificate number is shown in full or short.")})
    text_style({**value, "text": ""}, row)
    row["text"] = "{{serial}}" if row["format"] == "full" else "{{serial_short}}"


def normalize(kind, value, row, text_style):
    """Fill `row` for a certificate-only layer kind. `text_style` is `layout_layers._text` (passed in, no import cycle)."""
    if kind == "signature":
        _signature(value, row)
    elif kind == "signature_row":
        _signature_row(value, row)
    elif kind == "seal":
        _seal(value, row)
    else:
        _certificate_id(value, row, text_style)


def printed_slots(document):
    """Signatory slots a certificate document prints (both sides, hidden layers included: the safe side), for the approval gate."""
    found = set()
    for side in ("front", "back"):
        for layer in (document.get(side) or {}).get("layers", ()):
            if layer["kind"] == "signature":
                found.add(layer["signatory_slot"])
            elif layer["kind"] == "signature_row":
                found.update(layer["slots"])
    return sorted(found)
