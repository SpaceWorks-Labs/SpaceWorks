"""Unicode report font, independent of every separable domain."""

from pathlib import Path


def report_font_name():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    name = "ReportUnicode"
    if name not in pdfmetrics.getRegisteredFontNames():
        # Bundle Unicode coverage independently of host fonts or separable apps.
        # ReportLab's Vera lacks Greek glyphs and silently renders them as .notdef.
        font = Path(__file__).parent / "fonts" / "RobotoStatic-Regular.ttf"
        pdfmetrics.registerFont(TTFont(name, str(font)))
    return name
