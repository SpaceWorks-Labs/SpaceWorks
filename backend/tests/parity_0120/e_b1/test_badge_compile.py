"""E-B1: compile parity on the shared fixture (3 templates x 11 stocks x 3 flag sets) and layout rules."""
import pytest

from apps.card_designs import badge_compile, badge_format, stocks
from tests.parity_0120.e_b1.fixture_files import load

CASES = load("badge_compile_cases.json")["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_compile_matches_the_shared_fixture(case):
    settings = badge_format.normalize(case["input"], event_title="Spring Build Night", organisation_name="Tinkerspace")
    assert settings == case["settings"]
    assert badge_compile.compile_front(settings) == case["compiled"]


def test_every_compiled_layer_sits_on_the_card_and_the_qr_keeps_its_scan_minimum():
    for case in CASES:
        compiled = case["compiled"]
        width, height = compiled["page_width_mm"], compiled["page_height_mm"]
        assert len(compiled["layers"]) <= 40
        for layer in compiled["layers"]:
            assert -0.05 <= layer["x_mm"] and layer["x_mm"] + layer["w_mm"] <= width + 0.05
            assert -0.05 <= layer["y_mm"] and layer["y_mm"] + layer["h_mm"] <= height + 0.05
            if layer["kind"] == "checkin_qr":
                assert min(layer["w_mm"], layer["h_mm"]) >= stocks.qr_minimum_mm(compiled["stock"]) - 0.01


def test_six_by_four_is_a_stock_and_the_name_is_the_largest_text():
    assert stocks.dimensions("6x4") == (152.4, 101.6)
    compiled = badge_compile.compile_front(badge_format.normalize({"colorMode": "colour", "widthMm": 152.4, "heightMm": 101.6}))
    assert compiled["stock"] == "6x4"
    sizes = {layer["name"]: layer["font_size_pt"] for layer in compiled["layers"] if "font_size_pt" in layer}
    assert sizes["Name"] == max(sizes.values())


def test_same_settings_compile_to_byte_identical_layers_with_stable_ids():
    settings = badge_format.normalize({"colorMode": "colour"})
    assert badge_compile.compile_front(settings) == badge_compile.compile_front(settings)
