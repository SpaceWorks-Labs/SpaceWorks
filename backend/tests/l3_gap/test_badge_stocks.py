"""M9 / G13: the event badge designer accepts A6 landscape and a custom size (40-300 mm, 0.1 mm
steps); the six frozen stocks keep their packaged default designs."""
import json
from pathlib import Path

import pytest
from rest_framework.exceptions import ValidationError

from apps.events.certificates.badge_designs import validate_design
from apps.events.certificates.layout import DESIGN_STOCK_CHOICES, STOCKS

FIXTURES = Path(__file__).resolve().parents[1] / "events" / "programme" / "contracts" / "fixtures"


def _badge(width, height):
    document = json.loads((FIXTURES / "template-seed-v2.json").read_text())["badge_seed"]["document"]
    scale_x, scale_y = width / document["page_width_mm"], height / document["page_height_mm"]
    for layer in document["layers"]:
        layer["x_mm"], layer["width_mm"] = round(layer["x_mm"] * scale_x, 2), round(layer["width_mm"] * scale_x, 2)
        layer["y_mm"], layer["height_mm"] = round(layer["y_mm"] * scale_y, 2), round(layer["height_mm"] * scale_y, 2)
        if layer["type"] == "event_credential_qr":
            layer["width_mm"] = layer["height_mm"] = max(20, min(layer["width_mm"], layer["height_mm"]))
            # The 20 mm QR floor can overhang a small page once x is scaled, so keep it inside the page.
            layer["x_mm"] = round(min(layer["x_mm"], width - layer["width_mm"]), 2)
            layer["y_mm"] = round(min(layer["y_mm"], height - layer["height_mm"]), 2)
    return {**document, "page_width_mm": width, "page_height_mm": height}


def test_the_frozen_six_are_unchanged_and_the_design_choices_add_two():
    assert set(STOCKS) == {"a6-portrait", "4x6", "3x4", "4x3", "cr80-portrait", "cr80-landscape"}
    assert set(DESIGN_STOCK_CHOICES) == set(STOCKS) | {"a6-landscape", "custom"}


def test_a6_landscape_must_match_its_size():
    assert validate_design(_badge(148, 105), "a6-landscape")["page_width_mm"] == 148
    with pytest.raises(ValidationError):
        validate_design(_badge(105, 148), "a6-landscape")


@pytest.mark.parametrize("size", [(40, 40), (120.5, 80.3), (300, 300)])
def test_custom_sizes_inside_the_range(size):
    assert validate_design(_badge(*size), "custom")["page_height_mm"] == size[1]


@pytest.mark.parametrize("size", [(39.9, 60), (60, 300.1), (60.25, 60)])
def test_custom_sizes_outside_the_range_or_off_step_are_refused(size):
    with pytest.raises(ValidationError):
        validate_design(_badge(*size), "custom")


def test_unknown_stock_is_refused():
    with pytest.raises(ValidationError):
        validate_design(_badge(85.6, 53.98), "postcard")


@pytest.mark.django_db
def test_seed_list_is_empty_for_stocks_without_packaged_designs():
    from tests.l3_gap.helpers import live_event
    from tests.l3_local.helpers import client, manager
    space, event = live_event("gap-bs-seeds", features=())
    api = client(manager(space))
    response = api.get(f"/api/v1/admin/events/{event.pk}/badges/designs/?stock=a6-landscape&theme=light")
    assert response.status_code == 200 and response.json()["results"] == []
    assert api.get(f"/api/v1/admin/events/{event.pk}/badges/designs/?stock=postcard").status_code == 400
