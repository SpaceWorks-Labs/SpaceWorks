import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.accounts.saved_details import prefill as provider
from apps.accounts.saved_details.errors import SavedDetailsError
from apps.accounts.saved_details.workflow import change_detail

pytestmark = pytest.mark.django_db(transaction=True)
FIXTURES = Path(__file__).parents[2] / "events/programme/contracts/fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text())


def install(owner, monkeypatch, questions, *, kind="application", form_id="hackathon-application"):
    context = provider.PrefillContext(owner_id=owner.pk, event_id=42, subject_kind=kind, form_id=form_id,
        form_revision=3, event_date_revision=7, as_of_date=date(2026, 12, 1), questions=tuple(questions))
    monkeypatch.setattr(provider, "_provider", SimpleNamespace(resolve=lambda **_: context))


def test_exact_bootstrap_prefill_with_zero_memberships_and_vault_rows(owner, monkeypatch):
    fixture = load("public-url-bootstrap-v4.json")
    install(owner, monkeypatch, fixture["context"]["application_form"]["questions"])
    assert provider.prefill(owner.pk, fixture["prefill_request"]) == fixture["prefill_response"]


def test_compound_prefill_uses_frozen_standard_key_not_question_label_or_id(owner, monkeypatch):
    fixture = load("emergency-contact-v2.json")
    value = fixture["raw"]["emergency"]
    for version in (0, 1):
        change_detail(owner.pk, "emergency_contact", {"operation_id": uuid4(), "expected_version": version, "value": value, "save_consent": True})
    install(owner, monkeypatch, fixture["schema"]["questions"])
    response = provider.prefill(owner.pk, {"context": {"event_id": 42, "makerspace_id": 9, "subject_kind": "application"},
        "form_id": "hackathon-application", "form_revision": 3, "event_date_revision": 7})
    for key, expected in fixture["prefill_round_trip"].items():
        assert response[key] == expected


@pytest.mark.parametrize("kind", ["registration", "application", "role_assignment"])
def test_cross_journey_prefill_is_owner_only_and_dob_save_default_stays_false(owner, monkeypatch, kind):
    for key, value in (("institution", "Maker College"), ("date_of_birth", "2004-05-12")):
        change_detail(owner.pk, key, {"operation_id": uuid4(), "expected_version": 0, "value": value, "save_consent": True})
    form = load("form-v2.json")["schema"]
    install(owner, monkeypatch, [form["questions"][0], form["questions"][-1]], kind=kind, form_id=form["form_id"])
    body = {"context": {"event_id": 42, "makerspace_id": 9, "subject_kind": kind}, "form_id": form["form_id"], "form_revision": 3, "event_date_revision": 7}
    response = provider.prefill(owner.pk, body)
    assert response["values"] == {"institution": "Maker College"}
    assert response["save_defaults"]["date_of_birth"] is False
    assert response["derivation_inputs"]["age"]["value"] == 22
    assert "2004-05-12" not in str(response)
    with pytest.raises(SavedDetailsError) as error:
        provider.prefill(owner.pk, {**body, "event_date_revision": 8})
    assert error.value.status_code == 409 and type(error.value.detail["event_date_revision"]) is int
