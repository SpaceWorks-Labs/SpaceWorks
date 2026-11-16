"""Print-ready card output (decision 344(b)): bleed, crop marks and PDF page boxes around ONE card, plus the PNG.

The trim area is drawn by the ordinary `draw_side`, so it is the exact card every other output prints (parity holds by
construction). The bleed is a MIRROR of the card's outer `bleed_mm`: each edge strip and corner draws the side again,
reflected about the trim line and clipped to the strip. That is the standard "mirror edge" bleed: backgrounds, bands
and anything else that touches the trim run on past it, and nothing is re-laid-out. Content that sits inside the safe
zone (default 3 mm, never smaller than a 3 mm bleed by the designer's checks) is never mirrored into the bleed.

Crop marks (0.25 pt, registration black) start 1 mm outside the bleed and run 5 mm, in a 7 mm slug. The page carries
TrimBox, BleedBox and CropBox so a print shop's RIP finds the trim without guessing.
"""
from io import BytesIO

from .layout import sides as document_sides
from .rendering import draw_side, page_size

MAX_BLEED_MM = 5.0
SLUG_MM = 7.0
MARK_GAP_MM = 1.0
MARK_LENGTH_MM = 5.0


def options_from_query(params):
    """`bleed_mm` (0-5) and `crop_marks` (true/false) from a download URL; typed 400 on anything else."""
    from django.utils.translation import gettext
    from rest_framework.exceptions import ValidationError
    try:
        bleed = float(params.get("bleed_mm", 0) or 0)
    except (TypeError, ValueError):
        bleed = -1.0
    marks = str(params.get("crop_marks", "false")).lower()
    if not 0 <= bleed <= MAX_BLEED_MM or marks not in ("true", "false", "1", "0"):
        raise ValidationError({"bleed_mm": gettext("Use a bleed from 0 to 5 mm and crop marks true or false.")})
    return {"bleed_mm": bleed, "crop_marks": marks in ("true", "1")}


def geometry(document, bleed_mm, crop_marks):
    """(page_w, page_h, margin, bleed) in points: margin is the distance from the page edge to the trim."""
    from reportlab.lib.units import mm
    width, height = page_size(document)
    bleed = max(0.0, min(MAX_BLEED_MM, float(bleed_mm))) * mm
    margin = bleed + (SLUG_MM * mm if crop_marks else 0.0)
    return width + 2 * margin, height + 2 * margin, margin, bleed


def _mirrored(canvas, document, side, context, margin, bleed, width, height):
    """Draw the side's reflections into the 4 edge strips and 4 corners of the bleed."""
    left, right, bottom, top = margin, margin + width, margin, margin + height
    for sx, sy in ((-1, 1), (1, 1), (1, -1), (-1, -1), (-1, 0), (1, 0), (0, -1), (0, 1)):
        # (sx, sy): -1 = the left/bottom bleed, 1 = the right/top bleed, 0 = across the full trim on that axis.
        clip_x = (left - bleed, bleed) if sx == -1 else (right, bleed) if sx == 1 else (left, width)
        clip_y = (bottom - bleed, bleed) if sy == -1 else (top, bleed) if sy == 1 else (bottom, height)
        canvas.saveState()
        path = canvas.beginPath()
        path.rect(clip_x[0], clip_y[0], clip_x[1], clip_y[1])
        canvas.clipPath(path, stroke=0, fill=0)
        if sx:
            axis = left if sx == -1 else right
            canvas.translate(2 * axis, 0)
            canvas.scale(-1, 1)
        if sy:
            axis = bottom if sy == -1 else top
            canvas.translate(0, 2 * axis)
            canvas.scale(1, -1)
        draw_side(canvas, document, side, context, origin=(margin, margin))
        canvas.restoreState()


def _crop_marks(canvas, margin, bleed, width, height):
    from reportlab.lib.units import mm
    gap, length = bleed + MARK_GAP_MM * mm, MARK_LENGTH_MM * mm
    xs, ys = (margin, margin + width), (margin, margin + height)
    canvas.saveState()
    canvas.setLineWidth(0.25)
    canvas.setStrokeColorRGB(0, 0, 0)
    for x in xs:
        canvas.line(x, ys[0] - gap, x, ys[0] - gap - length)
        canvas.line(x, ys[1] + gap, x, ys[1] + gap + length)
    for y in ys:
        canvas.line(xs[0] - gap, y, xs[0] - gap - length, y)
        canvas.line(xs[1] + gap, y, xs[1] + gap + length, y)
    canvas.restoreState()


def _boxes(canvas, page_w, page_h, margin, bleed, width, height):
    trim = (margin, margin, margin + width, margin + height)
    bleed_box = (margin - bleed, margin - bleed, margin + width + bleed, margin + height + bleed)
    for name, box in (("setTrimBox", trim), ("setBleedBox", bleed_box), ("setCropBox", (0, 0, page_w, page_h))):
        setter = getattr(canvas, name, None)
        if setter:
            setter(box)


def render_print_pdf(document, context, *, sides=None, bleed_mm=3.0, crop_marks=True, title="Card"):
    """One page per side: the card at its trim, `bleed_mm` of mirror bleed, optional crop marks in a slug."""
    from reportlab.pdfgen.canvas import Canvas
    width, height = page_size(document)
    page_w, page_h, margin, bleed = geometry(document, bleed_mm, crop_marks)
    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=(page_w, page_h), pageCompression=1, invariant=1)
    canvas.setTitle(title)
    canvas.setCreator("Space Works")
    for side_name in sides or document_sides(document):
        _boxes(canvas, page_w, page_h, margin, bleed, width, height)
        if bleed:
            _mirrored(canvas, document, side_name, context, margin, bleed, width, height)
        draw_side(canvas, document, side_name, context, origin=(margin, margin))
        if crop_marks:
            _crop_marks(canvas, margin, bleed, width, height)
        canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def render_print_png(document, context, *, side="front", bleed_mm=3.0, dpi=300):
    """The trim plus bleed (no marks) as a PNG at `dpi`: what an online print service asks for."""
    from .raster import pdf_page_to_png
    if side not in document_sides(document):
        side = "front"
    return pdf_page_to_png(render_print_pdf(document, context, sides=(side,), bleed_mm=bleed_mm, crop_marks=False), 0,
                           dpi=dpi)
