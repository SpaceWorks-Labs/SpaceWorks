"""ReportLab must attempt the supported floor for arbitrary float font sizes."""

from io import BytesIO
from types import SimpleNamespace

import pytest
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph
from rest_framework.exceptions import ValidationError

from apps.operations.printable_fonts import font_markup
from apps.operations.printable_pdf import text_box


@pytest.mark.parametrize("start", [6, 6.2, 7.3])
@pytest.mark.parametrize("text", ["W", "\u05e9\u05dc\u05d5\u05dd"])
@pytest.mark.parametrize("constraint", ["height", "width"])
def test_fractional_size_reaches_six_point_floor(start, text, constraint, monkeypatch):
    markup = font_markup(text, "sans", False)
    floor = Paragraph(markup, ParagraphStyle("floor", fontName="Print-sans-False", fontSize=6, shaping=1))
    element = {
        "x_mm": 0, "y_mm": 0, "width_mm": 100, "height_mm": 20,
        "font": "sans", "font_size_pt": start, "bold": False,
        "align": "left", "colour": "#000000",
    }
    if constraint == "height":
        # One line fits at 6 pt (7.8 pt leading), but not at 6.2 pt.
        element["height_mm"] = 7.9 / mm
    else:
        # A single unbreakable word fits at 6 pt, but not at 6.2 pt.
        # For RTL this also exercises rtl_markup returning None before the floor.
        element["width_mm"] = floor.minWidth() * (6.05 / 6) / mm
        element["height_mm"] = 7.9 / mm
    drawn = []
    monkeypatch.setattr(Paragraph, "drawOn", lambda paragraph, *args: drawn.append(paragraph))

    text_box(Canvas(BytesIO()), text, element, area_height_mm=55)

    assert len(drawn) == 1
    assert drawn[0].style.fontSize == 6


@pytest.mark.parametrize("text", ["W", "\u05e9\u05dc\u05d5\u05dd"])
def test_fractional_overflow_stops_after_floor_without_drawing(text, monkeypatch):
    element = {
        "x_mm": 0, "y_mm": 0, "width_mm": 0.01, "height_mm": 20,
        "font": "sans", "font_size_pt": 6.2, "bold": False,
        "align": "left", "colour": "#000000",
    }
    drawn = []
    monkeypatch.setattr(Paragraph, "drawOn", lambda *args: drawn.append(args))
    with pytest.raises(ValidationError, match="does not fit"):
        text_box(Canvas(BytesIO()), text, element, area_height_mm=55)
    assert drawn == []


def test_certificate_preflight_reaches_floor_for_fractional_size(monkeypatch):
    from apps.events.certificate_rendering import validate_certificate_layout

    certificate = SimpleNamespace(recipient_name="Ada Lovelace", layout_snapshot={
        "page_width_mm": 297, "page_height_mm": 210,
        "artwork_object_key": "private/artwork.png",
        "name_box": {
            "x_mm": 0, "y_mm": 0, "width_mm": 100, "height_mm": 7.9 / mm,
            "font": "sans", "font_size_pt": 6.2, "bold": False,
            "align": "left", "colour": "#000000",
        },
    })
    drawn = []
    monkeypatch.setattr(Paragraph, "drawOn", lambda paragraph, *args: drawn.append(paragraph))

    validate_certificate_layout(certificate)

    assert len(drawn) == 1 and drawn[0].style.fontSize == 6
