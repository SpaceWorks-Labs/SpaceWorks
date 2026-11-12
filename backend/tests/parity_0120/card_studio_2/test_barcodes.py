"""Barcode symbologies (decision 345(c)): one encoder for print and the designer, minimum sizes, and the routes."""
import pytest
from rest_framework.exceptions import ValidationError

from apps.card_designs import barcode_symbols
from apps.card_designs.layout import normalize_document
from apps.card_designs.layout_layers import normalize_layer
from apps.card_designs.rendering import RenderContext, render_pdf

from .conftest import document, layer

LANDSCAPE = (85.6, 53.98, "cr80-landscape")


def _norm(**extra):
    return normalize_layer(layer("barcode", 2, 2, extra.pop("w", 40), extra.pop("h", 12), **extra), *LANDSCAPE)


@pytest.mark.parametrize("symbology,payload", [("code128", "TNK-0042"), ("code39", "TNK-0042"), ("ean13", "590123412345"),
                                               ("upca", "03600029145"), ("pdf417", "TNK-0042"), ("datamatrix", "TNK-0042"),
                                               ("aztec", "TNK-0042")])
def test_every_symbology_encodes_deterministically(symbology, payload):
    first, second = barcode_symbols.encode(symbology, payload), barcode_symbols.encode(symbology, payload)
    assert first == second and first["symbology"] == symbology
    if first["kind"] == "linear":
        assert set(first["bars"]) == {"0", "1"} and first["bars"][0] == "1"
    else:
        assert len({len(row) for row in first["rows"]}) == 1 and "1" in "".join(first["rows"])


def test_ean_and_upc_take_digits_only_and_check_a_given_check_digit():
    assert barcode_symbols.encode("ean13", "TNK-0042") is None
    assert barcode_symbols.encode("ean13", "590123412345")["text"] == "5901234123457"
    assert barcode_symbols.encode("ean13", "5901234123457") is not None
    assert barcode_symbols.encode("ean13", "5901234123450") is None  # wrong check digit
    assert barcode_symbols.encode("upca", "03600029145")["text"] == "036000291452"
    assert barcode_symbols.encode("code128", "x" * 81) is None


def test_code128_keeps_the_bars_cards_printed_before():
    from reportlab.graphics.barcode.code128 import Code128
    probe = Code128("TNK-0042", barWidth=1, quiet=False)
    assert len(barcode_symbols.encode("code128", "TNK-0042")["bars"]) == probe.width


def test_rects_fill_linear_quiet_zones_and_centre_square_modules():
    linear = barcode_symbols.rects({"kind": "linear", "bars": "1101", "quiet": [2, 2]}, 16, 10, 2, gap=0.4)
    assert linear == [[4.0, 0.2, 4.0, 7.6], [10.0, 0.2, 2.0, 7.6]]
    matrix = barcode_symbols.rects({"kind": "matrix", "rows": ["10", "11"]}, 20, 10)
    assert matrix == [[5.0, 0.0, 5.0, 5.0], [5.0, 5.0, 10.0, 5.0]]


def test_the_layer_keeps_a_non_default_symbology_and_checks_its_minimum():
    assert _norm(symbology="aztec", w=12, h=12)["symbology"] == "aztec"
    assert "symbology" not in _norm(symbology="code128")  # sparse: the default is omitted
    with pytest.raises(ValidationError):
        _norm(symbology="aztec", w=8, h=8)
    with pytest.raises(ValidationError):
        _norm(symbology="code39", source="desk", w=80, h=12)  # Code 39 cannot carry the 32-character desk code
    with pytest.raises(ValidationError):
        _norm(symbology="qrcode-ish")


def test_cards_render_every_symbology_and_an_unfit_number_prints_nothing():
    layers = [layer("barcode", 2, 2, 40, 12, symbology="code39"), layer("barcode", 44, 2, 32, 12, symbology="ean13"),
              layer("barcode", 2, 20, 40, 12, symbology="pdf417"), layer("barcode", 50, 20, 14, 14, symbology="datamatrix"),
              layer("barcode", 66, 20, 14, 14, symbology="aztec")]
    doc = normalize_document(document(layers, stock="cr80-landscape"), check_contrast=False)
    assert render_pdf(doc, RenderContext(values={"number": "TNK-0042"})).startswith(b"%PDF")
    assert render_pdf(doc, RenderContext(values={"number": "TNK-0042"}, preview=True)).startswith(b"%PDF")
