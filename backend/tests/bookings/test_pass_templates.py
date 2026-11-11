from copy import deepcopy

import pytest
from rest_framework.exceptions import ValidationError

from apps.bookings.pass_templates import DEFAULT_PASS_TEMPLATE, normalize_pass_template
from apps.bookings.serializers_passes import BookingPassTemplateSerializer


@pytest.mark.parametrize("field", ["custom:purpose", "answers", "custom_answers", "note", "email", "phone", "qr_value", "checkin_token", "public_token", "location"])
def test_forbidden_binding_refuses_serializer_and_stored_template(field):
    template = deepcopy(DEFAULT_PASS_TEMPLATE)
    template["elements"][0]["field"] = field
    assert not BookingPassTemplateSerializer(data=template).is_valid()
    with pytest.raises(ValidationError):
        normalize_pass_template(template)


@pytest.mark.parametrize("change", [
    {"fields": ["custom:purpose"]}, {"include_qr": True}, {"version": 1},
    {"version": True}, {"artwork": "foreign-key"}, {"grid_mm": float("nan")},
    {"card_width_mm": float("inf")}, {"paper_size": "unbounded"},
    {"card_width_mm": 150, "card_height_mm": 120, "margin_mm": 40},
    {"elements": []}, {"elements": [{"field": "name", "text": "Secret"}]},
])
def test_hostile_geometry_and_legacy_properties_refuse(change):
    with pytest.raises(ValidationError):
        normalize_pass_template({**deepcopy(DEFAULT_PASS_TEMPLATE), **change})


def test_default_is_independent_and_reference_is_optional():
    a = normalize_pass_template({})
    a["elements"].pop()
    b = normalize_pass_template({})
    assert len(b["elements"]) == 4
    assert len(normalize_pass_template(a)["elements"]) == 3
    a["elements"][0]["x_mm"] = 89
    with pytest.raises(ValidationError):
        normalize_pass_template(a)


def test_duplicate_binding_refuses():
    template = deepcopy(DEFAULT_PASS_TEMPLATE)
    template["elements"][1]["field"] = "name"
    with pytest.raises(ValidationError):
        normalize_pass_template(template)
