"""Compile a stored v2 certificate layout into a v3 certificate document (decision 315, SPEC 12.1).

Nothing stored is rewritten: `EventCertificateTemplateRevision.parameters` and `EventAttendanceCertificate.layout_snapshot`
keep their v2 form and this function runs at render time. The result carries `source: {"kind": "certificate_v2"}`,
which switches the text drawer to the v2 metrics (`rendering_text.draw_compat`) so an old certificate prints with the
same line breaks, baselines and shrink steps. The compiled document is never saved or normalised.

Known, deliberate differences from the old renderer (none moves a glyph): one full-page white rectangle is painted
first, and a v2 image/logo is drawn by the shared image path (same contained placement). A v1 design that prints a
page-sized legacy background image is NOT compilable (`NotCompilable`) and stays on the old renderer.
"""
from . import stocks

SOURCE = {"kind": "certificate_v2"}
# The v2 brand colour tokens (`apps.events.certificates.layout.COLOURS`); a test pins the two tables together.
TOKENS = {"ink": "#142C2A", "teal": "#006E63", "orange": "#FF7447", "citron": "#DFFF8F",
          "sky": "#B5CDFF", "yellow": "#FFD447", "cream": "#FFF4E8"}
TAGS = {"eventDate": "event_date", "issueDate": "issue_date", "crewRole": "role"}
TEXT_KEYS = ("font_family", "font_weight", "font_size_pt", "align", "uppercase", "tracking_pt", "line_height", "shrink_to_fit")


class NotCompilable(ValueError):
    """The layout cannot be expressed on the shared engine; the caller keeps the v2 renderer."""


def _colour(layer):
    return (layer.get("colour") or TOKENS[layer.get("colour_token", "ink")]).upper()


def _text_style(layer):
    from .fonts import canonical
    return {"font_family": canonical(layer.get("font_family", "Outfit")), "font_weight": layer.get("font_weight", 400),
            "font_size_pt": layer.get("font_size_pt", 12), "align": layer.get("align", "left"), "valign": "top",
            "colour": _colour(layer), "uppercase": layer.get("uppercase", False), "tracking_pt": layer.get("tracking_pt", 0),
            "line_height": layer.get("line_height", 1.3), "shrink_to_fit": layer.get("shrink_to_fit", True)}


def _tags(text, frozen):
    """v2 camelCase tags to the shared tag set. `{{crewRole}}` printed "" on rows issued before labels were frozen."""
    for old, new in TAGS.items():
        text = text.replace("{{" + old + "}}", "{{" + new + "}}" if old != "crewRole" or frozen else "")
    return text


def _layer(layer, frozen):
    kind = layer["type"]
    row = {"id": layer["id"], "name": "", "x_mm": layer["x_mm"], "y_mm": layer["y_mm"], "w_mm": layer["width_mm"],
           "h_mm": layer["height_mm"], "rotation": layer.get("rotation", 0), "opacity": round(layer.get("opacity", 1) * 100, 2),
           "locked": bool(layer.get("locked")), "hidden": bool(layer.get("hidden")), "group": None}
    if kind == "text":
        return {**row, "kind": "text", "text": _tags(layer["text"], frozen), **_text_style(layer)}
    if kind == "certificate_id":
        return {**row, "kind": "certificate_id", "format": "full", "text": "{{serial}}", **_text_style(layer)}
    if kind == "certificate_qr":
        return {**row, "kind": "verify_qr"}
    if kind == "image":
        return {**row, "kind": "image", "asset_id": layer["resource_id"], "fit": "contain"}
    if kind == "logo":
        return {**row, "kind": "logo", "source": "organisation", "tile": False}
    if kind == "signature":
        style = _text_style(layer)
        return {**row, "kind": "signature", "signatory_slot": layer["signature_slot"], "show_image": True,
                "show_name": True, "show_title": True, "rule": {"colour": style["colour"], "width_pt": 0.6},
                **{key: style[key] for key in ("font_family", "font_weight", "font_size_pt", "align", "uppercase",
                                                "tracking_pt", "colour")}}
    raise NotCompilable(kind)


def compile_v2(layout, snapshot=None):
    """-> a v3 `kind: "certificate"` document (in memory only)."""
    snapshot = layout if snapshot is None else snapshot
    if layout.get("version") != 2 or layout.get("legacy_background"):
        raise NotCompilable("only a v2 layer layout without a legacy background image")
    width, height = layout["page_width_mm"], layout["page_height_mm"]
    frozen = isinstance((snapshot.get("merge")), dict)
    layers = [_layer(layer, frozen) for layer in sorted(layout["layers"], key=lambda row: row["order"])]
    side = {"page_width_mm": width, "page_height_mm": height, "background": {"kind": "colour", "colour": "#FFFFFF"}}
    return {"version": 3, "kind": "certificate", "stock": stocks.CUSTOM, "page_width_mm": width, "page_height_mm": height,
            "back_enabled": False, "mono": False, "source": dict(SOURCE),
            "watermark": {"kind": "none", "text": "", "asset_id": None, "opacity_pct": 10, "angle_deg": -30, "colour": "#006E63"},
            "front": {**side, "layers": layers}, "back": {**side, "layers": []}}
