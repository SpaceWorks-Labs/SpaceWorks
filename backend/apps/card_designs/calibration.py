"""The print calibration sheet: check a printer's scale, alignment and colour before a run.

`paper="a4"|"letter"` draws, at 100 %: a 100 mm ruler on both axes, the design's stock
outline imposed exactly where card 1 of a sheet job lands (with the 3 mm safe area and
crop marks), a 10 mm square, the brand colour patches with their hex values, a grey
ramp, text at 6-12 pt and a QR and Code128 at their minimum sizes. `paper="card"` draws
one card-sized page for PVC printers: the trim frame, the safe area and a centre cross.
No person's data is ever on it; the codes carry a fixed test string.
"""
from io import BytesIO

from rest_framework.exceptions import ValidationError

from . import stocks
from .sheets import grid

PAPERS = ("a4", "letter", "card")
BRAND = (("Ink", "#142C2A"), ("Teal", "#006E63"), ("Cream", "#FFF4E8"), ("Citron", "#DFFF8F"),
         ("Sky", "#B5CDFF"), ("Orange", "#FF7447"))
TEST_CODE = "SPACEWORKS-CALIBRATION"


def _text(canvas, x, y, value, size=7, bold=False):
    from .rendering_text import draw
    style = {"font_family": "Gilroy", "font_weight": 700 if bold else 400, "font_size_pt": size, "align": "left",
             "valign": "top", "line_height": 1.2, "tracking_pt": 0, "shrink_to_fit": False}
    draw(canvas, value, style, colour="#000000", x=x, top=y, box_width=400, box_height=size * 1.4)


def _ruler(canvas, x, y, *, vertical=False):
    from reportlab.lib.units import mm
    canvas.setLineWidth(0.4)
    end = (x, y - 100 * mm) if vertical else (x + 100 * mm, y)
    canvas.line(x, y, *end)
    for step in range(0, 101):
        length = (3 if step % 10 == 0 else 2 if step % 5 == 0 else 1) * mm
        if vertical:
            canvas.line(x, y - step * mm, x + length, y - step * mm)
        else:
            canvas.line(x + step * mm, y, x + step * mm, y + length)


def _codes(canvas, x, y, stock):
    from reportlab.lib.units import mm
    from .rendering import RenderContext
    from .rendering_extras import draw_barcode
    from .rendering_layers import _qr
    size = stocks.qr_minimum_mm(stock) * mm
    layer = {"kind": "desk_qr"}
    _qr(canvas, {}, {}, 0, layer, RenderContext(desk_qr=TEST_CODE), (x, y - size, size, size))
    draw_barcode(canvas, {"source": "desk", "show_text": True}, RenderContext(desk_qr=TEST_CODE),
                 (x + size + 6 * mm, y - 12 * mm, 75 * mm, 12 * mm))


def _sheet_page(canvas, paper, stock, card_w, card_h):
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import mm
    from .sheets import _crop_marks
    paper_w, paper_h = stocks.PAPERS[paper]
    columns, rows, left, top = grid(paper, card_w, card_h)
    x0, y0 = left * mm, (paper_h - top - card_h) * mm
    canvas.setStrokeColor(HexColor("#000000"))
    canvas.setLineWidth(0.3)
    canvas.rect(x0, y0, card_w * mm, card_h * mm, stroke=1, fill=0)
    canvas.setDash(1.5, 1.5)
    safe = stocks.SAFE_AREA_MM * mm
    canvas.rect(x0 + safe, y0 + safe, card_w * mm - 2 * safe, card_h * mm - 2 * safe, stroke=1, fill=0)
    canvas.setDash()
    _crop_marks(canvas, 1, 1, left, top, card_w, card_h, paper_h)
    _text(canvas, x0 + 2 * mm, y0 + card_h * mm / 2 + 4 * mm, "Card 1 lands here", 8, True)
    _text(canvas, x0 + 2 * mm, y0 + card_h * mm / 2, f"{card_w:g} x {card_h:g} mm; dashed = 3 mm safe area", 6)
    base = y0 - 14 * mm
    if base - 145 * mm < 8 * mm:  # A large stock fills the first page; the checks go on the next one.
        canvas.showPage()
        base = (paper_h - 15) * mm
    _text(canvas, 15 * mm, base, "Print calibration sheet", 12, True)
    _text(canvas, 15 * mm, base - 6 * mm, "Print at 100 % (actual size), no scaling or fit-to-page. "
                                          "Each ruler must measure exactly 100 mm and the square 10 mm.", 7)
    _ruler(canvas, 15 * mm, base - 14 * mm)
    _ruler(canvas, paper_w * mm - 15 * mm, base - 14 * mm, vertical=True)
    canvas.rect(120 * mm, base - 30 * mm, 10 * mm, 10 * mm, stroke=1, fill=0)
    _text(canvas, 120 * mm, base - 31 * mm, "10 mm", 6)
    for index, (name, colour) in enumerate(BRAND):
        x = 15 * mm + index * 28 * mm
        canvas.setFillColor(HexColor(colour))
        canvas.rect(x, base - 52 * mm, 24 * mm, 12 * mm, stroke=1, fill=1)
        _text(canvas, x, base - 53 * mm, f"{name} {colour}", 6)
    for step in range(11):
        canvas.setFillColor(HexColor("#{0:02X}{0:02X}{0:02X}".format(round(255 * step / 10))))
        canvas.rect(15 * mm + step * 9 * mm, base - 72 * mm, 9 * mm, 8 * mm, stroke=0, fill=1)
    _text(canvas, 15 * mm, base - 73 * mm, "Grey ramp 0-100 %: every step should be distinct.", 6)
    for index, size in enumerate((6, 7, 8, 10, 12)):
        _text(canvas, 15 * mm, base - (82 + index * 6) * mm, f"{size} pt  The quick brown fox · അക്ഷരം · अक्षर · ₹ 1,250", size)
    _codes(canvas, 15 * mm, base - 120 * mm, stock)
    _text(canvas, 15 * mm, base - 142 * mm, "Scan both codes with a phone and the desk scanner: they read "
                                            f"“{TEST_CODE}”.", 6)


def _card_page(canvas, card_w, card_h):
    from reportlab.lib.units import mm
    w, h, safe = card_w * mm, card_h * mm, stocks.SAFE_AREA_MM * mm
    canvas.setLineWidth(0.3)
    canvas.rect(0.3, 0.3, w - 0.6, h - 0.6, stroke=1, fill=0)
    canvas.setDash(1.5, 1.5)
    canvas.rect(safe, safe, w - 2 * safe, h - 2 * safe, stroke=1, fill=0)
    canvas.setDash()
    canvas.line(w / 2 - 4 * mm, h / 2, w / 2 + 4 * mm, h / 2)
    canvas.line(w / 2, h / 2 - 4 * mm, w / 2, h / 2 + 4 * mm)
    _text(canvas, safe + 1 * mm, h - safe - 1 * mm, f"Card {card_w:g} x {card_h:g} mm", 6, True)
    _text(canvas, safe + 1 * mm, safe + 4 * mm, "The solid frame is the trim edge; keep text inside the dashes.", 5.5)


def render(document, paper):
    from reportlab.lib.units import mm
    from reportlab.pdfgen.canvas import Canvas
    if paper not in PAPERS:
        raise ValidationError({"paper": "Choose A4, Letter or a single card."})
    card_w, card_h = document["front"]["page_width_mm"], document["front"]["page_height_mm"]
    buffer = BytesIO()
    size = (card_w * mm, card_h * mm) if paper == "card" else tuple(v * mm for v in stocks.PAPERS[paper])
    canvas = Canvas(buffer, pagesize=size, pageCompression=1)
    canvas.setTitle("Print calibration sheet")
    canvas.setCreator("Space Works")
    if paper == "card":
        _card_page(canvas, card_w, card_h)
    else:
        _sheet_page(canvas, paper, document["stock"], card_w, card_h)
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()
