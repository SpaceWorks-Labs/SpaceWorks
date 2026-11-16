"""Shape and band layers: rect, rounded, circle, ellipse, arch, line, triangle, diamond, hexagon, star; gradient fill;
stroke; drop shadow."""
from reportlab.lib.colors import HexColor

from .rendering_background import colour_for
from .studio_geometry import POLYGON_SHAPES, arch_radius, polygon_points

INK = "#142C2A"
DEFAULT_ROUNDED_MM = 3.0


def outline_path(canvas, shape, x, y, w, h, radius):
    """A reportlab path for the shape inside box (x, y, w, h), y up; None for a line. `radius` is in points."""
    path = canvas.beginPath()
    if shape == "circle":
        side = min(w, h)
        path.ellipse(x + (w - side) / 2, y + (h - side) / 2, side, side)
    elif shape == "ellipse":
        path.ellipse(x, y, w, h)
    elif shape == "arch":
        top = arch_radius(w, h)
        if top is None:
            path.roundRect(x, y, w, h, min(radius, w / 2, h / 2))
        else:
            path.moveTo(x, y)
            path.lineTo(x + w, y)
            path.lineTo(x + w, y + h - top)
            path.arcTo(x, y + h - 2 * top, x + w, y + h, startAng=0, extent=180)
            path.close()
    elif shape in POLYGON_SHAPES:
        # polygon_points is top-left origin in the box's own unit; reportlab's y runs up from the box bottom.
        points = polygon_points(shape, w, h)
        path.moveTo(x + points[0][0], y + h - points[0][1])
        for px, py in points[1:]:
            path.lineTo(x + px, y + h - py)
        path.close()
    elif shape in ("rounded", "rect") and radius > 0:
        path.roundRect(x, y, w, h, min(radius, w / 2, h / 2))
    elif shape in ("rounded", "rect"):
        path.rect(x, y, w, h)
    else:
        return None
    return path


def _radius(layer):
    from reportlab.lib.units import mm
    radius = layer.get("radius_mm", 0)
    if layer.get("shape") == "rounded" and not radius:
        radius = DEFAULT_ROUNDED_MM
    return radius * mm


def _mirrored(spec, layer):
    """flip_x / flip_y mirror a gradient's direction."""
    angle = spec.get("angle_deg", 0)
    if layer.get("flip_x"):
        angle = (360 - angle) % 360
    if layer.get("flip_y"):
        angle = (180 - angle) % 360
    return {**spec, "angle_deg": angle}


def _gradient(canvas, document, layer, path, x, y, w, h):
    from reportlab.lib.units import mm
    spec = _mirrored(layer["fill_gradient"], layer)
    canvas.saveState()
    canvas.clipPath(path, stroke=0, fill=0)
    if all(stop.get("alpha_pct", 100) >= 100 for stop in spec["stops"]):
        from .rendering_background import paint_gradient
        canvas.translate(x, y)
        paint_gradient(canvas, spec, w, h)
    else:
        from reportlab.lib.utils import ImageReader
        from .rendering_media import overlay_image
        canvas.drawImage(ImageReader(overlay_image(spec, w / mm, h / mm)), x, y, width=w, height=h, mask="auto")
    canvas.restoreState()


def draw_shape(canvas, document, side, index, layer, context, box):
    from reportlab.lib.units import mm
    x, y, w, h = box
    fill, stroke = layer.get("fill"), layer.get("stroke")
    shape = layer.get("shape", "rect")
    if shape == "line":
        canvas.setStrokeColor(HexColor(colour_for(document, stroke or fill or INK)), alpha=layer.get("opacity", 100) / 100)
        canvas.setLineWidth(max(0.1, layer.get("stroke_mm", 0.3)) * mm)
        canvas.line(x, y + h / 2, x + w, y + h / 2)
        return
    path = outline_path(canvas, shape, x, y, w, h, _radius(layer))
    if layer.get("shadow") and not document.get("mono"):
        from .rendering_media import draw_shape_shadow
        draw_shape_shadow(canvas, layer, (x, y, w, h))
    gradient = layer.get("fill_gradient") and not document.get("mono")
    if gradient:
        _gradient(canvas, document, layer, path, x, y, w, h)
    alpha = layer.get("opacity", 100) / 100  # setFillColor(HexColor) resets the alpha, so state it again
    if fill and not gradient:
        canvas.setFillColor(HexColor(colour_for(document, fill)), alpha=alpha)
    if stroke:
        canvas.setStrokeColor(HexColor(colour_for(document, stroke)), alpha=alpha)
        canvas.setLineWidth(max(0.1, layer.get("stroke_mm", 0.3)) * mm)
    do_fill, do_stroke = int(bool(fill) and not gradient), int(bool(stroke))
    if do_fill or do_stroke:
        canvas.drawPath(path, fill=do_fill, stroke=do_stroke)
