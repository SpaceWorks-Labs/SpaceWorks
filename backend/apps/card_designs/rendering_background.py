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


def paint_gradient(canvas, spec, width, height):
    """A linear or radial gradient across the box (0, 0, width, height) in points; CSS angle convention."""
    from reportlab.lib.colors import HexColor
    from .studio_geometry import gradient_line, radial_circle
    colours = [HexColor(stop["colour"]) for stop in spec["stops"]]
    positions = [stop["at"] / 100 for stop in spec["stops"]]
    if spec["type"] == "radial":
        cx, cy, radius = radial_circle(spec, width, height)
        canvas.radialGradient(cx, height - cy, radius, colours, positions, extend=True)
        return
    x0, y0, x1, y1 = gradient_line(spec, width, height)
    canvas.linearGradient(x0, height - y0, x1, height - y1, colours, positions, extend=True)


def draw_background_image(canvas, background, data, width, height):
    """Uploaded background: fit, zoom, focal point and blur (blur_mm) through the effects raster when asked for."""
    if not data:
        return
    plain = (background.get("fit", "cover") in ("cover", "contain") and not background.get("zoom")
             and "focal_x_pct" not in background and "focal_y_pct" not in background and not background.get("blur_mm"))
    if plain:
        draw_image(canvas, data, 0, 0, width, height, fit=background.get("fit", "cover"))
        return
    from reportlab.lib.units import mm
    from .rendering_media import blurred_background
    composed = blurred_background(data, background, width / mm, height / mm)
    if composed is not None:
        from reportlab.lib.utils import ImageReader
        canvas.drawImage(ImageReader(composed), 0, 0, width=width, height=height, mask="auto")


def draw_overlay(canvas, document, side):
    """The side's gradient overlay (stops carry alpha), laid over the background and under the layers."""
    overlay = side.get("overlay")
    if not overlay or document.get("mono"):
        return
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from .rendering_media import overlay_image
    width, height = side["page_width_mm"], side["page_height_mm"]
    canvas.drawImage(ImageReader(overlay_image(overlay, width, height)), 0, 0, width=width * mm, height=height * mm,
                     mask="auto")


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
        paint_gradient(canvas, background, width, height)
        return
    fill = background.get("colour") if kind == "colour" else background.get("fallback", "#FFFFFF")
    canvas.setFillColor(HexColor(fill))
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    if kind == "image":
        draw_background_image(canvas, background, context.assets.get(background["asset_id"]), width, height)
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
    found = nearest_face("Outfit", 700)
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
