"""Print-ready output (decision 344(b)): mirror bleed, crop marks and PDF page boxes around the unchanged trim."""
from io import BytesIO

import pytest
from PIL import Image
from rest_framework.exceptions import ValidationError

from apps.card_designs.layout import normalize_document
from apps.card_designs.print_export import options_from_query, render_print_pdf, render_print_png
from apps.card_designs.rendering import RenderContext, render_png

from .conftest import document, layer

PT_PER_MM = 72 / 25.4


def _doc(**top):
    background = {"kind": "gradient", "type": "linear", "angle_deg": 90,
                  "stops": [{"colour": "#006E63", "at": 0}, {"colour": "#DFFF8F", "at": 100}]}
    return normalize_document(document([layer("band", 0, 75, 54, 10.6, fill="#142C2A")], background=background, **top),
                              check_contrast=False)


def _page_size(pdf):
    import pypdfium2 as pdfium
    page = pdfium.PdfDocument(pdf)[0]
    return page.get_size()


def _trim(doc):
    return doc["front"]["page_width_mm"], doc["front"]["page_height_mm"]  # CR80 portrait: 53.98 x 85.6


def test_a_print_pdf_is_trim_plus_bleed_plus_the_mark_slug():
    doc = _doc()
    width, height = _page_size(render_print_pdf(doc, RenderContext(), bleed_mm=3, crop_marks=True))
    assert width == pytest.approx((_trim(doc)[0] + 2 * 10) * PT_PER_MM, abs=0.05)  # 3 mm bleed + 7 mm slug each side
    assert height == pytest.approx((_trim(doc)[1] + 2 * 10) * PT_PER_MM, abs=0.05)


def test_without_marks_the_page_is_trim_plus_bleed_and_carries_page_boxes():
    doc = _doc()
    pdf = render_print_pdf(doc, RenderContext(), bleed_mm=2, crop_marks=False)
    assert _page_size(pdf)[0] == pytest.approx((_trim(doc)[0] + 4) * PT_PER_MM, abs=0.05)
    assert b"/TrimBox" in pdf and b"/BleedBox" in pdf


def test_a_print_png_is_300_dpi_with_the_bleed():
    doc = _doc()
    image = Image.open(BytesIO(render_print_png(doc, RenderContext(), bleed_mm=3)))
    width, height = _trim(doc)
    assert image.size == (round((width + 6) / 25.4 * 300), round((height + 6) / 25.4 * 300))


def test_the_trim_area_is_the_same_card_and_the_bleed_continues_the_edges():
    doc = _doc()
    plain = Image.open(BytesIO(render_png(doc, RenderContext()))).convert("RGB")
    bleed = Image.open(BytesIO(render_print_png(doc, RenderContext(), bleed_mm=3))).convert("RGB")
    offset = round(3 / 25.4 * 300)
    for x, y in ((50, 50), (300, 500), (600, 980)):  # inside the trim: identical pixels (tolerance for resampling)
        assert all(abs(a - b) <= 6 for a, b in zip(plain.getpixel((x, y)), bleed.getpixel((x + offset, y + offset))))
    # The band touches the bottom trim edge: its colour runs on into the bottom bleed (mirror), not white paper.
    bottom = bleed.getpixel((bleed.width // 2, bleed.height - 3))
    assert all(abs(a - b) <= 12 for a, b in zip(bottom, (0x14, 0x2C, 0x2A)))


def test_bleed_is_capped_and_query_options_are_validated():
    assert options_from_query({"bleed_mm": "3", "crop_marks": "true"}) == {"bleed_mm": 3.0, "crop_marks": True}
    assert options_from_query({}) == {"bleed_mm": 0.0, "crop_marks": False}
    for bad in ({"bleed_mm": "6"}, {"bleed_mm": "x"}, {"crop_marks": "maybe"}, {"bleed_mm": "-1"}):
        with pytest.raises(ValidationError):
            options_from_query(bad)
