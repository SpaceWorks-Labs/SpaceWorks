"""Fail closed before mutation and expose source DOB only to its owner."""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from apps.events.answer_derivations import crypto, serialization
from apps.events.answer_derivations.dates import event_date, require_review, review_target
from apps.events.answer_derivations.errors import DerivationError
from apps.events.answer_derivations.models import EventAnswerDerivation
from apps.events.answer_derivations.preparation import source_dob
from apps.events.contracts.subjects import AnswerSubject, SubjectKind


def test_fixture_all_three_subjects_are_in_actual_constraints():
    fixture = json.loads((Path(__file__).parents[1] / "contracts/fixtures/profile-role-age-v3.json").read_text())
    fields = {f.name for f in EventAnswerDerivation._meta.fields}
    assert set(fixture["subjects"]) <= fields
    assert "age" not in fields and "age_at_event" not in fields
    constraints = EventAnswerDerivation._meta.constraints
    uniques = [c for c in constraints if hasattr(c, "fields")]
    assert {tuple(c.fields) for c in uniques} == {
        (kind, "question_id") for kind in fixture["subjects"]
    }
    check = next(c for c in constraints if c.name == "event_derivation_one_subject")
    assert all(kind in repr(check.condition) for kind in fixture["subjects"])


def test_local_start_and_frozen_date_review():
    event = SimpleNamespace(starts_at=datetime(2026, 12, 1, 1, tzinfo=UTC), timezone_name="America/Los_Angeles", event_date_revision=8)
    assert event_date(event) == date(2026, 11, 30)
    frozen = SimpleNamespace(locked_at=datetime.now(UTC), event_date_revision=7, as_of_date=date(2026, 10, 1))
    assert review_target(event, [frozen]) == (7, date(2026, 10, 1))
    require_review(7, "2026-10-01", review_target(event, [frozen]))
    with pytest.raises(DerivationError) as caught:
        require_review(7, "2026-10-01", review_target(event))
    assert caught.value.status_code == 409
    assert caught.value.detail["code"] == "event_date_changed"
    assert type(caught.value.detail["event_date_revision"]) is int
    assert "date_of_birth" not in caught.value.detail


def test_saved_source_is_resolved_with_exact_actor_and_vault_version():
    loader = Mock(return_value="2004-05-12")
    result = source_dob({"kind": "saved_detail", "field_key": "date_of_birth", "version": 3}, actor_id=17, saved_dob_loader=loader)
    assert result == date(2004, 5, 12)
    loader.assert_called_once_with(actor_id=17, version=3)
    with pytest.raises(DerivationError):
        source_dob({"kind": "saved_detail", "field_key": "date_of_birth", "version": 3, "owner_id": 18}, actor_id=17, saved_dob_loader=loader)


@pytest.mark.parametrize("source", [22, {"kind": "age", "value": 22}, {"kind": "inline_dob", "date_of_birth": "2004-05-12", "value": 22}])
def test_numeric_age_is_never_a_source(source):
    with pytest.raises(DerivationError):
        source_dob(source, actor_id=17, saved_dob_loader=None)


def test_encryption_flag_off_fails_before_key_loader(settings, monkeypatch):
    settings.PII_ENCRYPTION_ENABLED = False
    monkeypatch.setattr(crypto, "require_preparation_boundary", lambda: None)
    keys = Mock()
    monkeypatch.setattr(crypto.MakerspaceEncryptionKey, "objects", keys)
    with pytest.raises(DerivationError) as caught:
        crypto.prepared_key(9)
    assert caught.value.status_code == 503
    assert caught.value.detail["code"] == "event_pii_unavailable"
    keys.get.assert_not_called()


def test_projection_omits_source_dob_and_key_data(monkeypatch):
    event = SimpleNamespace(starts_at=datetime(2026, 12, 1, tzinfo=UTC), timezone_name="UTC")
    row = SimpleNamespace(question_id="age", locked_at=None, event=event, source_dob_envelope="secret")
    monkeypatch.setattr(serialization, "decrypt_source", lambda row: "2004-05-12")
    assert serialization._project(row) == {
        "id": "age", "type": "age_at_event", "value": 22,
        "as_of_date": "2026-12-01", "locked": False,
    }
    row.locked_at, row.as_of_date = datetime.now(UTC), date(2025, 12, 1)
    assert serialization._project(row)["value"] == 21


def test_owner_is_required_before_any_source_is_loaded(monkeypatch):
    from rest_framework.exceptions import NotFound

    def deny(*args):
        raise NotFound()

    subject = AnswerSubject(event_id=42, owner_member_id=17, kind=SubjectKind.ROLE_ASSIGNMENT, subject_id=81)
    monkeypatch.setattr(serialization, "require_owner", deny)
    read = Mock()
    monkeypatch.setattr(serialization, "_source", read)
    with pytest.raises(NotFound):
        serialization.project_owner(actor_id=18, subject=subject, question_id="age")
    read.assert_not_called()
