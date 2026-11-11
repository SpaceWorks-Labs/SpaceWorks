"""Staff ID card templates (O-B4 part 2): every member look, re-labelled for staff, plus a STAFF band.

A staff card reuses the shipped member/programme layouts, so the designer, previews, light and dark themes
and stock presets all work unchanged. This post-processor only swaps what is member-specific:

* `{{programme}}`/`{{event}}` eyebrow text becomes "Staff"; plan and programme fields show the held roles;
  member-since shows the machine scope; any desk QR becomes the public check QR (a staff card has no desk QR);
* a teal band across the bottom edge reads STAFF in cream (the same pairing as the header band, so it passes
  the 4.5:1 contrast check in both themes).
"""
from .builders import CREAM, TEAL, Builder

BAND_HEIGHT = 3.4
FIELD_SWAPS = {"plan": "roles", "programme": "roles", "event": "roles", "member_since": "machine_scope",
               "valid_until": "valid_until", "role": "roles"}
LABEL_SWAPS = {"Plan": "Roles", "Programme": "Roles", "Event": "Roles", "Member since": "Scope"}


def _relabel(layer):
    layer = dict(layer)
    if layer["kind"] == "desk_qr":
        layer["kind"] = "verify_qr"
    elif layer["kind"] == "data_field":
        layer["field"] = FIELD_SWAPS.get(layer["field"], layer["field"])
    elif layer["kind"] == "text":
        text = layer.get("text") or ""
        if "{{programme}}" in text or "{{event}}" in text:
            layer["text"] = "Staff"
        elif text in LABEL_SWAPS:
            layer["text"] = LABEL_SWAPS[text]
        elif text in ("Show at the desk", "Show at the door"):
            layer["text"] = "Scan to check"
    return layer


def _band(side):
    width, height = side["page_width_mm"], side["page_height_mm"]
    builder = (Builder("staff-band")
               .band("Staff band", 0, height - BAND_HEIGHT, width, BAND_HEIGHT, TEAL)
               .text("Staff band text", "Staff", 0, height - BAND_HEIGHT + 0.6, width, 2.4, size=6, weight=700,
                     colour=CREAM, align="center", upper=True, tracking=1.2))
    return builder.layers


def staff_document(document, theme="light"):
    """-> the staff version of a member/programme template document (see the module docstring)."""
    front = {**document["front"], "layers": [_relabel(layer) for layer in document["front"]["layers"]]}
    front["layers"] = front["layers"] + _band(front)
    back = {**document["back"], "layers": [_relabel(layer) for layer in document["back"]["layers"]]}
    return {**document, "front": front, "back": back}
