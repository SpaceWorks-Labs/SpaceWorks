"""Real P sources through ordinary event edits, close, notices and owner review."""
from datetime import timedelta

import pytest
from django.db import transaction

from apps.events.answer_derivations.lifecycle import lock_subject_locked, review_date_locked
from apps.events.answer_derivations.models import EventAnswerDerivation
from apps.events.contracts.subjects import SubjectKind
from apps.events.hackathons.admission_date_notices import eligible, register_date_notices
from apps.events.models import Event
from apps.events.services_event_details import update_event
from apps.events.services_lifecycle import complete
from apps.integrations.models_contract import NotificationEnvelope
from tests.events.collab_helpers import make_staff
from tests.events.programme.answer_derivations.conftest import age_world, create_subject, insert, prepare, locked

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("kind", list(SubjectKind))
def test_date_edit_marks_each_unlocked_subject_and_commits_source_notice(age_world, kind):
    owner, _, space, event = age_world
    manager = make_staff(space)
    row, subject = create_subject(age_world, kind)
    insert(age_world, subject, prepare(age_world, subject))
    register_date_notices()
    updated = update_event(event, actor=manager, starts_at=event.starts_at + timedelta(days=1))
    row.refresh_from_db()
    assert updated.event_date_revision == 8 and row.date_review_required
    source = EventAnswerDerivation.objects.get(event=event)
    # The source remains server-derived; changing a date never stores an age.
    assert source.event_date_revision == 7 and source.locked_at is None
    envelope = NotificationEnvelope.objects.get(source_kind="events.answer_date", recipient=owner)
    assert envelope.context == {"event_id": event.pk, "subject_kind": kind.value}
    assert eligible(envelope)
    with locked(age_world, subject) as locks:
        review_date_locked(actor_id=owner.pk, subject=subject, revision=8,
                           as_of_date=updated.starts_at.date(), locks=locks)
    assert not eligible(envelope)


def test_timezone_edit_marks_review_even_if_utc_timestamp_does_not_change(age_world):
    _, _, space, event = age_world
    manager = make_staff(space)
    row, subject = create_subject(age_world, SubjectKind.ROLE_ASSIGNMENT)
    insert(age_world, subject, prepare(age_world, subject))
    update_event(event, actor=manager, timezone_name="America/Los_Angeles")
    row.refresh_from_db()
    event.refresh_from_db()
    assert row.date_review_required and event.event_date_revision == 8


def test_locked_source_keeps_original_date_without_a_new_notice(age_world):
    owner, _, space, event = age_world
    row, subject = create_subject(age_world, SubjectKind.ROLE_ASSIGNMENT)
    insert(age_world, subject, prepare(age_world, subject))
    with locked(age_world, subject) as locks:
        lock_subject_locked(actor_id=owner.pk, subject=subject, locks=locks)
    update_event(event, actor=make_staff(space), starts_at=event.starts_at + timedelta(days=366),
                 ends_at=event.ends_at + timedelta(days=366))
    source = EventAnswerDerivation.objects.get(event=event)
    row.refresh_from_db()
    assert source.locked_at and source.event_date_revision == 7
    assert not row.date_review_required
    assert not NotificationEnvelope.objects.filter(source_kind="events.answer_date").exists()


def test_failed_edit_rolls_back_revision_review_and_notice_together(age_world, monkeypatch):
    _, _, space, event = age_world
    row, subject = create_subject(age_world, SubjectKind.REGISTRATION)
    insert(age_world, subject, prepare(age_world, subject))
    # Key preparation must precede any domain transaction, so the failure is injected
    # inside the edit itself: the notice enqueue runs after the revision and review flag.
    def abort(**kwargs):
        raise RuntimeError("abort")
    monkeypatch.setattr("apps.events.hackathons.admission_date_notices.enqueue_locked", abort)
    with pytest.raises(RuntimeError, match="abort"):
        update_event(event, actor=make_staff(space), starts_at=event.starts_at + timedelta(hours=1))
    row.refresh_from_db()
    event.refresh_from_db()
    assert event.event_date_revision == 7 and not row.date_review_required
    assert not NotificationEnvelope.objects.filter(source_kind="events.answer_date").exists()


def test_event_close_freezes_role_source_but_preserves_pending_review(age_world):
    _, _, space, event = age_world
    row, subject = create_subject(age_world, SubjectKind.ROLE_ASSIGNMENT)
    row.state = "applied"
    row.save(update_fields=["state"])
    insert(age_world, subject, prepare(age_world, subject))
    manager = make_staff(space)
    Event.objects.filter(pk=event.pk).update(status="published")
    update_event(event, actor=manager, starts_at=event.starts_at + timedelta(hours=1))
    complete(event, actor=manager)
    row.refresh_from_db()
    source = EventAnswerDerivation.objects.get(event=event)
    assert source.locked_at and source.event_date_revision == 8 and row.date_review_required
    event.refresh_from_db()
    assert event.status == "completed"
