"""Text on a card: the card font library first, the bundled Noto chain for any glyph
the chosen face lacks (Indic, Arabic, CJK, symbols such as ₹), bidi, shrink-to-fit.

A card never fails to render because of text: below 6 pt the last line is clipped
with an ellipsis, so one long name cannot stop a bulk job.
"""
import unicodedata
from functools import lru_cache

MIN_PT = 6.0


@lru_cache(maxsize=256)
def face(family, weight):
    """(registered reportlab name, covered code points) or None when the face is absent."""
    from fontTools.ttLib import TTFont as Font
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    from .font_store import local_path
    path = local_path(family, weight)
    if path is None:
        return None
    name = f"Card-{family.replace(' ', '')}-{weight}"
    try:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(path), shapable=True))
        with Font(str(path), lazy=True) as font:
            codes = frozenset((font.getBestCmap() or {}).keys())
    except Exception:
        return None
    return name, codes


def nearest_face(family, weight):
    from .fonts import family_weights
    for candidate in sorted(family_weights(family), key=lambda value: abs(value - weight)):
        found = face(family, candidate)
        if found:
            return found
    return None


def runs(text, family, weight):
    from apps.operations.printable_fonts import clusters, font_runs, registered_name
    primary = nearest_face(family, weight)
    result = []
    for cluster in clusters(text):
        if primary and all(ord(char) in primary[1] or unicodedata.category(char) == "Cf" for char in cluster):
            items = [(primary[0], cluster)]
        else:
            items = [(registered_name(filename), value) for filename, value in font_runs(cluster, "sans", weight >= 600)]
        for font, value in items:
            if result and result[-1][0] == font:
                result[-1] = (font, result[-1][1] + value)
            else:
                result.append((font, value))
    return result


def visual(value):
    if any(unicodedata.bidirectional(char) in ("R", "AL") for char in value):
        from arabic_reshaper import reshape
        from bidi.algorithm import get_display
        return get_display(reshape(value))
    return value


def width(value, layer, size):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    return sum(stringWidth(part, font, size) for font, part in runs(value, layer["font_family"], layer["font_weight"])) \
        + max(0, len(value) - 1) * layer.get("tracking_pt", 0)


def wrap(text, layer, size, box_width):
    from apps.operations.printable_fonts import clusters
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            candidate = f"{line} {word}" if line else word
            if width(visual(candidate), layer, size) <= box_width:
                line = candidate
                continue
            if line:
                lines.append(line)
            line = ""
            for cluster in clusters(word):
                if line and width(visual(line + cluster), layer, size) > box_width:
                    lines.append(line)
                    line = ""
                line += cluster
        lines.append(line)
    return lines


def fit(text, layer, box_width, box_height):
    size = layer["font_size_pt"]
    while True:
        lines = wrap(text, layer, size, box_width)
        if len(lines) * size * layer["line_height"] <= box_height or not layer.get("shrink_to_fit", True) or size <= MIN_PT:
            break
        size = max(MIN_PT, size - 0.5)
    capacity = max(1, int(box_height // (size * layer["line_height"])))
    if len(lines) > capacity:
        lines = lines[:capacity]
        last = lines[-1]
        while last and width(visual(last + "…"), layer, size) > box_width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return size, lines


def draw(canvas, text, layer, *, colour, x, top, box_width, box_height):
    """Draw `text` inside a box whose top-left is (x, top) in points."""
    from reportlab.lib.colors import HexColor
    if layer.get("uppercase"):
        text = text.upper()
    text = text[:1000]
    size, lines = fit(text, layer, box_width, box_height)
    leading = size * layer["line_height"]
    block = len(lines) * leading
    offset = {"top": 0, "middle": (box_height - block) / 2, "bottom": box_height - block}[layer.get("valign", "top")]
    canvas.setFillColor(HexColor(colour))
    y = top - max(0, offset) - size * 0.9
    for line in lines:
        line = visual(line)
        used = width(line, layer, size)
        shift = {"left": 0, "center": (box_width - used) / 2, "right": box_width - used}[layer["align"]]
        output = canvas.beginText(x + shift, y)
        output.setCharSpace(layer.get("tracking_pt", 0))
        for font, value in runs(line, layer["font_family"], layer["font_weight"]):
            output.setFont(font, size)
            output.textOut(value)
        canvas.drawText(output)
        y -= leading
