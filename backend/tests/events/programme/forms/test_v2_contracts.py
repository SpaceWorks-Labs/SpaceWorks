"""Replay G's literal shared input bytes through the sole F validation engine."""
import json
from copy import deepcopy
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError as SchemaError
from rest_framework.exceptions import ValidationError

from apps.forms_schema.profile_fields import PROFILE_FIELDS, normalize_profile_value
from apps.forms_schema.submission import validate_submission
from apps.forms_schema.validation import validate_answers, validate_form_schema

FIXTURES = Path(__file__).parents[1] / "contracts" / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_registry_matches_every_frozen_descriptor():
    data = fixture("profile-fields-v3.json")
    assert set(PROFILE_FIELDS) == {item["field_key"] for item in data["descriptors"]}
    for expected in data["descriptors"]:
        item = PROFILE_FIELDS[expected["field_key"]]
        assert item.sensitive == expected["sensitive"]
        assert item.default_save == expected["default_save"]
        assert item.persistable == expected["persistable"]


def test_emergency_raw_canonical_and_explicit_sensitive_save():
    data = fixture("emergency-contact-v2.json")
    result = validate_submission(schema=data["schema"], payload={"answers": data["raw"], **data["false_save"]})
    assert result.snapshot["answers"] == [data["canonical"]]
    assert result.save_choices == {"emergency_contact": False}
    assert result.profile_values == {"emergency_contact": data["canonical"]["value"]}
    saved = validate_submission(schema=data["schema"], payload={"answers": data["raw"],
        "save_choices": {"emergency_contact": True}, "saved_detail_versions": {"emergency_contact": 0}})
    assert saved.save_choices["emergency_contact"] is True


@pytest.mark.parametrize("case", fixture("emergency-contact-v2.json")["invalid"], ids=lambda case: case["case"])
def test_emergency_nested_errors_match_frozen_bytes(case):
    schema = fixture("emergency-contact-v2.json")["schema"]
    with pytest.raises(ValidationError) as caught:
        validate_submission(schema=schema, payload={"answers": case["answers"]})
    assert caught.value.detail == case["error"]


def test_hidden_required_and_invalid_values_are_dropped_before_mapping():
    data = fixture("form-v2.json")
    payload = deepcopy(data["member_input"])
    payload["answers"]["diet_note"] = {"malformed": "hidden"}
    result = validate_submission(schema=data["schema"], payload=payload)
    assert result.omitted_question_ids == ("diet_note",)
    assert "dietary_needs" not in result.profile_values
    with pytest.raises(ValidationError, match="derivation_preparation_required"):
        _ = result.snapshot
    snapshot = result.snapshot_with_derivations({"age": 19})
    assert next(item for item in snapshot["answers"] if item["id"] == "age") == data["canonical_snapshot"]["answers"][-1]
    assert "2004-05-12" not in json.dumps(snapshot)
    assert '"value": 22' not in json.dumps(snapshot)
    payload["save_choices"]["dietary_needs"] = True
    with pytest.raises(ValidationError, match="invalid_save_choices"):
        validate_submission(schema=data["schema"], payload=payload)


def test_sensitive_fields_default_off_but_nonsensitive_requires_a_version():
    data = fixture("emergency-contact-v2.json")
    result = validate_submission(schema=data["schema"], payload={"answers": data["raw"]})
    assert result.save_choices == {"emergency_contact": False}
    data = fixture("form-v2.json")
    payload = deepcopy(data["member_input"])
    payload.pop("saved_detail_versions")
    with pytest.raises(ValidationError, match="saved_version_required"):
        validate_submission(schema=data["schema"], payload=payload)


@pytest.mark.parametrize("target", ["age", "unknown"])
def test_numeric_age_and_unknown_answers_are_refused(target):
    data = fixture("form-v2.json")
    payload = deepcopy(data["member_input"])
    payload["answers"][target] = 22
    with pytest.raises(ValidationError):
        validate_submission(schema=data["schema"], payload=payload)


@pytest.mark.parametrize("schema_change", [
    lambda s: s["questions"][0].update(show_if={"all": [{"field_id": "diet", "op": "eq", "value": "none"}]}),
    lambda s: s["questions"][3].update(bounds={"min": 18}),
    lambda s: s["questions"][3].update(profile_field_key="name"),
    lambda s: s["questions"][1].update(profile_field_key="dietary_needs"),
    lambda s: s["questions"][0].update(bounds={"min_length": 10, "max_length": 2}),
    lambda s: s["questions"][2].update(show_if={"any": [{"all": [{"any": [{"field_id": "diet", "op": "eq", "value": "none"}]}]}]}),
])
def test_invalid_schemas_reject_forward_references_bounds_and_mapping(schema_change):
    schema = fixture("form-v2.json")["schema"]
    schema_change(schema)
    with pytest.raises(SchemaError):
        validate_form_schema(schema)


def test_age_and_birth_date_never_control_show_if():
    schema = fixture("form-v2.json")["schema"]
    schema["questions"].append({"id": "later", "label": "Later", "type": "short_text", "required": False,
        "show_if": {"all": [{"field_id": "age", "op": "eq", "value": 18}]}})
    with pytest.raises(SchemaError, match="eligibility"):
        validate_form_schema(schema)


def test_v1_snapshot_and_error_paths_are_unchanged():
    schema = [{"id": "name", "label": "Name", "type": "short_text", "options": [], "required": True}]
    assert validate_answers(schema, {"name": " Person "}) == {"version": 1, "answers": [
        {"id": "name", "label": "Name", "type": "short_text", "value": "Person"}]}
    with pytest.raises(ValidationError) as caught:
        validate_answers(schema, {})
    assert "custom_answers" in caught.value.detail


def test_dob_no_future_or_invalid_dates_but_no_minimum_age():
    from datetime import date
    assert normalize_profile_value("date_of_birth", "2026-10-18", today=date(2026, 10, 18)) == "2026-10-18"
    for invalid in ("2026-02-29", "2026-10-19", "22"):
        with pytest.raises(ValueError):
            normalize_profile_value("date_of_birth", invalid, today=date(2026, 10, 18))
    with pytest.raises(ValueError):
        normalize_profile_value("age_at_event", 22)


def test_stale_form_and_event_date_have_frozen_conflict_status():
    from apps.forms_schema.submission import FormContextConflict
    data = fixture("form-v2.json")
    payload = deepcopy(data["member_input"])
    payload["form"]["revision"] -= 1
    with pytest.raises(FormContextConflict) as caught:
        validate_submission(schema=data["schema"], payload=payload)
    assert caught.value.status_code == 409 and caught.value.detail["code"] == "form_revision_changed"
    payload = deepcopy(data["member_input"])
    payload["derivations"]["age"]["reviewed_event_date_revision"] -= 1
    with pytest.raises(FormContextConflict) as caught:
        validate_submission(schema=data["schema"], payload=payload)
    assert caught.value.status_code == 409 and caught.value.detail["code"] == "event_date_changed"
