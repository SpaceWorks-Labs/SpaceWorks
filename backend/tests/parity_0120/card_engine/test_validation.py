"""Card Studio: the v3 document validates the new properties, and v2 documents upgrade without changing their sides."""
import json
from pathlib import Path

import pytest
from rest_framework.exceptions import ValidationError

from apps.card_designs import stocks
from apps.card_designs.layout import normalize_document, upgrade

from .conftest import document, layer, uid

FIXTURES = Path(__import__("apps.card_designs", fromlist=["x"]).__file__).parent / "fixtures"
COMPAT = json.loads((FIXTURES / "studio_compat_cases.json").read_text(encoding="utf-8"))["cases"]


def clean(layers, **top):
    return normalize_document(document(layers, **top), check_contrast=False)


def refused(layers, **top):
    with pytest.raises(ValidationError):
        clean(layers, **top)


@pytest.mark.parametrize("case", COMPAT, ids=lambda case: case["id"])
def test_a_v2_document_keeps_its_sides_under_v3(case):
    old = case["input"]
    assert old["version"] == 2 and upgrade(old)["version"] == 3
    new = normalize_document(old, check_contrast=False)
    assert new["version"] == 3
    assert new["front"] == case["expected"]["front"] and new["back"] == case["expected"]["back"]
    assert "guides" not in new and "kind" not in new  # sparse: nothing is added to an old document


def test_background_gradient_takes_six_stops_and_a_radial_centre():
    stops = [{"colour": "#000000", "at": index * 20} for index in range(6)]
    out = clean([], background={"kind": "gradient", "type": "radial", "angle_deg": 0, "cx_pct": 30, "radius_pct": 80,
                                "stops": stops})
    background = out["front"]["background"]
    assert len(background["stops"]) == 6 and background["cx_pct"] == 30 and background["radius_pct"] == 80
    assert "cy_pct" not in background  # a default is omitted
    refused([], background={"kind": "gradient", "type": "linear", "stops": stops + [{"colour": "#FFFFFF", "at": 100}]})


def test_background_image_fit_zoom_focal_blur_and_darken_limits():
    asset = uid()
    base = {"kind": "image", "asset_id": asset}
    out = normalize_document(document([], background={**base, "fit": "stretch", "zoom": 2, "focal_x_pct": 20,
                                                      "blur_mm": 3, "dim_pct": 70}), asset_colours={asset: "#808080"},
                             check_contrast=False)
    image = out["front"]["background"]
    assert (image["fit"], image["zoom"], image["focal_x_pct"], image["blur_mm"], image["dim_pct"]) == ("stretch", 2, 20, 3, 70)
    for bad in ({"fit": "tile"}, {"zoom": 9}, {"blur_mm": 20}, {"dim_pct": 95}, {"focal_x_pct": 120}):
        with pytest.raises(ValidationError):
            normalize_document(document([], background={**base, **bad}), asset_colours={asset: "#808080"},
                               check_contrast=False)


def test_overlay_gradient_needs_alpha_stops_and_lives_on_the_side():
    doc = document([])
    doc["front"]["overlay"] = {"type": "linear", "angle_deg": 180, "stops": [
        {"colour": "#000000", "at": 0, "alpha_pct": 0}, {"colour": "#000000", "at": 100, "alpha_pct": 60}]}
    assert normalize_document(doc, check_contrast=False)["front"]["overlay"]["stops"][1]["alpha_pct"] == 60
    doc["front"]["overlay"]["stops"][1]["alpha_pct"] = 140
    with pytest.raises(ValidationError):
        normalize_document(doc, check_contrast=False)


def test_guides_are_validated_and_sparse():
    assert "guides" not in clean([])
    out = clean([], guides={"safe_mm": 4, "punch_slot": {"shape": "slot", "x_mm": 21, "y_mm": 3, "w_mm": 12, "h_mm": 3},
                            "rulers": [{"axis": "x", "at_mm": 10}]})
    assert out["guides"]["punch_slot"]["w_mm"] == 12 and out["guides"]["rulers"] == [{"axis": "x", "at_mm": 10.0}]
    for bad in ({"punch_slot": {"x_mm": 50, "y_mm": 3, "w_mm": 12, "h_mm": 3}}, {"bleed_mm": 9},
                {"rulers": [{"axis": "z", "at_mm": 1}]}, {"mystery": 1}):
        with pytest.raises(ValidationError):
            clean([], guides=bad)


def test_groups_are_created_for_legacy_ids_and_dropped_below_two_members():
    group = uid()
    out = clean([layer("shape", 1, 1, 5, 5, shape="rect", fill="#006E63", group=group),
                 layer("shape", 8, 1, 5, 5, shape="rect", fill="#006E63", group=group),
                 layer("shape", 15, 1, 5, 5, shape="rect", fill="#006E63", group=uid())])
    assert [row["id"] for row in out["front"]["groups"]] == [group]
    assert out["front"]["layers"][2]["group"] is None


def test_rich_text_spans_stroke_shadow_highlight_underline_translations():
    spans = [{"text": "{{first_name}} ", "font_family": "Gilroy Light", "font_weight": 300},
             {"text": "{{last_name}}", "font_family": "Gilroy ExtraBold", "font_weight": 800, "size_scale": 1.2}]
    text = layer("text", 2, 2, 48, 12, text="", spans=spans, stroke={"colour": "#000000", "width_pt": 1},
                 shadow={"blur_mm": 5}, highlight={"colour": "#DFFF8F"}, underline={"colour": "#006E63"},
                 translations={"ml": "{{name}}"}, decorative=True)
    row = clean([text])["front"]["layers"][0]
    assert row["text"] == "{{first_name}} {{last_name}}" and len(row["spans"]) == 2
    assert row["shadow"]["blur_mm"] == 2.0  # text shadows blur up to 2 mm
    assert row["highlight"]["pad_x_mm"] == 1.5 and row["underline"]["thickness_pt"] == 1.5 and row["decorative"] is True
    for bad in ({"spans": []}, {"spans": [{"text": "x", "font_family": "Comic Sans"}]},
                {"spans": [{"text": "x", "font_family": "Gilroy Light", "font_weight": 700}]},
                {"spans": [{"text": "{{nope}}"}]}, {"stroke": {"colour": "#000000", "width_pt": 20}},
                {"translations": {"EN-us!": "x"}}):
        refused([layer("text", 2, 2, 48, 12, text="x", **bad)])
    refused([layer("data_field", 2, 2, 48, 12, field="name", spans=spans)])


def test_a_span_colour_below_contrast_is_flagged_on_publish():
    low = layer("text", 2, 2, 48, 12, text="", spans=[{"text": "Hi", "colour": "#F0F0F0"}], colour="#142C2A")
    with pytest.raises(ValidationError):
        normalize_document(document([low]), check_contrast=True)


def test_decorative_lettering_is_exempt_from_the_contrast_check():
    faint = layer("text", 0, 5, 54, 30, text="TINKER", colour="#F0F0F0", font_size_pt=60, decorative=True)
    normalize_document(document([faint]), check_contrast=True)


def test_shapes_images_and_photos_take_the_studio_properties():
    asset = uid()
    gradient = {"type": "linear", "angle_deg": 90, "stops": [{"colour": "#006E63", "at": 0, "alpha_pct": 100},
                                                            {"colour": "#DFFF8F", "at": 100, "alpha_pct": 50}]}
    layers = [layer("shape", 1, 1 + 12 * index, 10, 10, shape=name, fill="#006E63", fill_gradient=gradient, shadow={})
              for index, name in enumerate(("rect", "rounded", "circle", "ellipse", "arch"))]
    layers.append(layer("image", 20, 1, 10, 10, asset_id=asset, fit="stretch", mask="arch", zoom=2, focal_y_pct=10,
                        flip_x=True, outline={}, shadow={"blur_mm": 2}))
    layers.append(layer("photo", 20, 20, 20, 30, shape="arch", variant="cutout", zoom=1.5, outline={"width_mm": 1.2},
                        shadow={}))
    out = normalize_document(document(layers), asset_colours={asset: "#808080"}, check_contrast=False)["front"]["layers"]
    assert [row["shape"] for row in out[:5]] == ["rect", "rounded", "circle", "ellipse", "arch"]
    assert out[5]["mask"] == "arch" and out[5]["outline"]["width_mm"] == 0.8 and out[5]["flip_x"] is True
    assert out[6]["variant"] == "cutout" and out[6]["outline"]["colour"] == "#FFFFFF" and out[6]["zoom"] == 1.5
    for bad in (layer("photo", 1, 1, 10, 10, variant="holographic"), layer("photo", 1, 1, 10, 10, shape="star"),
                layer("shape", 1, 1, 5, 5, shape="blob", fill="#006E63"),
                layer("image", 1, 1, 5, 5, asset_id=asset, mask="hex")):
        with pytest.raises(ValidationError):
            normalize_document(document([bad]), asset_colours={asset: "#808080"}, check_contrast=False)


def test_the_photo_variant_vocabulary_is_original_cutout_auto():
    for variant in ("original", "cutout", "auto"):
        clean([layer("photo", 1, 1, 10, 10, variant=variant)])


def test_certificate_kind_uses_paper_stocks_and_custom_up_to_420():
    out = clean([], kind="certificate", stock="a4-landscape")
    assert out["kind"] == "certificate" and out["front"]["page_width_mm"] == 297.0
    assert clean([], kind="certificate", stock="custom", page_width_mm=420, page_height_mm=300)["front"]["page_height_mm"] == 300.0
    refused([], kind="certificate", stock="cr80-landscape")
    refused([], kind="card", stock="custom", page_width_mm=420, page_height_mm=300)
    refused([], kind="poster")


def test_stock_presets_cover_card_badge_and_certificate_families():
    rows = {row["key"]: row for row in stocks.presets()}
    assert {"cr80-portrait", "cr80-landscape", "a6-portrait", "badge-90x130", "a4-landscape", "letter-portrait",
            "a5-portrait"} <= set(rows)
    assert rows["a4-landscape"]["family"] == "certificate" and rows["cr80-portrait"]["orientation"] == "portrait"


def test_first_name_and_last_name_tags_split_the_name():
    from apps.card_designs.data_fields import merge, valid_tag
    assert valid_tag("first_name") and valid_tag("last_name")
    assert merge("{{first_name}}|{{last_name}}", {"name": "Fathima Shenza Khan"}) == "Fathima|Shenza Khan"
    assert merge("{{last_name}}", {"name": "Madonna"}) == ""
