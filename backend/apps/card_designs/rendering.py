"""Render a CardDesignDocument v2 to PDF (one page per side) with reportlab.

The PDF is the single source of truth: the PNG is the same page rasterised by
pdfium (`raster.py`), and sheets draw the same sides into imposed cells (`sheets.py`).
Inputs are already authorised and frozen: a `RenderContext` holds the merged values,
the QR payloads and the image bytes. Nothing here queries the database.
"""
from dataclasses import dataclass, field
from io import BytesIO

from .layout import sides as document_sides


@dataclass
class RenderContext:
    values: dict = field(default_factory=dict)
    allow_sensitive: bool = False
    desk_qr: str | None = None
    verify_qr: str | None = None
    checkin_qr: str | None = None  # E-B1: an event registration's live check-in code; never rotated by a print
    photo: bytes | None = field(default=None, repr=False)
    logos: dict = field(default_factory=dict, repr=False)
    assets: dict = field(default_factory=dict, repr=False)
    asset_colours: dict = field(default_factory=dict)
    preview: bool = False
    preview_label: str = ""


def page_size(document):
    from reportlab.lib.units import mm
    front = document["front"]
    return front["page_width_mm"] * mm, front["page_height_mm"] * mm


def draw_side(canvas, document, side_name, context, *, origin=(0.0, 0.0), mirror=False):
    """Draw one side with its bottom-left corner at `origin` (points)."""
    from .rendering_background import draw_background, draw_preview_mark, draw_watermark
    from .rendering_layers import draw_layer
    side = document[side_name]
    canvas.saveState()
    try:
        canvas.translate(*origin)
        path = canvas.beginPath()
        width, height = page_size(document)
        path.rect(0, 0, width, height)
        canvas.clipPath(path, stroke=0, fill=0)
        draw_background(canvas, document, side, context)
        draw_watermark(canvas, document, side, context)
        for index, layer in enumerate(side["layers"]):
            if not layer.get("hidden"):
                draw_layer(canvas, document, side, index, layer, context)
        if context.preview and context.preview_label:
            draw_preview_mark(canvas, side, context.preview_label)
    finally:
        canvas.restoreState()


def render_pdf(document, context, *, sides=None, title="Card"):
    from reportlab.pdfgen.canvas import Canvas
    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=page_size(document), pageCompression=1)
    canvas.setTitle(title)
    canvas.setCreator("Space Works")
    for side_name in sides or document_sides(document):
        draw_side(canvas, document, side_name, context)
        canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def render_png(document, context, *, side="front", dpi=300):
    from .raster import pdf_page_to_png
    sides = document_sides(document)
    if side not in sides:
        side = "front"
    return pdf_page_to_png(render_pdf(document, context, sides=(side,)), 0, dpi=dpi)
