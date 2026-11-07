from django.utils.translation import gettext
import unicodedata

from rest_framework.exceptions import ValidationError
from .fonts import runs
from .layout import COLOURS


def draw_text(canvas, text, layer, area_height_mm):
    """Wrap logical lines, bidi each final line, shrink to ≥6 pt, refuse overflow."""
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    if len(text) > 1000:
        raise ValidationError({"layout": gettext("Merged text exceeds 1000 characters.")})
    text = text.upper() if layer.get("uppercase") else text
    width, height = layer["width_mm"] * mm, layer["height_mm"] * mm
    size = layer["font_size_pt"]
    while True:
        lines = wrap_lines(text, layer, size, width)
        leading = size * layer.get("line_height", 1.3)
        if lines is not None and len(lines) * leading <= height:
            break
        if size <= 6 or not layer.get("shrink_to_fit", True):
            raise ValidationError({"layout": gettext("Text does not fit at a legible size. Enlarge its box.")})
        size = max(6, size - 0.5)
    canvas.setFillColor(HexColor(layer.get("colour") or COLOURS[layer.get("colour_token", "ink")]))
    y = (area_height_mm - layer["y_mm"]) * mm - size
    for line in lines:
        line = visual(line)
        used = text_width(line, layer, size)
        offset = {"left": 0, "center": (width-used)/2, "right": width-used}[layer.get("align", "left")]
        output = canvas.beginText(layer["x_mm"] * mm + offset, y)
        output.setCharSpace(layer.get("tracking_pt", 0))
        for font, value in runs(line, layer.get("font_family", "Gilroy"), layer.get("font_weight", 400)):
            output.setFont(font, size)
            output.textOut(value)
        canvas.drawText(output)
        y -= leading


def visual(value):
    if any(unicodedata.bidirectional(char) in ("R", "AL") for char in value):
        from arabic_reshaper import reshape
        from bidi.algorithm import get_display
        return get_display(reshape(value))
    return value


def text_width(value, layer, size):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    return sum(stringWidth(text, font, size) for font, text in runs(
        value, layer.get("font_family", "Gilroy"), layer.get("font_weight", 400),
    )) + max(0, len(value)-1) * layer.get("tracking_pt", 0)


def wrap_lines(text, layer, size, width):
    from apps.operations.printable_fonts import clusters
    result = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            candidate = f"{line} {word}" if line else word
            if text_width(visual(candidate), layer, size) <= width:
                line = candidate
                continue
            if line:
                result.append(line)
            line = ""
            for cluster in clusters(word):
                if text_width(visual(line + cluster), layer, size) > width:
                    if not line:
                        return None
                    result.append(line)
                    line = ""
                line += cluster
        result.append(line)
    return result
