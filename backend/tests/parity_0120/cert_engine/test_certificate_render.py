"""The certificate layers drawn through the shared `draw_side`: signatures and consent, rows, seals, serial, QR, PDF."""
from io import BytesIO

import pytest
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from apps.card_designs import rendering_certificate
from apps.card_designs.layout import normalize_document
from apps.card_designs.rendering import RenderContext, draw_side, page_size

from .helpers import certificate, layer, signatory, signature
from .recording import Recorder


def _ops(document, **context):
    recorder = Recorder()
    draw_side(recorder, document, "front", RenderContext(**context))
    return recorder.ops


def _kinds(ops):
    return [op[0] for op in ops]


def _texts(ops):
    return [op[4] for op in ops if op[0] == "text"]


def test_an_approved_signatory_prints_image_rule_name_and_title():
    ops = _ops(normalize_document(certificate([signature(1)])), signatories={1: signatory()})
    assert _kinds(ops).count("image") == 1 and _kinds(ops).count("line") == 1
    assert _texts(ops) == ["Dr Director", "Director"]


def test_an_unapproved_signatory_is_a_placeholder_rule_never_the_image_or_the_name():
    ops = _ops(normalize_document(certificate([signature(1)])), signatories={1: signatory(approved=False)})
    assert "image" not in _kinds(ops) and _texts(ops) == [] and _kinds(ops).count("line") == 1


def test_a_missing_signatory_is_a_placeholder_rule_and_never_an_error():
    ops = _ops(normalize_document(certificate([signature(2)])), signatories={1: signatory()})
    assert "image" not in _kinds(ops) and _texts(ops) == [] and _kinds(ops).count("line") == 1


def test_the_signature_parts_can_be_switched_off_and_the_rule_removed():
    document = normalize_document(certificate([signature(1, show_image=False, show_title=False, rule=None)]))
    ops = _ops(document, signatories={1: signatory()})
    assert "image" not in _kinds(ops) and "line" not in _kinds(ops) and _texts(ops) == ["Dr Director"]


def test_a_signature_without_an_image_still_prints_name_and_title():
    ops = _ops(normalize_document(certificate([signature(1)])), signatories={1: signatory(image=False)})
    assert "image" not in _kinds(ops) and _texts(ops) == ["Dr Director", "Director"]


def test_the_signature_geometry_is_the_v2_one():
    document = normalize_document(certificate([signature(1, x=20, y=120, w=70, h=30)]))
    ops = _ops(document, signatories={1: signatory()})
    page_h = document["front"]["page_height_mm"]
    line = next(op for op in ops if op[0] == "line")
    assert line[2] == pytest.approx((page_h - 120 - 30 * 0.6) * mm, abs=0.01)
    assert line[1] == pytest.approx((20 + 70 * 0.08) * mm, abs=0.01)
    image = next(op for op in ops if op[0] == "image")
    assert image[4] <= 30 * 0.56 * mm + 0.01  # the image sits in the top 56 % of the layer


def test_a_signature_row_spaces_the_present_signatories_equally_and_skips_absent_slots():
    document = normalize_document(certificate([layer("signature_row", 20, 120, 200, 30, slots=[1, 2, 3], gap_mm=14)]))
    ops = _ops(document, signatories={1: signatory("A", "One"), 3: signatory("C", "Three")})
    lines = [op for op in ops if op[0] == "line"]
    assert len(lines) == 2 and _texts(ops) == ["A", "One", "C", "Three"]
    expected = rendering_certificate.cells(200 * mm, 14 * mm, 2)
    for row, (offset, width) in zip(lines, expected):
        assert row[1] == pytest.approx(20 * mm + offset + width * 0.08, abs=0.01)
        assert row[3] == pytest.approx(20 * mm + offset + width * 0.92, abs=0.01)
    assert _ops(document, signatories={}) == [op for op in _ops(document, signatories={}) if op[0] == "rect"]


def test_row_cells_are_equal_and_fill_the_width():
    cells = rendering_certificate.cells(200, 14, 3)
    assert [round(width, 6) for _offset, width in cells] == [57.333333] * 3
    assert cells[2][0] + cells[2][1] == pytest.approx(200)
    assert rendering_certificate.cells(130, 8, 1) == [(0.0, 130.0)]


@pytest.mark.parametrize("style", ["ring", "scallop", "star"])
def test_a_seal_draws_ring_text_one_glyph_at_a_time_and_the_label(style):
    document = normalize_document(certificate([layer("seal", 20, 20, 40, 40, style=style, fill="#006E63", stroke="#FFFFFF",
                                                     ring_text="SPACE WORKS CERTIFIED", label="{{kind}}")]))
    ops = _ops(document, values={"kind": "Winner"})
    texts = _texts(ops)
    assert len(texts) == len("SPACE WORKS CERTIFIED") + 1 and texts[-1] == "Winner"
    assert "".join(texts[:-1]) == "SPACE WORKS CERTIFIED"


def test_a_seal_without_ring_text_or_label_draws_no_text():
    document = normalize_document(certificate([layer("seal", 20, 20, 30, 30, stroke="#142C2A")]))
    assert _texts(_ops(document)) == []


def test_the_certificate_number_prints_in_full_or_short():
    values = {"serial": "SW-2026-000042", "serial_short": "SW-2026-"}
    full = normalize_document(certificate([layer("certificate_id", 10, 10, 60, 6)]))
    short = normalize_document(certificate([layer("certificate_id", 10, 10, 60, 6, format="short")]))
    assert _texts(_ops(full, values=values)) == ["SW-2026-000042"]
    assert _texts(_ops(short, values=values)) == ["SW-2026-"]


def test_the_verification_qr_prints_a_real_code_and_a_preview_prints_a_dummy():
    document = normalize_document(certificate([layer("verify_qr", 10, 170, 22, 22)]))
    preview = _ops(document, preview=True)
    assert len([op for op in preview if op[0] == "rect"]) > 5  # the dummy pattern
    assert _pdf(document, RenderContext(verify_qr="https://example.org/certificates/verify/SW-1")).startswith(b"%PDF")


def _pdf(document, context):
    out = BytesIO()
    canvas = Canvas(out, pagesize=page_size(document), pageCompression=1, invariant=1)
    canvas.setTitle("Certificate")
    draw_side(canvas, document, "front", context)
    canvas.showPage()
    canvas.save()
    return out.getvalue()


def test_the_pdf_is_stable_embeds_its_fonts_and_has_no_active_content():
    document = normalize_document(certificate([
        layer("text", 20, 30, 200, 14, text="{{recipient}}", font_size_pt=30),
        signature(1), layer("seal", 230, 20, 30, 30, stroke="#142C2A", ring_text="SPACE WORKS"),
        layer("verify_qr", 10, 170, 22, 22), layer("certificate_id", 40, 190, 100, 6)]))
    context = RenderContext(values={"recipient": "Fathima Shenza", "serial": "SW-1"}, signatories={1: signatory()},
                            verify_qr="https://example.org/certificates/verify/SW-1")
    first, second = _pdf(document, context), _pdf(document, context)
    assert first == second and first.startswith(b"%PDF")
    assert b"/FontFile2" in first  # the TrueType faces are embedded, not referenced
    for forbidden in (b"/JavaScript", b"/JS", b"/Encrypt", b"/URI", b"/Launch"):
        assert forbidden not in first
