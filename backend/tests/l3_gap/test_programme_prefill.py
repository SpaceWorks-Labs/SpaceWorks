"""P24 / G14: opt-in Saved-details prefill on the programme join page, non-sensitive keys only."""
import pytest
from rest_framework.exceptions import ValidationError

from apps.id_programmes import prefill, questions, services
from tests.l3_gap.helpers import programme
from tests.l3_local.helpers import client, member

pytestmark = pytest.mark.django_db

SCHEMA = [
    {"key": "college", "label": "College", "type": "text", "saved_details_key": "institution"},
    {"key": "size", "label": "T-shirt", "type": "choice", "options": ["S", "M", "L"], "saved_details_key": "shirt_size"},
    {"key": "note", "label": "Anything else", "type": "text"},
]


def _base(row):
    return f"/api/v1/public/organizations/{row.organization.slug}/id-programmes/{row.slug}"


def test_only_non_sensitive_single_value_keys_may_prefill():
    assert prefill.allowed("institution") and prefill.allowed("phone")
    for key in ("date_of_birth", "emergency_contact", "dietary_needs", "accessibility_needs", "resume", "skills",
                "age_at_event", "nonsense", ""):
        assert not prefill.allowed(key)
    with pytest.raises(ValidationError):
        questions.validate_schema([{"key": "dob", "label": "Birthday", "type": "text",
                                    "saved_details_key": "date_of_birth"}])
    clean = questions.validate_schema(SCHEMA)
    assert clean[0]["saved_details_key"] == "institution" and clean[2]["saved_details_key"] == ""


def test_public_page_says_which_questions_can_prefill_but_never_the_key():
    space, _org, sm, row = programme("gap-pf-public")
    services.update(sm, row, {"form_schema": SCHEMA})
    body = client(member(space, "gap-pf-viewer")[0]).get(_base(row)).json()
    assert [question["prefill"] for question in body["questions"]] == [True, True, False]
    assert "saved_details_key" not in str(body)


def test_prefill_returns_only_mapped_matching_values_and_is_not_stored(monkeypatch):
    space, _org, sm, row = programme("gap-pf-values")
    services.update(sm, row, {"form_schema": SCHEMA})
    asked = {}

    def fake(user, keys):
        asked["keys"] = set(keys)
        return {"institution": "  College of Engineering  ", "shirt_size": "XXL"}

    monkeypatch.setattr(prefill, "saved_values", fake)
    user, _m = member(space, "gap-pf-joiner")
    response = client(user).get(f"{_base(row)}/prefill")
    assert response.status_code == 200
    assert response.json() == {"values": {"college": "College of Engineering"}}
    assert response["Cache-Control"] == "private, no-store"
    assert asked["keys"] == {"institution", "shirt_size"}
    assert not row.cards.exists()


def test_prefill_needs_a_signed_in_account():
    _space, _org, sm, row = programme("gap-pf-anon")
    from rest_framework.test import APIClient
    assert APIClient().get(f"{_base(row)}/prefill").status_code in (401, 403)


def test_no_mapped_questions_means_no_vault_read(monkeypatch):
    space, _org, _sm, row = programme("gap-pf-none")
    monkeypatch.setattr(prefill, "saved_values", lambda user, keys: pytest.fail("vault read"))
    user, _m = member(space, "gap-pf-nobody")
    assert client(user).get(f"{_base(row)}/prefill").json() == {"values": {}}
