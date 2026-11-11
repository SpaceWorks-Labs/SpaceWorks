"""Barcodes and photo filters: the two layer features added beyond the first engine.

A Code128 barcode is drawn as vector bars on a white plate with a 10-module quiet zone
each side, the module width chosen so the code fills the box; the human-readable line
is optional. A photo filter (greyscale, or a two-colour duotone in brand colours) is
applied to the photo's pixels before it is drawn, so PDF, PNG and sheets agree.
"""
from io import BytesIO

QUIET_MODULES = 10
TEXT_PT = 6.0


def barcode_payload(layer, context):
    if layer["source"] == "desk":
        return context.desk_qr or None
    value = str(context.values.get("number") or "").strip()
    return value[:48] or None


def draw_barcode(canvas, layer, context, box):
    from reportlab.graphics.barcode.code128 import Code128
    from reportlab.lib.colors import HexColor
    x, y, w, h = box
    payload = barcode_payload(layer, context)
    if not payload and not context.preview:
        return  # No number or no desk code yet: print nothing rather than a code that resolves to no one.
    payload = payload or "SW-0000"
    try:
        probe = Code128(payload, barWidth=1, quiet=True, lquiet=QUIET_MODULES, rquiet=QUIET_MODULES)
        modules = probe.width
    except Exception:
        return
    canvas.setFillColor(HexColor("#FFFFFF"))
    canvas.rect(x, y, w, h, fill=1, stroke=0)
    text_h = TEXT_PT * 1.25 if layer.get("show_text", True) else 0
    bar_h = max(1.0, h - text_h - 1.0)
    module = w / modules
    code = Code128(payload, barWidth=module, barHeight=bar_h, quiet=True, lquiet=QUIET_MODULES * module,
                   rquiet=QUIET_MODULES * module, humanReadable=False)
    canvas.setFillColor(HexColor("#000000"))
    code.drawOn(canvas, x, y + h - bar_h - 0.5)
    if text_h:
        from .fonts import BRAND
        from .rendering_text import draw
        style = {"font_family": "Outfit", "font_weight": 500 if 500 in BRAND["Outfit"] else 400,
                 "font_size_pt": TEXT_PT, "align": "center", "valign": "middle", "line_height": 1.0,
                 "tracking_pt": 0.6, "shrink_to_fit": True}
        label = payload if layer["source"] == "number" else payload.upper()
        draw(canvas, label, style, colour="#000000", x=x, top=y + text_h, box_width=w, box_height=text_h)


def filtered_photo(data, layer):
    """Photo bytes after the layer's filter; the original bytes when there is none or it fails."""
    kind = layer.get("filter", "none")
    if not data or kind == "none":
        return data
    try:
        from PIL import Image, ImageOps
        with Image.open(BytesIO(data)) as source:
            grey = ImageOps.exif_transpose(source).convert("L")
        grey = ImageOps.autocontrast(grey, cutoff=1)
        image = grey if kind == "grey" else ImageOps.colorize(grey, layer.get("duotone_dark", "#142C2A"),
                                                              layer.get("duotone_light", "#DFFF8F"))
        buffer = BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=92)
        return buffer.getvalue()
    except Exception:
        return data


def barcode_svg_uri(payload):
    """An SVG data URI of the bars alone (the browser's printed-card view draws the label itself)."""
    if not payload:
        return None
    import base64

    from reportlab.graphics import renderSVG
    from reportlab.graphics.barcode import createBarcodeDrawing
    try:
        drawing = createBarcodeDrawing("Code128", value=payload, barWidth=1, barHeight=40, quiet=True,
                                       lquiet=QUIET_MODULES, rquiet=QUIET_MODULES, humanReadable=False)
        svg = renderSVG.drawToString(drawing)
    except Exception:
        return None
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
