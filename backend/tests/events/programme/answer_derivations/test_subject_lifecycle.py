"""Real-DB owner/scoping/retention tests, including roles without registrations."""

import json
from dataclasses import replace
from datetime import date, timedelta

import pytest
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.events.answer_derivations.errors import DerivationError
from apps.events.answer_derivations.lifecycle import (
    date_changed_locked, lock_subject_locked, prepare_reopen, reopen_subject_locked,
    review_date_locked,
)
from apps.events.answer_derivations.models import EventAnswerDerivation
from apps.events.answer_derivations.serialization import owner_export, project_owner
from apps.events.answer_derivations.subjects import binding_for, require_owner
from apps.events.answer_derivations.workflow import (
    erase_owner_drafts_locked, insert_prepared_locked, purge_event_sources_locked,
)
from apps.events.contracts.subjects import SubjectKind
from apps.events.models_event import Event
from apps.events.models_registration import EventRegistration

from .conftest import create_subject, insert, locked, prepare

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize(("kind", "role"), [
    (SubjectKind.REGISTRATION, "mentor"), (SubjectKind.APPLICATION, "mentor"),
    (SubjectKind.ROLE_ASSIGNMENT, "volunteer"), (SubjectKind.ROLE_ASSIGNMENT, "mentor"),
])
def test_owner_source_date_review_lock_export_and_event_purge(age_world, kind, role):
    owner, foreign, _, event = age_world
    source, subject = create_subject(age_world, kind, role=role)
    canonical = insert(age_world, subject, prepare(age_world, subject))
    assert canonical == [{"id": "age", "type": "age_at_event", "derivation_id": canonical[0]["derivation_id"]}]
    row = EventAnswerDerivation.objects.get(pk=canonical[0]["derivation_id"])
    assert "2004-05-12" not in row.source_dob_envelope
    if kind == SubjectKind.ROLE_ASSIGNMENT:
        assert not EventRegistration.objects.filter(event=event).exists()
        source.state = "applied"
        source.save(update_fields=["state"])
    with pytest.raises(NotFound):
        owner_export(actor_id=foreign.pk, subject=subject)
    # G increments the single event revision and then calls the P hook.
    # Move both ends: an event may never end before it starts (DB check constraint).
    Event.objects.filter(pk=event.pk).update(starts_at=event.starts_at + timedelta(days=366),
        ends_at=event.ends_at + timedelta(days=366), event_date_revision=8)
    # G's event edit prepares tenant keys before its locks; the date notice it emits is
    # encrypted under them.
    from apps.encryption.preparation import prepare_tenants
    with prepare_tenants([event.makerspace_id]), locked(age_world, subject) as locks:
        assert date_changed_locked(event_id=event.pk, actor_id=owner.pk, locks=locks) == (owner.pk,)
    assert project_owner(actor_id=owner.pk, subject=subject, question_id="age")["value"] == 23
    source.refresh_from_db()
    assert source.date_review_required
    with pytest.raises(DerivationError, match="Owner date review"):
        with locked(age_world, subject) as locks:
            lock_subject_locked(actor_id=owner.pk, subject=subject, locks=locks)
    # Close freezes the new date, leaving review pending. Subsequent schedule
    # changes cannot shift that evidence or turn closure into approval.
    with locked(age_world, subject) as locks:
        lock_subject_locked(actor_id=owner.pk, subject=subject, locks=locks, closing=True)
    source.refresh_from_db()
    assert source.date_review_required
    Event.objects.filter(pk=event.pk).update(starts_at=event.starts_at + timedelta(days=732),
        ends_at=event.ends_at + timedelta(days=732), event_date_revision=9)
    with locked(age_world, subject) as locks:
        review_date_locked(actor_id=owner.pk, subject=subject, revision=8, as_of_date=date(2027, 12, 2), locks=locks)
    projection = project_owner(actor_id=owner.pk, subject=subject, question_id="age")
    assert projection["as_of_date"] == "2027-12-02" and projection["value"] == 23 and projection["locked"]
    exported = owner_export(actor_id=owner.pk, subject=subject)[0]
    assert exported["source_date_of_birth"] == "2004-05-12" and exported["subject_kind"] == kind.value
    source.refresh_from_db()
    assert not source.date_review_required
    if kind == SubjectKind.ROLE_ASSIGNMENT:
        assert not EventRegistration.objects.filter(event=event).exists()
    # Locked DOB sources are retained except inside a purge, which runs under the
    # scoped immutable-delete GUC like every tenant/event purge.
    from django.db import connection
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
        purge_event_sources_locked(event_id=event.pk, actor_id=owner.pk)
    assert not EventAnswerDerivation.objects.filter(event=event).exists()


def test_foreign_event_and_member_splices_are_refused(age_world):
    _, foreign, _, _ = age_world
    row, binding = create_subject(age_world, SubjectKind.ROLE_ASSIGNMENT)
    for subject in (replace(binding, owner_member_id=foreign.pk), replace(binding, event_id=binding.event_id + 999)):
        with pytest.raises(NotFound):
            require_owner(subject.owner_member_id, subject)
    assert row.member_id == binding.owner_member_id


def test_insert_is_ciphertext_only_and_checks_hash_expiry_and_owner(age_world, monkeypatch):
    owner, foreign, _, _ = age_world
    _, subject = create_subject(age_world, SubjectKind.ROLE_ASSIGNMENT)
    prepared = prepare(age_world, subject)
    # A cache miss under locks must not trigger a broker call.
    def forbidden(*args, **kwargs):
        raise AssertionError("Key broker/decryption called under event locks")
    monkeypatch.setattr("apps.encryption.services.unwrap_dek", forbidden)
    monkeypatch.setattr("apps.encryption.services.get_dek", forbidden)
    with locked(age_world, subject) as locks:
        with pytest.raises(NotFound):
            insert_prepared_locked(prepared, actor_id=foreign.pk, subject=subject, locks=locks,
                                   form_sha256="a" * 64, canonical_answer_sha256="b" * 64)
        with pytest.raises(DerivationError) as bad_hash:
            insert_prepared_locked(prepared, actor_id=owner.pk, subject=subject, locks=locks,
                                   form_sha256="c" * 64, canonical_answer_sha256="b" * 64)
        assert bad_hash.value.detail["code"] == "form_revision_changed"
        with pytest.raises(DerivationError) as expired:
            insert_prepared_locked(replace(prepared, expires_at=timezone.now() - timedelta(seconds=1)), actor_id=owner.pk,
                                   subject=subject, locks=locks, form_sha256="a" * 64, canonical_answer_sha256="b" * 64)
        assert expired.value.detail["code"] == "save_preparation_expired"
    assert not EventAnswerDerivation.objects.filter(event_id=subject.event_id).exists()
    insert(age_world, subject, prepared)


def test_reopen_appends_encrypted_history_and_preserves_locked_source(age_world, monkeypatch):
    owner = age_world[0]
    _, subject = create_subject(age_world, SubjectKind.ROLE_ASSIGNMENT)
    insert(age_world, subject, prepare(age_world, subject))
    with locked(age_world, subject) as locks:
        lock_subject_locked(actor_id=owner.pk, subject=subject, locks=locks)
    monkeypatch.setattr("apps.events.event_authority.require", lambda *args: None)
    prepared = prepare_reopen(actor_id=owner.pk, subject=subject, reason="Correct an answer with its owner")
    with locked(age_world, subject) as locks:
        reopen_subject_locked(prepared, actor_id=owner.pk, subject=subject, locks=locks)
    insert(age_world, subject, prepare(age_world, subject, dob="2003-05-12"))
    row = EventAnswerDerivation.objects.get(**{"role_assignment_id": subject.subject_id})
    stored_history = json.dumps(row.source_history)
    assert "2004-05-12" not in stored_history and "Correct an answer" not in stored_history
    exported = owner_export(actor_id=owner.pk, subject=subject)[0]
    assert exported["source_date_of_birth"] == "2003-05-12"
    assert exported["source_history"][0]["source_date_of_birth"] == "2004-05-12"


def test_database_three_subject_check_and_partial_uniqueness(age_world):
    _, subject = create_subject(age_world, SubjectKind.ROLE_ASSIGNMENT)
    reg, _ = create_subject(age_world, SubjectKind.REGISTRATION)
    insert(age_world, subject, prepare(age_world, subject))
    source = EventAnswerDerivation.objects.get(role_assignment_id=subject.subject_id)
    base = {name: getattr(source, name) for name in (
        "event_id", "role_assignment_id", "question_id", "source_dob_envelope", "event_date_revision", "as_of_date",
    )}
    for extra in ({}, {"registration_id": reg.pk}, {"role_assignment_id": None}):
        with pytest.raises(IntegrityError), transaction.atomic():
            # Bypass the Python boundary intentionally to prove the database CHECK
            # and partial unique constraints protect non-ORM write paths too.
            models.Model.save(EventAnswerDerivation(**{**base, **extra}), force_insert=True)


def test_account_erasure_removes_only_unsubmitted_draft_sources(age_world):
    owner = age_world[0]
    _, draft = create_subject(age_world, SubjectKind.ROLE_ASSIGNMENT, role="volunteer")
    _, retained = create_subject(age_world, SubjectKind.ROLE_ASSIGNMENT, role="mentor")
    insert(age_world, draft, prepare(age_world, draft))
    insert(age_world, retained, prepare(age_world, retained))
    with locked(age_world, retained) as locks:
        lock_subject_locked(actor_id=owner.pk, subject=retained, locks=locks)
    with locked(age_world, draft) as locks:
        assert erase_owner_drafts_locked(owner_member_id=owner.pk, event_id=draft.event_id,
                                        actor_id=owner.pk, locks=locks) == 1
    assert not EventAnswerDerivation.objects.filter(role_assignment_id=draft.subject_id).exists()
    assert owner_export(actor_id=owner.pk, subject=retained)[0]["source_date_of_birth"] == "2004-05-12"
