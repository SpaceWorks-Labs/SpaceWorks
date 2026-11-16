"""Certificate documents on the shared engine: stocks, the four certificate layer kinds, tags and the kind fences."""
import pytest
from rest_framework.exceptions import ValidationError

from apps.card_designs import stocks
from apps.card_designs.layout import normalize_document

from .helpers import certificate, layer, signature


def _text(**extra):
    return layer("text", 20, 40, 100, 12, text="{{recipient}} - {{event_date}} - {{hours}} - {{achievement}}", **extra)


@pytest.mark.parametrize("stock", ["a4-landscape", "a4-portrait", "letter-landscape", "letter-portrait",
                                   "a5-landscape", "a5-portrait"])
def test_certificate_stocks_are_accepted(stock):
    width, height = stocks.STOCKS[stock]
    document = normalize_document(certificate([_text()], stock=stock))
    assert document["kind"] == "certificate" and document["front"]["page_width_mm"] == width


def test_a_certificate_refuses_card_stocks_and_takes_custom_sizes_to_420_mm():
    with pytest.raises(ValidationError):
        normalize_document(certificate([_text()], stock="cr80-landscape"))
    ok = normalize_document(certificate([_text()], stock="custom", page_width_mm=420, page_height_mm=100))
    assert (ok["page_width_mm"], ok["page_height_mm"]) == (420.0, 100.0)
    for width, height in ((421, 200), (210, 99)):
        with pytest.raises(ValidationError):
            normalize_document(certificate([_text()], stock="custom", page_width_mm=width, page_height_mm=height))


def test_certificate_tags_exist_only_in_a_certificate():
    normalize_document(certificate([_text()]))
    card = {"version": 3, "stock": "cr80-landscape", "back_enabled": False, "mono": False,
            "front": {"background": {"kind": "colour", "colour": "#FFFFFF"},
                      "layers": [layer("text", 2, 2, 40, 8, text="{{recipient}}")]}, "back": {"layers": []}}
    with pytest.raises(ValidationError):
        normalize_document(card)
    for tag in ("recipient", "event_date", "issue_date", "kind", "award", "place", "hours", "achievement", "serial",
                "serial_short"):
        normalize_document(certificate([layer("text", 20, 40, 100, 12, text="{{" + tag + "}}")]))


def test_a_certificate_document_is_one_page_with_the_certificate_fences():
    from apps.events.certificate_templates import normalize_certificate_template
    two_pages = certificate([_text()], back_enabled=True)
    with pytest.raises(ValidationError):
        normalize_certificate_template(two_pages)
    for kind, extra in (("photo", {}), ("desk_qr", {}), ("checkin_qr", {}), ("perforation", {"colour": "#D5D0C6"})):
        with pytest.raises(ValidationError):
            normalize_document(certificate([layer(kind, 20, 40, 30, 30, **extra)]))
    with pytest.raises(ValidationError):
        normalize_document(certificate([layer("logo", 20, 40, 20, 20, source="space")]))
    normalize_document(certificate([layer("logo", 20, 40, 20, 20, source="symbol")]))


def test_certificate_layers_are_refused_on_a_card():
    card = {"version": 3, "stock": "cr80-landscape", "back_enabled": False, "mono": False,
            "front": {"background": {"kind": "colour", "colour": "#FFFFFF"},
                      "layers": [signature(1, 5, 5, 30, 20)]}, "back": {"layers": []}}
    with pytest.raises(ValidationError):
        normalize_document(card)


def test_signature_layer_defaults_and_validation():
    row = normalize_document(certificate([signature(2)]))["front"]["layers"][0]
    assert row["signatory_slot"] == 2 and row["show_image"] and row["show_name"] and row["show_title"]
    assert row["rule"] == {"colour": row["colour"], "width_pt": 0.6}
    for bad in ({"signatory_slot": 4}, {"signatory_slot": True}, {"font_family": "Comic Sans"}, {"rule": {"width_pt": 9}},
                {"rule": {"colour": "red"}}, {"image_url": "https://x.test/a.png"}, {"show_name": "yes"}):
        with pytest.raises(ValidationError):
            normalize_document(certificate([{**signature(1), **bad}]))
    with pytest.raises(ValidationError):  # a signature needs room for the image, name and title
        normalize_document(certificate([signature(1, w=70, h=8)]))
    assert normalize_document(certificate([signature(1, rule=None)]))["front"]["layers"][0]["rule"] is None


def test_signature_row_layer():
    row = normalize_document(certificate([layer("signature_row", 20, 120, 200, 30, slots=[3, 1])]))["front"]["layers"][0]
    assert row["slots"] == [1, 3] and row["gap_mm"] == 8.0
    for bad in ({"slots": []}, {"slots": [1, 1]}, {"slots": [0]}, {"slots": [1, 2, 3, 4]}, {"slots": [1], "gap_mm": 2},
                {"slots": [1], "gap_mm": 41}):
        with pytest.raises(ValidationError):
            normalize_document(certificate([layer("signature_row", 20, 120, 200, 30, **bad)]))


def test_seal_layer():
    row = normalize_document(certificate([layer("seal", 20, 20, 30, 30, style="star", fill="#DFFF8F", stroke="#142C2A",
                                                label="{{kind}}", ring_text="SPACE WORKS")]))["front"]["layers"][0]
    assert row["style"] == "star" and row["label"] == "{{kind}}" and row["ring_text_colour"] == "#142C2A"
    assert set(row["label_style"]) == {"font_family", "font_weight", "font_size_pt", "colour"}
    for bad in ({"style": "heart", "fill": "#FFFFFF"}, {"fill": None, "stroke": None}, {"fill": "#FFFFFF", "label": "x" * 25},
                {"fill": "#FFFFFF", "ring_text": "x" * 41}, {"fill": "#FFFFFF", "ring_text": "{{kind}}"},
                {"fill": "#FFFFFF", "ring_text": "കേരളം"},  # ring text is Latin only
                {"fill": "#FFFFFF", "label_style": {"font_size": 9}}):
        with pytest.raises(ValidationError):
            normalize_document(certificate([layer("seal", 20, 20, 30, 30, **bad)]))


def test_certificate_number_and_verification_qr_cannot_be_hidden_and_the_qr_keeps_20_mm():
    for kind, size in (("certificate_id", (60, 6)), ("verify_qr", (22, 22))):
        with pytest.raises(ValidationError):
            normalize_document(certificate([layer(kind, 10, 10, *size, hidden=True)]))
    with pytest.raises(ValidationError):
        normalize_document(certificate([layer("verify_qr", 10, 10, 19, 19)]))
    row = normalize_document(certificate([layer("certificate_id", 10, 10, 60, 6, format="short")]))["front"]["layers"][0]
    assert row["text"] == "{{serial_short}}" and row["format"] == "short"
    assert normalize_document(certificate([layer("certificate_id", 10, 10, 60, 6)]))["front"]["layers"][0]["text"] == "{{serial}}"


def test_printed_slots_cover_signatures_and_rows():
    from apps.card_designs.layout_certificate import printed_slots
    document = normalize_document(certificate([signature(2), layer("signature_row", 20, 120, 200, 30, slots=[1, 3])]))
    assert printed_slots(document) == [1, 2, 3]


def test_the_events_slot_gate_reads_studio_documents():
    from apps.events.certificates.signatories import printed_slots
    document = normalize_document(certificate([signature(3)]))
    assert printed_slots(document) == [3]
    assert printed_slots({"version": 2, "layers": [{"type": "signature", "signature_slot": 1}]}) == [1]


def test_unreadable_certificate_number_is_caught_by_the_contrast_check():
    with pytest.raises(ValidationError):
        normalize_document(certificate([layer("certificate_id", 10, 10, 60, 6, colour="#EEEEEE")]))


def test_normalising_a_saved_certificate_again_changes_nothing():
    from apps.card_designs.default_templates import CERTIFICATE_LOOKS, THEMES, build_certificate
    mixed = certificate([signature(1), layer("signature_row", 20, 120, 200, 30, slots=[2, 3]),
                         layer("seal", 20, 20, 30, 30, style="scallop", fill="#006E63", ring_text="SPACE WORKS", label="{{kind}}"),
                         layer("certificate_id", 10, 10, 60, 6, format="short"), layer("verify_qr", 10, 170, 22, 22)])
    documents = [mixed, *(build_certificate(key, theme) for key in CERTIFICATE_LOOKS for theme in THEMES)]
    for document in documents:
        once = normalize_document(document)
        assert normalize_document(once) == once
