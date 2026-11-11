"""Print-sheet imposition (SPEC §3.1): cards centred in a gutterless grid on A4/Letter.

CR80 landscape on A4 portrait is 2 x 5. Crop marks are 0.25 pt, starting 2 mm outside
the grid and 5 mm long. Backs are mirrored per row, so a long-edge duplex print (or
re-feeding the fronts for a single-sided printer) puts each back behind its front.
"""
from django.utils.translation import gettext
from io import BytesIO
from math import floor

from rest_framework.exceptions import ValidationError

from . import stocks
from .layout import sides as document_sides
from .rendering import draw_side

MAX_CARDS_PER_PDF = 1000
ORDERS = ("duplex", "fronts_then_backs")
# E-B2: one card per page, the page being the card itself (card and label printers, badge desks).
PER_CARD = "per_card"


def grid(paper, card_w_mm, card_h_mm):
    if paper == PER_CARD:
        return 1, 1, 0.0, 0.0
    paper_w, paper_h = stocks.PAPERS[paper]
    columns, rows = floor(paper_w / card_w_mm), floor(paper_h / card_h_mm)
    if columns < 1 or rows < 1:
        raise ValidationError({"paper": gettext("This card stock is larger than the paper.")})
    left = (paper_w - columns * card_w_mm) / 2
    top = (paper_h - rows * card_h_mm) / 2
    return columns, rows, left, top


def _crop_marks(canvas, columns, rows, left, top, card_w, card_h, paper_h):
    from reportlab.lib.units import mm
    canvas.saveState()
    canvas.setLineWidth(0.25)
    canvas.setStrokeColorRGB(0, 0, 0)
    xs = [left + c * card_w for c in range(columns + 1)]
    ys = [top + r * card_h for r in range(rows + 1)]
    grid_left, grid_right, grid_top, grid_bottom = xs[0], xs[-1], ys[0], ys[-1]
    for x in xs:
        canvas.line(x * mm, (paper_h - grid_top + 2) * mm, x * mm, (paper_h - grid_top + 7) * mm)
        canvas.line(x * mm, (paper_h - grid_bottom - 2) * mm, x * mm, (paper_h - grid_bottom - 7) * mm)
    for y in ys:
        canvas.line((grid_left - 2) * mm, (paper_h - y) * mm, (grid_left - 7) * mm, (paper_h - y) * mm)
        canvas.line((grid_right + 2) * mm, (paper_h - y) * mm, (grid_right + 7) * mm, (paper_h - y) * mm)
    canvas.restoreState()


def _page(canvas, cards, side, columns, rows, left, top, card_w, card_h, paper_h, *, mirror, crop_marks):
    from reportlab.lib.units import mm
    for position, (document, context) in enumerate(cards):
        row, column = divmod(position, columns)
        if mirror:
            column = columns - 1 - column
        x = left + column * card_w
        y = paper_h - top - (row + 1) * card_h
        if side in document_sides(document):
            draw_side(canvas, document, side, context, origin=(x * mm, y * mm))
    if crop_marks:
        _crop_marks(canvas, columns, rows, left, top, card_w, card_h, paper_h)
    canvas.showPage()


def render_sheets(cards, *, paper="a4", order="duplex", crop_marks=True, title="Cards"):
    """`cards` is a list of (document, RenderContext) that all share one stock."""
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.units import mm
    if (paper not in stocks.PAPERS and paper != PER_CARD) or order not in ORDERS:
        raise ValidationError({"paper": gettext("Choose A4 or Letter, duplex or fronts then backs.")})
    if not 1 <= len(cards) <= MAX_CARDS_PER_PDF:
        raise ValidationError({"cards": gettext('A sheet PDF holds 1-{MAX_CARDS_PER_PDF} cards.').format(MAX_CARDS_PER_PDF=MAX_CARDS_PER_PDF)})
    first = cards[0][0]["front"]
    card_w, card_h = first["page_width_mm"], first["page_height_mm"]
    columns, rows, left, top = grid(paper, card_w, card_h)
    paper_w, paper_h = (card_w, card_h) if paper == PER_CARD else stocks.PAPERS[paper]
    crop_marks = crop_marks and paper != PER_CARD
    per_page = columns * rows
    pages = [cards[i:i + per_page] for i in range(0, len(cards), per_page)]
    any_back = any(document.get("back_enabled") for document, _context in cards)
    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=(paper_w * mm, paper_h * mm), pageCompression=1)
    canvas.setTitle(title)
    canvas.setCreator("Space Works")
    geometry = (columns, rows, left, top, card_w, card_h, paper_h)
    if order == "duplex":
        for page in pages:
            _page(canvas, page, "front", *geometry, mirror=False, crop_marks=crop_marks)
            if any_back:
                _page(canvas, page, "back", *geometry, mirror=True, crop_marks=crop_marks)
    else:
        for page in pages:
            _page(canvas, page, "front", *geometry, mirror=False, crop_marks=crop_marks)
        if any_back:
            for page in pages:
                _page(canvas, page, "back", *geometry, mirror=True, crop_marks=crop_marks)
    canvas.save()
    return buffer.getvalue()
