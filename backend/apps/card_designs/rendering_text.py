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

    from .fonts import is_outline
    if is_outline(family, weight):
        from .rendering_outline import codes, pseudo_name
        return pseudo_name(family, weight), codes(family, weight)
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
    from .fonts import canonical, family_weights
    family = canonical(family)
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


def string_width(part, font, size):
    from .rendering_outline import is_outline_name
    if is_outline_name(font):
        from .rendering_outline import string_width as outline_width
        return outline_width(part, font, size)
    from reportlab.pdfbase.pdfmetrics import stringWidth
    return stringWidth(part, font, size)


def width(value, layer, size):
    items = runs(value, layer["font_family"], layer["font_weight"])
    return sum(string_width(part, font, size) for font, part in items) + max(0, len(value) - 1) * layer.get("tracking_pt", 0)


def draw_runs(canvas, items, x, y, size, tracking=0.0, *, stroke=False):
    """Draw (font, text) runs left to right from baseline (x, y); returns the x after the last run.

    `stroke=True` strokes the glyph outlines instead of filling them (the caller sets colour and line width)."""
    from .rendering_outline import draw_string, is_outline_name
    for font, value in items:
        if is_outline_name(font):
            x = draw_string(canvas, value, font, size, x, y, tracking, fill=0 if stroke else 1, stroke=1 if stroke else 0)
            continue
        output = canvas.beginText(x, y)
        if stroke:
            output.setTextRenderMode(1)
        output.setCharSpace(tracking)
        output.setFont(font, size)
        output.textOut(value)
        canvas.drawText(output)
        x += string_width(value, font, size) + len(value) * tracking
    return x


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


ONE_LINE_FLOOR = 0.6


def one_line_size(text, layer, box_width, box_height):
    """The largest size, down to 60 % of the design size, that keeps `text` on one line; None if none does."""
    size = layer["font_size_pt"]
    floor = max(MIN_PT, size * ONE_LINE_FLOOR)
    line = visual(text)
    while size >= floor - 0.001:
        if size * layer["line_height"] <= box_height + 0.01 and width(line, layer, size) <= box_width:
            return size
        size -= 0.25
    return None


def fit(text, layer, box_width, box_height):
    """Shrink-to-fit that keeps a short value such as a name on one line, down to 60 % of the
    design size, before wrapping it. A box tall enough to wrap at a larger size still wraps."""
    size = layer["font_size_pt"]
    while True:
        lines = wrap(text, layer, size, box_width)
        if len(lines) * size * layer["line_height"] <= box_height or not layer.get("shrink_to_fit", True) or size <= MIN_PT:
            break
        size = max(MIN_PT, size - 0.5)
    if len(lines) > 1 and "\n" not in text and layer.get("shrink_to_fit", True):
        single = one_line_size(text, layer, box_width, box_height)
        if single is not None and single >= size:
            return single, [text]
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
    canvas.setFillColor(HexColor(colour), alpha=layer.get("opacity", 100) / 100)
    y = top - max(0, offset) - size * 0.9
    for line in lines:
        line = visual(line)
        used = width(line, layer, size)
        shift = {"left": 0, "center": (box_width - used) / 2, "right": box_width - used}[layer["align"]]
        draw_runs(canvas, runs(line, layer["font_family"], layer["font_weight"]), x + shift, y, size,
                  layer.get("tracking_pt", 0))
        y -= leading


# --- Certificate v2 compat metrics (decision 315): old certificates print byte-for-byte the same layout. ---
COMPAT = "certificate_v2"


def is_compat(document):
    """True for a document compiled from a stored v2 certificate (`certificate_compile.compile_v2`)."""
    return (document.get("source") or {}).get("kind") == COMPAT


def wrap_compat(text, layer, size, box_width):
    """The v2 certificate wrapper: None when one character cluster is wider than the box (the caller shrinks)."""
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
                if width(visual(line + cluster), layer, size) > box_width:
                    if not line:
                        return None
                    lines.append(line)
                    line = ""
                line += cluster
        lines.append(line)
    return lines


def fit_compat(text, layer, box_width, box_height):
    """(size, lines) under the v2 metrics: shrink in 0.5 pt steps to 6 pt; overflow raises (never clips). Pure: no canvas."""
    from django.utils.translation import gettext
    from rest_framework.exceptions import ValidationError
    if len(text) > 1000:
        raise ValidationError({"layout": gettext("Merged text exceeds 1000 characters.")})
    text = text.upper() if layer.get("uppercase") else text
    size = layer["font_size_pt"]
    while True:
        lines = wrap_compat(text, layer, size, box_width)
        if lines is not None and len(lines) * size * layer["line_height"] <= box_height:
            return size, lines
        if size <= MIN_PT or not layer.get("shrink_to_fit", True):
            raise ValidationError({"layout": gettext("Text does not fit at a legible size. Enlarge its box.")})
        size = max(MIN_PT, size - 0.5)


def draw_compat(canvas, text, layer, *, colour, x, top, box_width, box_height):
    """v2 metrics: first baseline = top - size, leading = size x line_height, no one-line preference, overflow raises."""
    from reportlab.lib.colors import HexColor
    size, lines = fit_compat(text, layer, box_width, box_height)
    canvas.setFillColor(HexColor(colour))
    y = top - size
    for line in lines:
        line = visual(line)
        used = width(line, layer, size)
        shift = {"left": 0, "center": (box_width - used) / 2, "right": box_width - used}[layer.get("align", "left")]
        draw_runs(canvas, runs(line, layer["font_family"], layer["font_weight"]), x + shift, y, size,
                  layer.get("tracking_pt", 0))
        y -= size * layer["line_height"]
