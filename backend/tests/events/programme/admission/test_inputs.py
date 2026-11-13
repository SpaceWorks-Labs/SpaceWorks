"""A consumes G's exact admission/emergency bytes, without rewriting fixtures."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from rest_framework.exceptions import ValidationError
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.hackathons.admission_inputs import effective_contacts, typed_admission_input

FIXTURES = Path(__file__).parents[1] / "contracts" / "fixtures"


def admission_fixture():
    return json.loads((FIXTURES / "application-admission-v3.json").read_text())


def test_exact_top_level_inputs_preserve_opaque_waiver_and_compound():
    fixture = admission_fixture()
    data, selection = typed_admission_input(fixture["request"])
    assert selection.values["host_waiver_version"] == "host-2026-10"
    assert data["answers"]["emergency"] == fixture["canonical_snapshot"]["answers"][1]["value"]
    assert "invite_code" not in selection.draft_values()
    assert "promo_code" not in selection.draft_values()


@pytest.mark.parametrize("field", ["member", "actor", "name", "staff_registration", "collaborative", "amount", "currency", "validated"])
def test_authority_and_price_overrides_refused(field):
    body = admission_fixture()["request"]
    body[field] = "forged"
    with pytest.raises(ProgrammeError) as exc:
        typed_admission_input(body)
    assert exc.value.status_code == 400
    assert field in exc.value.detail["fields"]


@pytest.mark.parametrize("value", [None, {}, {"x": 1}])
def test_application_rejects_custom_answers_even_if_empty(value):
    body = admission_fixture()["request"]
    body["custom_answers"] = value
    with pytest.raises(ProgrammeError) as exc:
        typed_admission_input(body)
    assert exc.value.detail["code"] == "answer_field_conflict"


@pytest.mark.parametrize("field", ["invite_code", "promo_code"])
def test_codes_submit_only(field):
    body = admission_fixture()["request"]
    body.pop("promo_code" if field == "invite_code" else "invite_code")
    with pytest.raises(ProgrammeError) as exc:
        typed_admission_input(body, draft=True)
    assert exc.value.detail["code"] == "admission_code_submit_only"


@pytest.mark.parametrize("value", ["true", "false", 1, 0, None])
def test_waiver_acceptance_requires_literal_boolean(value):
    body = admission_fixture()["request"]
    body["host_waiver_accepted"] = value
    with pytest.raises(ProgrammeError) as exc:
        typed_admission_input(body)
    assert exc.value.detail["code"] == "invalid_admission_input"


def test_account_contacts_win_without_changing_account():
    body = admission_fixture()["request"]
    _, selection = typed_admission_input(body)
    actor = SimpleNamespace(email="Account@Example.test", phone="+919800000099")
    assert effective_contacts(actor, selection) == {"email": "account@example.test", "phone": actor.phone}
    assert actor.email == "Account@Example.test"


def test_fallback_contacts_required_separately_from_form_answers():
    body = admission_fixture()["request"]
    body.pop("email")
    body.pop("phone")
    _, selection = typed_admission_input(body)
    with pytest.raises(ProgrammeError) as exc:
        effective_contacts(SimpleNamespace(email="", phone=""), selection)
    assert exc.value.detail["code"] == "contact_required"
    assert set(exc.value.detail["fields"]) == {"phone", "email"}
