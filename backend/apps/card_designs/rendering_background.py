"""Side backgrounds (colour, gradient, image with dim), the watermark and the PREVIEW mark.

Backgrounds stop at the trim: there is no bleed (SPEC §3.1). Mono print mode draws
every side on white for laser and thermal printers.
"""
from io import BytesIO

from .contrast import luminance, rgb


def mono(colour):
    return "#000000" if luminance(rgb(colour)) < 0.4 else "#FFFFFF"


def colour_for(document, colour):
    return mono(colour) if document.get("mono") else colour


def _image(canvas, data, x, y, width, height, *, fit, alpha=1.0, grey=False):
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    with Image.open(BytesIO(data)) as source:
        image = source.convert("LA" if grey else "RGBA")
        image.load()
    iw, ih = image.size
    scale = (max if fit == "cover" else min)(width / iw, height / ih)
    dw, dh = iw * scale, ih * scale
    canvas.saveState()
    path = canvas.beginPath()
    path.rect(x, y, width, height)
    canvas.clipPath(path, stroke=0, fill=0)
    canvas.setFillAlpha(alpha)
    canvas.drawImage(ImageReader(image), x + (width - dw) / 2, y + (height - dh) / 2, width=dw, height=dh,
                     mask="auto")
    canvas.restoreState()


def draw_image(canvas, data, x, y, width, height, *, fit="contain", alpha=1.0, grey=False):
    """Draw image bytes into a box; unreadable bytes draw nothing rather than failing a card."""
    if not data:
        return False
    try:
        _image(canvas, data, x, y, width, height, fit=fit, alpha=alpha, grey=grey)
    except Exception:
        return False
    return True


def draw_background(canvas, document, side, context):
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    width, height = side["page_width_mm"] * mm, side["page_height_mm"] * mm
    background = side["background"]
    if document.get("mono"):
        canvas.setFillColor(HexColor("#FFFFFF"))
        canvas.rect(0, 0, width, height, fill=1, stroke=0)
        return
    kind = background["kind"]
    if kind == "gradient":
        import math
        colours = [HexColor(stop["colour"]) for stop in background["stops"]]
        positions = [stop["at"] / 100 for stop in background["stops"]]
        if background["type"] == "radial":
            canvas.radialGradient(width / 2, height / 2, math.hypot(width, height) / 2, colours, positions,
                                  extend=True)
        else:
            angle = math.radians(background["angle_deg"])
            dx, dy = math.sin(angle), math.cos(angle)
            half = (abs(width * dx) + abs(height * dy)) / 2
            cx, cy = width / 2, height / 2
            canvas.linearGradient(cx - dx * half, cy - dy * half, cx + dx * half, cy + dy * half, colours,
                                  positions, extend=True)
        return
    fill = background.get("colour") if kind == "colour" else background.get("fallback", "#FFFFFF")
    canvas.setFillColor(HexColor(fill))
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    if kind == "image":
        draw_image(canvas, context.assets.get(background["asset_id"]), 0, 0, width, height, fit=background["fit"])
        if background.get("dim_pct"):
            canvas.saveState()
            canvas.setFillColor(HexColor("#000000"))
            canvas.setFillAlpha(background["dim_pct"] / 100)
            canvas.rect(0, 0, width, height, fill=1, stroke=0)
            canvas.restoreState()


def draw_watermark(canvas, document, side, context):
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    mark = document.get("watermark") or {}
    if mark.get("kind", "none") == "none":
        return
    width, height = side["page_width_mm"] * mm, side["page_height_mm"] * mm
    alpha = mark["opacity_pct"] / 100
    if mark["kind"] == "image":
        draw_image(canvas, context.assets.get(mark["asset_id"]), width * 0.15, height * 0.15, width * 0.7,
                   height * 0.7, alpha=alpha, grey=document.get("mono", False))
        return
    from .rendering_text import nearest_face
    found = nearest_face("Gilroy", 700)
    canvas.saveState()
    canvas.translate(width / 2, height / 2)
    canvas.rotate(-mark["angle_deg"])
    canvas.setFillColor(HexColor(colour_for(document, mark["colour"])))
    canvas.setFillAlpha(alpha)
    size = min(width / max(4, len(mark["text"])) * 1.6, height * 0.4)
    canvas.setFont(found[0] if found else "Helvetica-Bold", size)
    canvas.drawCentredString(0, -size / 3, mark["text"])
    canvas.restoreState()


def draw_preview_mark(canvas, side, label):
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    width, height = side["page_width_mm"] * mm, side["page_height_mm"] * mm
    canvas.saveState()
    canvas.translate(width / 2, height / 2)
    canvas.rotate(20)
    canvas.setFillColor(HexColor("#B91C1C"))
    canvas.setFillAlpha(0.35)
    canvas.setFont("Helvetica-Bold", min(width / 8, 28))
    canvas.drawCentredString(0, 0, label)
    canvas.restoreState()
