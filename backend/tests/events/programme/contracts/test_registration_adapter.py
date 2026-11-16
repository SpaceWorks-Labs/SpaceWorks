"""A/G/F boundary tests; domain lanes add real provider replay of these bytes."""

from copy import deepcopy
import json
from pathlib import Path
from uuid import UUID

import pytest
from rest_framework.exceptions import ValidationError

from apps.events.contracts.subjects import AnswerSubject, SubjectKind
from apps.events.registration_form_adapter import (
    ValidatedRegistrationForm, normalize_registration_input, validate_registration_form,
)

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def subject(kind=SubjectKind.REGISTRATION):
    return AnswerSubject(event_id=42, owner_member_id=17, kind=kind,
                         creation_operation_id=UUID("33333333-3333-4333-8333-333333333333"))


@pytest.mark.parametrize("index", [0, 1])
def test_both_ordinary_spellings_validate_once_without_losing_admission(index):
    data = fixture("application-admission-v3.json")
    payload = data["ordinary_branches"][index]["request"]
    original = deepcopy(payload)
    calls = []

    def validator(*, schema, payload, subject):
        calls.append((schema, payload, subject))
        assert payload["answers"] == data["request"]["answers"]
        for key in ("ticket_type_id", "host_waiver_id", "host_waiver_version",
                    "host_waiver_accepted", "email", "phone", "invite_code", "promo_code"):
            assert payload[key] == data["request"][key]
        return data["canonical_snapshot"]

    schema = data["setup"]["form"]
    result = validate_registration_form(payload, schema=schema, subject=subject(),
                                        validator=validator)
    assert len(calls) == 1
    assert result.require_subject(subject()) == data["canonical_snapshot"]
    assert payload == original
    with pytest.raises(ValueError):
        result.require_subject(subject(SubjectKind.APPLICATION))


@pytest.mark.parametrize("left,right", [({}, {}), (None, None), ({}, None), (None, {})])
def test_presence_of_both_keys_always_refuses(left, right):
    with pytest.raises(ValidationError) as error:
        normalize_registration_input({"answers": left, "custom_answers": right}, schema_version=2)
    assert error.value.detail["code"] == "answer_field_conflict"


@pytest.mark.parametrize("raw", [{}, None])
def test_new_application_route_refuses_legacy_spelling_even_if_empty(raw):
    with pytest.raises(ValidationError):
        normalize_registration_input({"custom_answers": raw}, schema_version=2, application=True)


def test_client_cannot_supply_canonical_snapshot_or_validated_flag():
    snapshot = fixture("application-admission-v3.json")["canonical_snapshot"]
    with pytest.raises(ValidationError):
        normalize_registration_input({"answers": snapshot}, schema_version=2)
    with pytest.raises(TypeError):
        ValidatedRegistrationForm(subject=subject(), answer_field="answers",
                                  validated=snapshot, _factory=True)


def test_legacy_errors_preserve_compound_subfield_path():
    data = fixture("application-admission-v3.json")

    def validator(**kwargs):
        raise ValidationError({"answers": {"emergency": {"phone": ["Enter a valid phone."]}}})

    with pytest.raises(ValidationError) as error:
        validate_registration_form(data["ordinary_branches"][1]["request"],
                                   schema=data["setup"]["form"], subject=subject(), validator=validator)
    assert error.value.detail == {"custom_answers": {"emergency": {"phone": ["Enter a valid phone."]}}}


def test_v1_still_passes_raw_map_to_validator_once():
    raw = {"school": "Maker College"}
    calls = []

    def validator(*, payload, **kwargs):
        calls.append(payload["answers"])
        return {"version": 1, "answers": []}

    result = validate_registration_form({"custom_answers": raw}, schema=[],
                                        subject=subject(), validator=validator)
    assert calls == [raw]
    assert result.require_subject(subject())["version"] == 1


def test_new_application_uses_answers_even_with_a_legacy_form_descriptor():
    result = normalize_registration_input({"answers": {"school": "Maker College"}},
                                          schema_version=1, application=True)
    assert result.answer_field == "answers"


@pytest.mark.parametrize("kind", list(SubjectKind))
def test_exactly_three_subject_kinds_accept_role_without_registration(kind):
    assert subject(kind).kind == kind
    with pytest.raises(ValueError):
        AnswerSubject(event_id=42, owner_member_id=17, kind=kind, subject_id=81,
                      creation_operation_id=UUID("33333333-3333-4333-8333-333333333333"))
