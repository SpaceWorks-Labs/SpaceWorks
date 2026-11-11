"""Logical paragraph line order survives visual bidi reordering."""
from types import SimpleNamespace

from apps.operations import printable_pdf


def test_rtl_reorders_each_wrapped_line_without_moving_last_words_to_first(monkeypatch):
    from arabic_reshaper import reshape
    from bidi.algorithm import get_display
    import reportlab.platypus

    # A deterministic two-word line capacity isolates paragraph ordering from
    # provider font metrics. The production bidi transform remains real.
    class TwoWordLine:
        def __init__(self, markup, style):
            self.markup = markup
            self.blPara = SimpleNamespace(kind=0, lines=[(0, [])])

        def wrap(self, width, height):
            return width, 10 if len(self.markup.split()) <= 2 else 20

    def visual(text, family, bold):
        return get_display(reshape(text))

    monkeypatch.setattr(reportlab.platypus, "Paragraph", TwoWordLine)
    monkeypatch.setattr(printable_pdf, "font_markup", visual)
    text = "\u0627\u0644\u0623\u0648\u0644 \u0627\u0644\u062b\u0627\u0646\u064a \u0627\u0644\u062b\u0627\u0644\u062b \u0627\u0644\u0631\u0627\u0628\u0639"
    actual = printable_pdf.rtl_markup(
        text, {"font": "sans", "bold": False}, SimpleNamespace(leading=10), 100,
    )
    expected = [visual("\u0627\u0644\u0623\u0648\u0644 \u0627\u0644\u062b\u0627\u0646\u064a", "sans", False), visual("\u0627\u0644\u062b\u0627\u0644\u062b \u0627\u0644\u0631\u0627\u0628\u0639", "sans", False)]
    assert actual.split("<br/>") == expected
    assert actual.split("<br/>")[0] != visual("\u0627\u0644\u062b\u0627\u0644\u062b \u0627\u0644\u0631\u0627\u0628\u0639", "sans", False)


def test_rtl_unbreakable_word_requests_smaller_font_instead_of_clipping(monkeypatch):
    import reportlab.platypus

    class TooWide:
        def __init__(self, markup, style):
            pass

        def wrap(self, width, height):
            return width, 20

    monkeypatch.setattr(reportlab.platypus, "Paragraph", TooWide)
    monkeypatch.setattr(printable_pdf, "font_markup", lambda text, family, bold: text)
    assert printable_pdf.rtl_markup(
        "\u0627\u0633\u0645\u0637\u0648\u064a\u0644", {"font": "sans", "bold": False}, SimpleNamespace(leading=10), 1,
    ) is None
