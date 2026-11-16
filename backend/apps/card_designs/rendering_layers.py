"""Draw one free-canvas layer: rotation and opacity around its centre, then its kind."""
from reportlab.lib.colors import HexColor

from .contrast import colour_under, to_hex
from .data_fields import merge
from .rendering_text import is_compat
from .rendering_background import colour_for, draw_image, mono
from .rendering_photo import draw_image_layer as _image, draw_photo as _photo
from .rendering_shapes import draw_shape as _shape

INK = "#142C2A"
PLACEHOLDER = "#D7E9E5"  # teal at ~15 % on cream: ink initials on it pass 4.5:1


def _box(layer, page_height_mm):
    from reportlab.lib.units import mm
    x, w, h = layer["x_mm"] * mm, layer["w_mm"] * mm, layer["h_mm"] * mm
    y = (page_height_mm - layer["y_mm"] - layer["h_mm"]) * mm
    return x, y, w, h


def draw_layer(canvas, document, side, index, layer, context):
    x, y, w, h = _box(layer, side["page_height_mm"])
    canvas.saveState()
    try:
        cx, cy = x + w / 2, y + h / 2
        canvas.translate(cx, cy)
        canvas.rotate(-layer["rotation"])
        canvas.translate(-cx, -cy)
        alpha = layer.get("opacity", 100) / 100
        canvas.setFillAlpha(alpha)
        canvas.setStrokeAlpha(alpha)
        DRAWERS[layer["kind"]](canvas, document, side, index, layer, context, (x, y, w, h))
    finally:
        canvas.restoreState()


def _text(canvas, document, side, index, layer, context, box):
    from .rendering_text import draw
    x, y, w, h = box
    from . import rendering_rich
    colour = layer["colour"]
    if document.get("mono"):
        under = mono(to_hex(colour_under(side, index, context.asset_colours)))
        colour = "#FFFFFF" if under == "#000000" else "#000000"
    if rendering_rich.is_rich(layer) or (layer.get("translations") and getattr(context, "locale", "") in layer["translations"]):
        rendering_rich.draw(canvas, document, layer, context, box, mono_colour=colour if document.get("mono") else None)
        return
    text = merge(layer["text"], context.values, allow_sensitive=context.allow_sensitive)
    if not text.strip():
        return
    from .rendering_text import draw_compat, is_compat
    (draw_compat if is_compat(document) else draw)(canvas, text, layer, colour=colour, x=x, top=y + h, box_width=w,
                                                   box_height=h)


def _rounded(canvas, x, y, w, h, radius, *, fill=True, stroke=False):
    if radius > 0:
        canvas.roundRect(x, y, w, h, min(radius, w / 2, h / 2), fill=int(fill), stroke=int(stroke))
    else:
        canvas.rect(x, y, w, h, fill=int(fill), stroke=int(stroke))


def _perforation(canvas, document, side, index, layer, context, box):
    from .contrast import background_at
    x, y, w, h = box
    canvas.setStrokeColor(HexColor(colour_for(document, layer["colour"])))
    canvas.setLineWidth(0.6)
    canvas.setDash(2.2, 1.8)
    vertical = layer["orientation"] == "vertical"
    if vertical:
        canvas.line(x + w / 2, y, x + w / 2, y + h)
    else:
        canvas.line(x, y + h / 2, x + w, y + h / 2)
    canvas.setDash()
    notch = HexColor("#FFFFFF" if document.get("mono") else to_hex(background_at(
        side["background"], layer["x_mm"], layer["y_mm"], side["page_width_mm"], side["page_height_mm"],
        context.asset_colours)))
    canvas.setFillColor(notch)
    radius = min(w, h, 8) / 2 if not vertical else min(w, 8) / 2
    ends = ((x + w / 2, y), (x + w / 2, y + h)) if vertical else ((x, y + h / 2), (x + w, y + h / 2))
    # A notch is a half-circle bitten out of the card's EDGE; one that ends inside the card (on a
    # band, say) would print as a stray dot, so only the ends that touch an edge get one.
    from reportlab.lib.units import mm
    page_w, page_h = side["page_width_mm"] * mm, side["page_height_mm"] * mm
    ends = [(px, py) for px, py in ends if min(px, py, page_w - px, page_h - py) <= 0.6 * mm]
    for px, py in ends:
        canvas.circle(px, py, radius, fill=1, stroke=0)


def _logo(canvas, document, side, index, layer, context, box):
    x, y, w, h = box
    if layer["source"] == "symbol":
        from .symbol import draw_symbol
        if layer.get("tile"):
            canvas.setFillColor(HexColor("#FFFFFF"))
            _rounded(canvas, x, y, w, h, min(w, h) * 0.12)
        draw_symbol(canvas, x, y, w, h, mono=document.get("mono", False))
        return
    data = context.logos.get(layer["source"])
    if not data:
        return
    if layer.get("tile"):
        canvas.setFillColor(HexColor("#FFFFFF"))
        _rounded(canvas, x, y, w, h, min(w, h) * 0.12)
        pad = min(w, h) * 0.08
        x, y, w, h = x + pad, y + pad, w - 2 * pad, h - 2 * pad
    draw_image(canvas, data, x, y, w, h, grey=document.get("mono", False))


def _qr(canvas, document, side, index, layer, context, box):
    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    x, y, w, h = box
    payload = {"desk_qr": context.desk_qr, "checkin_qr": context.checkin_qr}.get(layer["kind"], context.verify_qr)
    if not payload and not context.preview:
        # No live code of this kind (e.g. the public check is off): print nothing, never a fake QR.
        return
    canvas.setFillColor(HexColor("#FFFFFF"))
    canvas.rect(x, y, w, h, fill=1, stroke=0)
    side_pt = min(w, h)
    if context.preview and is_compat(document):  # a v2 certificate preview keeps its own dummy pattern
        canvas.setFillColor(HexColor(INK))
        for i in range(7):
            for j in range(7):
                if (i + j) % 3 == 0:
                    canvas.rect(x + i * side_pt / 7, y + j * side_pt / 7, side_pt / 9, side_pt / 9, fill=1, stroke=0)
        return
    if context.preview or not payload:
        canvas.setFillColor(HexColor(INK))
        cell = side_pt / 25
        ox, oy = x + (w - side_pt) / 2, y + (h - side_pt) / 2
        for i in range(4, 21):
            for j in range(4, 21):
                if (i * 7 + j * 3) % 5 < 2 or (i in (4, 20) or j in (4, 20)) and (i < 10 or j < 10):
                    canvas.rect(ox + i * cell, oy + j * cell, cell, cell, fill=1, stroke=0)
        return
    widget = QrCodeWidget(payload, barLevel="M", barBorder=4)
    left, bottom, right, top = widget.getBounds()
    drawing = Drawing(side_pt, side_pt, transform=[side_pt / (right - left), 0, 0, side_pt / (top - bottom), 0, 0])
    drawing.add(widget)
    renderPDF.draw(drawing, canvas, x + (w - side_pt) / 2, y + (h - side_pt) / 2)


def _barcode(canvas, document, side, index, layer, context, box):
    from .rendering_extras import draw_barcode
    draw_barcode(canvas, layer, context, box)


def _icon(canvas, document, side, index, layer, context, box):
    from .rendering_icons import draw_icon
    draw_icon(canvas, document, layer, box)


def _certificate(name):
    def drawer(*args):
        from . import rendering_certificate
        return getattr(rendering_certificate, name)(*args)
    return drawer


DRAWERS = {"text": _text, "data_field": _text, "shape": _shape, "band": _shape, "perforation": _perforation,
           "barcode": _barcode, "image": _image, "logo": _logo, "photo": _photo, "desk_qr": _qr, "verify_qr": _qr,
           "checkin_qr": _qr, "certificate_id": _text, "icon": _icon, "signature": _certificate("draw_signature"),
           "signature_row": _certificate("draw_signature_row"), "seal": _certificate("draw_seal")}
