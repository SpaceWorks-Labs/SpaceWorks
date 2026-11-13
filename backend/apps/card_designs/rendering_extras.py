"""Barcodes and photo filters: the two layer features added beyond the first engine.

A barcode (any symbology of `barcode_symbols`) is drawn as vector modules on a white plate: linear codes fill the
box with their quiet zones (10 modules for Code 128), matrix codes keep square modules; the human-readable line is
optional on linear codes. A photo filter (greyscale, or a two-colour duotone in brand colours) is
applied to the photo's pixels before it is drawn, so PDF, PNG and sheets agree.
"""
from io import BytesIO

TEXT_PT = 6.0


def barcode_payload(layer, context):
    if layer["source"] == "desk":
        return context.desk_qr or None
    value = str(context.values.get("number") or "").strip()
    return value[:48] or None


SAMPLES = {"ean13": "590123412345", "upca": "03600029145"}


def draw_barcode(canvas, layer, context, box):
    """Any symbology through `barcode_symbols` (one encoder for print and the designer), black on a white plate."""
    from reportlab.lib.colors import HexColor
    from .barcode_symbols import encode, rects
    x, y, w, h = box
    symbology = layer.get("symbology", "code128")
    payload = barcode_payload(layer, context)
    encoded = encode(symbology, payload) if payload else None
    if encoded is None and context.preview:
        encoded = encode(symbology, SAMPLES.get(symbology, "SW-0000"))
    if encoded is None:
        return  # No number, no desk code, or a number this symbology cannot carry: print nothing, never a wrong code.
    canvas.setFillColor(HexColor("#FFFFFF"))
    canvas.rect(x, y, w, h, fill=1, stroke=0)
    linear = encoded["kind"] == "linear"
    text_h = TEXT_PT * 1.25 if linear and layer.get("show_text", True) else 0
    canvas.setFillColor(HexColor("#000000"))
    for left, top, width, height in rects(encoded, w, h, text_h, gap=1.0):
        canvas.rect(x + left, y + h - top - height, width, height, fill=1, stroke=0)
    if text_h:
        from .fonts import BRAND
        from .rendering_text import draw
        style = {"font_family": "Outfit", "font_weight": 500 if 500 in BRAND["Outfit"] else 400,
                 "font_size_pt": TEXT_PT, "align": "center", "valign": "middle", "line_height": 1.0,
                 "tracking_pt": 0.6, "shrink_to_fit": True}
        label = encoded["text"] if layer["source"] == "number" else encoded["text"].upper()
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


def barcode_svg_uri(payload, symbology="code128"):
    """An SVG data URI of the symbol alone (the browser's printed-card view draws the label itself), from the same
    encoding and geometry as print: linear codes stretch to the box, matrix codes keep square modules."""
    import base64

    from .barcode_symbols import encode, rects
    encoded = encode(symbology, payload) if payload else None
    if encoded is None:
        return None
    linear = encoded["kind"] == "linear"
    width = len(encoded["bars"]) + sum(encoded["quiet"]) if linear else len(encoded["rows"][0])
    height = 40 if linear else len(encoded["rows"])
    body = "".join(f'<rect x="{x}" y="{y}" width="{w}" height="{h}"/>' for x, y, w, h in rects(encoded, width, height, gap=0))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" preserveAspectRatio="'
           f'{"none" if linear else "xMidYMid meet"}" shape-rendering="crispEdges"><rect width="{width}" height="{height}" '
           f'fill="#FFFFFF"/><g fill="#000000">{body}</g></svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
