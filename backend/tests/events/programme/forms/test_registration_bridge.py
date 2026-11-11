"""Actual A/G/F shared bytes, including the old error location and admission keys."""
import json
from copy import deepcopy
from pathlib import Path
from uuid import UUID
import pytest
from rest_framework.exceptions import ValidationError
from apps.events.contracts.subjects import AnswerSubject, SubjectKind
from apps.events.registration_form_adapter import validate_registration_form
from apps.forms_schema.registration import validate_registration_member_input
from apps.forms_schema.submission import validate_submission

FIXTURES = Path(__file__).parents[1] / "contracts" / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def subject(kind=SubjectKind.REGISTRATION):
    return AnswerSubject(event_id=42, owner_member_id=17, kind=kind,
        creation_operation_id=UUID("33333333-3333-4333-8333-333333333333"))


@pytest.mark.parametrize("index", [0, 1])
def test_both_frozen_ordinary_spellings_replay_through_real_f_validator(index):
    data = fixture("application-admission-v3.json")
    payload = data["ordinary_branches"][index]["request"]
    calls = []
    def validate(**kwargs):
        calls.append(deepcopy(kwargs["payload"]))
        return validate_registration_member_input(**kwargs)
    value = validate_registration_form(payload, schema=data["setup"]["form"], subject=subject(), validator=validate)
    result = value.require_subject(subject())
    assert result.snapshot == data["canonical_snapshot"]
    assert len(calls) == 1
    for key in ("ticket_type_id", "host_waiver_id", "host_waiver_version", "host_waiver_accepted",
                "email", "phone", "invite_code", "promo_code"):
        assert calls[0][key] == payload[key]


@pytest.mark.parametrize("field", ["answers", "custom_answers"])
def test_ordinary_nested_compound_error_keeps_requested_field(field):
    data = fixture("emergency-contact-v2.json")
    payload = {field: {"emergency": {"name": "Contact", "relationship": "Friend", "phone": "bad"}},
        "form": {key: data["schema"][key] for key in ("schema_version", "form_id", "revision")}}
    with pytest.raises(ValidationError) as caught:
        validate_registration_form(payload, schema=data["schema"], subject=subject(),
            validator=validate_registration_member_input)
    assert caught.value.detail == {field: {"emergency": {"phone": ["Enter a valid phone."]}}}


def test_new_application_keeps_fields_envelope_for_identical_compound_error():
    data = fixture("emergency-contact-v2.json")
    with pytest.raises(ValidationError) as caught:
        validate_registration_form({"answers": {"emergency": []}, "form": {
            key: data["schema"][key] for key in ("schema_version", "form_id", "revision")}}, schema=data["schema"],
            subject=subject(SubjectKind.APPLICATION), validator=validate_submission, application=True)
    assert caught.value.detail["code"] == "invalid_answer"
    assert caught.value.detail["fields"] == {"emergency": {"name": ["Expected an object."]}}
