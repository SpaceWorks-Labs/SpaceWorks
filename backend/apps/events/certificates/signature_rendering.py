"""Signature layers: the signatory's image above a rule, then their name and title (C4)."""
from io import BytesIO

from rest_framework.exceptions import ValidationError

from .layout import COLOURS
from .text_rendering import draw_text

IMAGE, RULE, NAME = 0.56, 0.6, 0.8  # Fractions of the layer height.


def draw_signature(canvas, layer, resource, area_height_mm):
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from .layer_rendering import ImageResource, SignatureResource
    if not isinstance(resource, SignatureResource):
        raise ValidationError({"layout": "Add the signatory for this signature layer."})
    x, top, width, height = layer["x_mm"], layer["y_mm"], layer["width_mm"], layer["height_mm"]
    colour = HexColor(layer.get("colour") or COLOURS[layer.get("colour_token", "ink")])
    if isinstance(resource.image, ImageResource):
        canvas.drawImage(ImageReader(BytesIO(resource.image.content)), x * mm,
                         (area_height_mm - top - height * IMAGE) * mm, width=width * mm,
                         height=height * IMAGE * mm, preserveAspectRatio=True, anchor="s", mask="auto")
    canvas.setStrokeColor(colour)
    canvas.setLineWidth(0.6)
    rule = (area_height_mm - top - height * RULE) * mm
    inset = width * 0.08
    canvas.line((x + inset) * mm, rule, (x + width - inset) * mm, rule)
    size = layer.get("font_size_pt", 12)
    base = {**layer, "type": "text", "shrink_to_fit": True, "x_mm": x, "width_mm": width}
    draw_text(canvas, resource.name, {**base, "y_mm": top + height * (RULE + 0.02),
                                      "height_mm": height * (NAME - RULE - 0.02), "line_height": 1.1}, area_height_mm)
    if resource.title:
        draw_text(canvas, resource.title, {**base, "y_mm": top + height * NAME, "height_mm": height * (1 - NAME),
                                           "font_weight": 400, "font_size_pt": max(6, size * 0.8),
                                           "line_height": 1.1}, area_height_mm)
