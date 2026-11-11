"""L3 rendering: PDF pages, PNG size and equality with the PDF, sheets, scripts, shapes."""
import io
from uuid import uuid4

import pytest

from apps.card_designs.default_templates import build, default_document
from apps.card_designs.layout import normalize_document
from apps.card_designs.raster import pdf_page_to_png, png_size
from apps.card_designs.rendering import RenderContext, render_pdf, render_png
from apps.card_designs.sheets import grid, render_sheets

VALUES = {"name": "പ്രിയ രാമൻ प्रिया ₹", "number": "TNK-0042", "plan": "Monthly", "valid_until": "31 Dec 2026",
          "space": "Tinkerspace", "member_since": "Mar 2024", "verify_url": "x/verify/c/abc"}


def _pages(pdf):
    from pypdf import PdfReader
    return len(PdfReader(io.BytesIO(pdf)).pages)


def _context(**extra):
    return RenderContext(values=VALUES, desk_qr="0" * 32, verify_qr="https://x/verify/c/" + "a" * 43, **extra)


def test_two_pages_with_a_back_and_one_without():
    with_back = normalize_document(default_document("member_cards"))
    assert _pages(render_pdf(with_back, _context())) == 2
    front_only = normalize_document({**build("minimal", "member_cards"), "back_enabled": False})
    assert _pages(render_pdf(front_only, _context())) == 1


def test_png_is_1011_by_638_at_300_dpi_and_equals_the_pdf_page():
    document = normalize_document(default_document("member_cards"))
    png = render_png(document, _context())
    assert png_size(png) == (1011, 638)
    pdf = render_pdf(document, _context(), sides=("front",))
    assert pdf_page_to_png(pdf, 0) == png


def test_indic_and_rupee_text_and_long_names_render():
    document = normalize_document(default_document("member_cards"))
    long_values = {**VALUES, "name": "Alexandra Montgomery-Fitzgerald " * 4}
    assert render_pdf(document, RenderContext(values=long_values)).startswith(b"%PDF")
    assert render_pdf(document, _context()).startswith(b"%PDF")


def test_rotation_opacity_shapes_gradient_and_hidden_layers():
    layers = [
        {"id": str(uuid4()), "kind": "shape", "name": "e", "shape": "ellipse", "x_mm": 10, "y_mm": 10, "w_mm": 20,
         "h_mm": 10, "fill": "#DFFF8F", "rotation": 30, "opacity": 60},
        {"id": str(uuid4()), "kind": "shape", "name": "l", "shape": "line", "x_mm": 5, "y_mm": 30, "w_mm": 40,
         "h_mm": 1, "stroke": "#142C2A"},
        {"id": str(uuid4()), "kind": "perforation", "name": "p", "x_mm": 50, "y_mm": 0, "w_mm": 2, "h_mm": 53.98},
        {"id": str(uuid4()), "kind": "text", "name": "hidden", "x_mm": 5, "y_mm": 40, "w_mm": 40, "h_mm": 6,
         "text": "Hidden", "colour": "#142C2A", "hidden": True},
        {"id": str(uuid4()), "kind": "logo", "name": "s", "source": "symbol", "x_mm": 60, "y_mm": 5, "w_mm": 10,
         "h_mm": 10},
    ]
    document = normalize_document({"version": 2, "stock": "cr80-landscape", "front": {
        "background": {"kind": "gradient", "type": "radial", "stops": [{"colour": "#FFFFFF", "at": 0},
                                                                    {"colour": "#FFF4E8", "at": 100}]},
        "layers": layers}, "back": {"layers": []}})
    assert render_pdf(document, _context()).startswith(b"%PDF")


def test_no_qr_is_printed_without_a_live_code():
    document = normalize_document(build("student", "id_programme"))
    with_code = render_png(document, _context(), dpi=72)
    without = render_png(document, RenderContext(values=VALUES), dpi=72)
    assert with_code != without


def test_sheet_grid_is_2_by_5_on_a4_and_backs_follow_fronts():
    assert grid("a4", 85.6, 53.98)[:2] == (2, 5)
    assert grid("letter", 85.6, 53.98)[:2] == (2, 5)
    document = normalize_document(default_document("member_cards"))
    cards = [(document, _context()) for _ in range(12)]
    assert _pages(render_sheets(cards, order="duplex")) == 4
    assert _pages(render_sheets(cards, order="fronts_then_backs")) == 4
    single = normalize_document({**build("minimal", "member_cards"), "back_enabled": False})
    assert _pages(render_sheets([(single, _context())] * 3)) == 1


def test_sheet_caps():
    from rest_framework.exceptions import ValidationError
    document = normalize_document(build("minimal", "member_cards"))
    with pytest.raises(ValidationError):
        render_sheets([])
    with pytest.raises(ValidationError):
        render_sheets([(document, _context())], paper="a3")


def test_mono_mode_renders_on_white():
    document = normalize_document({**build("bold", "member_cards"), "mono": True})
    png = render_png(document, _context(), dpi=72)
    from PIL import Image
    with Image.open(io.BytesIO(png)) as image:
        corner = image.convert("RGB").getpixel((image.width - 3, 2))
    assert corner == (255, 255, 255)


@pytest.mark.parametrize("template", ["classic", "community"])
@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("number", ["APAM-2026-0001", "APAM-2026-0002", "WWWWWW-2026-9999", "WWWWWW-2026-2147483647"])
def test_full_card_identifiers_survive_real_pdf_rendering_at_readable_size(template, theme, number):
    from pypdf import PdfReader
    from reportlab.lib.units import mm
    from apps.card_designs.rendering_text import fit

    document = normalize_document(build(template, "id_programme", theme))
    values = {**VALUES, "name": "Alexandria Rowan Engineering Workshop", "number": number}
    data = render_pdf(document, RenderContext(values=values), sides=("front",))
    fragments = []
    page = PdfReader(io.BytesIO(data)).pages[0]
    text = page.extract_text(visitor_text=lambda value, _cm, _tm, _font, size: fragments.append((value, size)))
    assert number in text  # The distinguishing sequence must be printed, not hidden behind an ellipsis.
    assert any(number in value and size >= 6 for value, size in fragments)
    layer = next(row for row in document["front"]["layers"] if row.get("field") == "number")
    size, lines = fit(number, layer, layer["w_mm"] * mm, layer["h_mm"] * mm)
    assert lines == [number] and size >= 6
