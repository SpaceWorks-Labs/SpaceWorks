"""EP-9: the approved MLH presets are valid, age-free, and usable as `optional_mlh_schema`."""
from django.urls import resolve

from apps.forms_schema.mlh_presets import mlh_presets
from apps.forms_schema.schema_v2 import validate_schema


def test_presets_are_valid_form_v2_schemas_with_stable_ids():
    presets = mlh_presets()
    assert [p["id"] for p in presets] == ["mlh-2026", "mlh-basics"]
    for preset in presets:
        assert validate_schema(preset["schema"])["schema_version"] == 2
        assert preset["schema"]["revision"] >= 1 and preset["label"]


def test_presets_carry_no_age_or_guardian_question():
    forbidden = {"date_of_birth", "age_at_event"}
    for preset in mlh_presets():
        assert not forbidden & {q["type"] for q in preset["schema"]["questions"]}
        assert not any("age" in q["id"].split("_") or "guardian" in q["id"] for q in preset["schema"]["questions"])


def test_each_call_returns_independent_copies():
    first = mlh_presets()
    first[0]["schema"]["questions"].clear()
    assert mlh_presets()[0]["schema"]["questions"]


def test_route_is_mounted_and_catalogued():
    from django.urls import reverse
    from apps.accounts.programme_route_catalog import BY_NAME
    name = "events-programme-admin-hackathon-mlh-presets"
    assert BY_NAME[name] == (("GET", "HEAD"), "event")
    assert resolve(reverse(name, kwargs={"pk": 7})).view_name == name
