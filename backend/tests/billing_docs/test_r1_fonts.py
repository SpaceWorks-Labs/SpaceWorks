"""G2/G4: coverage, embedded glyphs, shaping, extraction and shaping clusters."""

from io import BytesIO
import re
import unicodedata

import pytest
from fontTools.ttLib import TTFont
from pypdf import PdfReader
from pypdf.generic import ContentStream, DictionaryObject
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas

from apps.operations.printable_fonts import font_paths, font_cmap, font_runs, select_font
from apps.operations.printable_paragraph import UnicodeParagraph
from apps.operations.printable_text_fonts import FontScope, shaped_run

SAMPLES = ["Zoë", "Ελληνικά", "Кириллица", "العربية", "שָׁלוֹם", "नमस्ते", "ক্ষি", "ਪੰਜਾਬੀ", "ગુજરાતી",
    "ଓଡ଼ିଆ", "கொ", "తెలుగు", "ಕನ್ನಡ", "മലയാളം", "සිංහල", "ภาษาไทย", "ខ្មែរ", "က္က", "ລາວ", "አማርኛ",
    "Հայերեն", "ქართული", "བོད", "简体中文", "繁體中文", "日本語", "한국어", "क्‍ष क्‌ष", "العربية 123 Latin"]


def pdf_for(text):
    output = BytesIO()
    with FontScope():
        canvas = Canvas(output, invariant=1)
        paragraph = UnicodeParagraph(text, ParagraphStyle("test", fontSize=12, leading=18))
        paragraph.wrap(500, 500)
        paragraph.drawOn(canvas, 30, 700)
        canvas.save()
    return PdfReader(BytesIO(output.getvalue()))


def extracted_text(reader):
    # Complex glyph offsets are kerning, not word separators. Use an ActualText-
    # aware reader for logical extraction and pypdf below for embedded cmap proof.
    # Every rendered line is wrapped in a /Span ActualText marked-content block.
    page = reader.pages[0]
    lines = [
        str(operands[1]["/ActualText"])
        for operands, operator in ContentStream(page.get_contents(), reader).operations
        if operator == b"BDC" and len(operands) > 1 and isinstance(operands[1], DictionaryObject)
        and "/ActualText" in operands[1]
    ]
    return "\n".join(lines).strip()


@pytest.mark.parametrize("text", SAMPLES)
def test_covered_scripts_select_covering_cmaps_and_extract_logical_text(text):
    for filename, run in font_runs(text):
        codes = {ord(c) for c in run if unicodedata.category(c) != "Cf"}
        assert codes <= font_cmap(filename), (filename, run)
    reader = pdf_for(text)
    page = reader.pages[0]
    assert extracted_text(reader) == text
    embedded = 0
    for reference in page["/Resources"]["/Font"].values():
        font = reference.get_object()
        descriptor = font.get("/FontDescriptor")
        if not descriptor:
            continue
        embedded += 1
        subset = TTFont(BytesIO(descriptor.get_object()["/FontFile2"].get_data()))
        cmap = {}
        for table in subset["cmap"].tables:
            cmap.update(table.cmap)
        unicode_map = font["/ToUnicode"].get_data().decode("ascii")
        # Every text-bearing code in the subset must address a real glyph, not gid 0.
        mappings = "\n".join(re.findall(r"beginbfchar\s*(.*?)\s*endbfchar", unicode_map, re.S))
        for code, logical in re.findall(r"<([0-9A-Fa-f]{2})> <([0-9A-Fa-f]*)>", mappings):
            if logical and bytes.fromhex(logical).decode("utf-16-be").strip("\x00 "):
                glyph = cmap.get(int(code, 16))
                assert glyph and subset.getGlyphID(glyph) != 0
    assert embedded > 0


@pytest.mark.parametrize("text", ["العربية", "क्षि", "ক্ষি", "கொ", "ខ្មែរ", "က္က"])
def test_complex_scripts_shape_to_real_glyph_sequences(text):
    changed = False
    with FontScope() as scope:
        for filename, run in font_runs(text):
            font = scope.get(filename)
            original = [font.face.charToGlyph.get(ord(c), 0) for c in run]
            _, shaped, _ = shaped_run(filename, run, 12, encode=True)
            actual = [font.face.charToGlyph[ord(c)] for c in shaped]
            assert all(actual)
            changed |= actual != original
    assert changed, text


def test_every_script_in_the_full_bundle_has_a_covering_fallback():
    from fontTools.unicodedata import script
    samples = {}
    for filename in font_paths():
        for code in sorted(font_cmap(filename)):
            char = chr(code)
            if unicodedata.category(char).startswith("L"):
                samples.setdefault(script(char), char)
    assert len(samples) > 100  # Full Noto, rather than the old five-font vocabulary.
    for name, sample in samples.items():
        selected = select_font(sample)
        assert ord(sample) in font_cmap(selected), (name, selected)
        assert extracted_text(pdf_for(sample)) == sample


def test_joiners_combining_marks_and_mixed_rtl_keep_their_cluster_font():
    for text in ("क्‍ष", "ক্‌ষ", "e\u0301", "ខ្មែរ", "မြန်မာ"):
        runs = font_runs(text)
        assert len(runs) == 1
        assert all(ord(char) in font_cmap(runs[0][0]) for char in text if unicodedata.category(char) != "Cf")
    assert pdf_for("العربية 123 Latin").pages[0].extract_text().strip() == "العربية 123 Latin"


def test_uncovered_private_use_codepoint_does_not_crash_pdf():
    assert pdf_for("Unassigned \U0010ffff").pages
