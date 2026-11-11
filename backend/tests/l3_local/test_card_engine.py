"""L3 card engine: documents, stocks, templates, contrast, fonts, data fields, design files."""
import copy
from uuid import uuid4

import pytest
from rest_framework.exceptions import ValidationError

from apps.card_designs import contrast, data_fields, design_file, fonts, stocks
from apps.card_designs.default_templates import LABELS, TEMPLATES, build, default_document
from apps.card_designs.layout import normalize_document, upgrade


def _text(**extra):
    return {"id": str(uuid4()), "kind": "text", "name": "t", "x_mm": 5, "y_mm": 5, "w_mm": 40, "h_mm": 6,
            "text": "Hello {{name}}", "font_family": "Outfit", "font_weight": 700, "colour": "#142C2A", **extra}


def _doc(layers, background="#FFFFFF", **extra):
    return {"version": 2, "stock": "cr80-landscape", "back_enabled": False, "mono": False,
            "front": {"background": {"kind": "colour", "colour": background}, "layers": layers},
            "back": {"layers": []}, **extra}


def test_cr80_is_85_60_by_53_98_everywhere():
    assert stocks.STOCKS["cr80-landscape"] == (85.6, 53.98)
    assert stocks.STOCKS["cr80-portrait"] == (53.98, 85.6)
    assert stocks.STOCKS["a6-landscape"] == (148.0, 105.0)
    assert stocks.qr_minimum_mm("cr80-landscape") == 18 and stocks.qr_minimum_mm("a6-portrait") == 20


def test_custom_stock_bounds():
    assert stocks.dimensions("custom", 40, 300) == (40.0, 300.0)
    for bad in ((39.9, 100), (100, 300.1), ("a", 50)):
        with pytest.raises(ValidationError):
            stocks.dimensions("custom", *bad)


@pytest.mark.parametrize("key", list(TEMPLATES))
@pytest.mark.parametrize("domain", ["member_cards", "id_programme", "event_card", "event_ticket"])
def test_every_template_normalises_and_passes_contrast(key, domain):
    document = normalize_document(build(key, domain))
    assert document["version"] == 2
    assert set(LABELS) == {"classic", "bold", "minimal", "community", "student", "event_pass"}


def test_defaults_per_domain():
    assert default_document("member_cards")["back_enabled"] is True
    member = default_document("member_cards")["front"]["layers"]
    assert any(layer["kind"] == "desk_qr" for layer in member)
    assert any(layer["kind"] == "verify_qr" for layer in default_document("id_programme")["front"]["layers"])
    assert default_document("event_card")["stock"] == "cr80-portrait"


def test_contrast_refuses_unreadable_text_and_mono_skips_it():
    with pytest.raises(ValidationError) as caught:
        normalize_document(_doc([_text(colour="#F0F0F0")]))
    assert "contrast" in caught.value.detail
    assert normalize_document(_doc([_text(colour="#F0F0F0")], mono=True))["mono"] is True


def test_contrast_reads_the_shape_under_the_text():
    band = {"id": str(uuid4()), "kind": "band", "name": "b", "x_mm": 0, "y_mm": 0, "w_mm": 85.6, "h_mm": 20,
            "fill": "#142C2A"}
    with pytest.raises(ValidationError):
        normalize_document(_doc([band, _text(colour="#1F2A2A")]))
    assert normalize_document(_doc([band, _text(colour="#FFF4E8")]))


def test_gradient_contrast_samples_the_point():
    gradient = {"kind": "gradient", "type": "linear", "angle_deg": 90,
                "stops": [{"colour": "#000000", "at": 0}, {"colour": "#FFFFFF", "at": 100}]}
    side = {"page_width_mm": 100, "page_height_mm": 50, "background": gradient, "layers": []}
    left = contrast.background_at(gradient, 1, 25, 100, 50)
    right = contrast.background_at(gradient, 99, 25, 100, 50)
    assert contrast.luminance(left) < 0.05 < 0.9 < contrast.luminance(right)
    assert side


def test_qr_layers_need_size_full_opacity_and_right_angles():
    qr = {"id": str(uuid4()), "kind": "desk_qr", "name": "q", "x_mm": 60, "y_mm": 10, "w_mm": 18, "h_mm": 18}
    assert normalize_document(_doc([qr]))
    for change in ({"w_mm": 17, "h_mm": 17}, {"opacity": 90}, {"rotation": 45}):
        with pytest.raises(ValidationError):
            normalize_document(_doc([{**qr, **change}]))
    assert normalize_document(_doc([{**qr, "rotation": 90}]))


def test_layers_stay_on_the_card_and_ids_are_unique():
    with pytest.raises(ValidationError):
        normalize_document(_doc([_text(x_mm=80)]))
    layer = _text()
    with pytest.raises(ValidationError):
        normalize_document(_doc([layer, copy.deepcopy(layer)]))
    with pytest.raises(ValidationError):
        normalize_document(_doc([_text() for _ in range(41)]))


def test_fonts_come_only_from_the_card_font_library():
    assert {400, 500, 600, 700} <= set(fonts.family_weights("Outfit"))
    assert all(fonts.is_bundled("Outfit", weight) for weight in (400, 500, 600, 700))
    # Decision 220(c): the legacy "Gilroy" token reads as Outfit (old revisions, imports, dumps).
    assert fonts.family_weights("Gilroy") == fonts.family_weights("Outfit")
    assert [row["family"] for row in fonts.search("outfit")[1]].count("Outfit") == 1
    assert 700 in fonts.family_weights("Noto Sans Malayalam")
    assert fonts.family_weights("Comic Sans MS") == ()
    with pytest.raises(ValidationError):
        normalize_document(_doc([_text(font_family="Comic Sans MS")]))
    with pytest.raises(ValidationError):
        normalize_document(_doc([_text(font_family="Outfit", font_weight=950)]))
    legacy = normalize_document(_doc([_text(font_family="Gilroy", font_weight=700)]))
    assert legacy["front"]["layers"][0]["font_family"] == "Outfit"
    assert normalize_document(_doc([_text(font_family="Noto Sans Devanagari", font_weight=400)]))
    count, rows = fonts.search("noto sans", script="malayalam")
    assert count >= 1 and all("malayalam" in row["scripts"] for row in rows)
    assert len(fonts.catalogue()) > 1500


def test_data_fields_and_sensitive_tags():
    assert data_fields.valid_tag("name") and data_fields.valid_tag("field:shirt_size")
    assert not data_fields.valid_tag("password") and not data_fields.valid_tag("field:Bad Key")
    with pytest.raises(ValidationError):
        normalize_document(_doc([_text(text="{{secret}}")]))
    with pytest.raises(ValidationError):
        normalize_document(_doc([_text(text="stray { brace")]))
    values = {"name": "Priya", "blood_group": "O+"}
    assert data_fields.merge("{{name}} {{blood_group}}", values) == "Priya "
    assert data_fields.merge("{{name}} {{blood_group}}", values, allow_sensitive=True) == "Priya O+"


def test_watermark_bounds():
    base = _doc([_text()])
    for mark in ({"kind": "text", "text": "x" * 33}, {"kind": "text", "text": "OK", "opacity_pct": 3},
                 {"kind": "text", "text": "OK", "angle_deg": 61}, {"kind": "image", "asset_id": "nope"}):
        with pytest.raises(ValidationError):
            normalize_document({**base, "watermark": mark})
    assert normalize_document({**base, "watermark": {"kind": "text", "text": "MEMBER"}})["watermark"]["kind"] == "text"


def test_version_one_documents_upgrade_on_read():
    upgraded = upgrade({"version": 1, "stock": "cr80-landscape", "layers": [_text()]})
    assert normalize_document(upgraded)["front"]["layers"][0]["kind"] == "text"


def test_design_file_round_trip_and_version_refusal():
    class Design:
        domain = "member_cards"
        document = default_document("member_cards")

    exported = design_file.export(Design)
    document, notes = design_file.parse(__import__("json").dumps(exported))
    assert normalize_document(document) and notes == []
    with pytest.raises(ValidationError):
        design_file.parse({"kind": design_file.KIND, "version": 3, "document": {}})
    with pytest.raises(ValidationError):
        design_file.parse("not json")


def test_legacy_badge_design_files_are_accepted_as_a_format():
    legacy = {"kind": "yuyu-id-card-design", "version": 2, "settings": {
        "widthMm": 85.6, "heightMm": 53.98, "heading": "Maker Night", "showName": True, "showQr": True,
        "elementPositions": {"header": {"xMm": 4, "yMm": 4}, "name": {"xMm": 4, "yMm": 14}, "qr": {"xMm": 60, "yMm": 20}},
        "elementSizes": {"header": 40, "name": 40, "qr": 20}, "elementTextSizes": {"header": 10, "name": 12}}}
    document, notes = design_file.parse(legacy)
    clean = normalize_document(document)
    kinds = {layer["kind"] for layer in clean["front"]["layers"]}
    assert {"text", "data_field", "verify_qr"} <= kinds and notes


def test_foreign_assets_are_stripped_on_import():
    asset = str(uuid4())
    document = _doc([{**_text(), "id": str(uuid4())}, {"id": str(uuid4()), "kind": "image", "name": "i", "x_mm": 1,
                                                      "y_mm": 1, "w_mm": 10, "h_mm": 10, "asset_id": asset}])
    document["front"]["background"] = {"kind": "image", "asset_id": asset}
    notes = design_file.strip_foreign_assets(document, owned_ids=set())
    assert document["front"]["background"]["kind"] == "colour"
    assert all(layer["kind"] != "image" for layer in document["front"]["layers"]) and len(notes) == 2


def test_programme_number_pattern_tokens():
    from apps.id_programmes.numbering import formatted, prefix_from, validate_prefix
    assert formatted("STU", 2026, 1) == "STU-2026-0001"
    assert formatted("STU", 2026, 12345) == "STU-2026-12345"
    assert formatted("AB", 2027, 7, "{PREFIX}/{SEQ:2}") == "AB/07"
    assert prefix_from("Student ID card") == "SIC"
    with pytest.raises(ValidationError):
        validate_prefix("toolong7")


@pytest.mark.django_db
def test_normalising_is_idempotent_for_every_template():
    from apps.card_designs.default_templates import DEFAULT_FOR_DOMAIN, LABELS
    for key in LABELS:
        for domain in DEFAULT_FOR_DOMAIN:
            once = normalize_document(build(key, domain), check_contrast=False)
            assert normalize_document(once, check_contrast=False) == once
