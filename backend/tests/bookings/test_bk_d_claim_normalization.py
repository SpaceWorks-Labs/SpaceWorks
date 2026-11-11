"""Legacy schedules must survive claim/discovery batch-order differences."""

from datetime import timedelta

import pytest

from apps.bookings.reminder_delivery import identity
from apps.bookings.reminders import normalize_booking_claim
from apps.integrations.models import EmailLog
from apps.operations.models import ReminderSchedule
from apps.operations.reminder_members import occurrence_subject
from apps.operations.reminder_services import claim_reminders, complete_reminder, schedule_reminders
from tests.bookings.bk_d_reminder_helpers import sweep_and_deliver as run_reminder_sweep
from apps.integrations.models_contract import NotificationEnvelope
from tests.bookings.bk_d_helpers import reserve
from tests.bookings.test_bk_d_reminder_review import SOURCE, _world

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("approved", [False, True])
@pytest.mark.parametrize("replacement", [False, True])
def test_claim_upgrades_legacy_booking_outside_discovery_batch(monkeypatch, approved, replacement):
    tenant, owner, later, clock, send = _world(monkeypatch, approved=approved)
    tenant.booking_reminder_lead_hours = [24, 2]
    tenant.save(update_fields=["booking_reminder_lead_hours"])
    # This booking occupies discovery's starts_at-ordered batch. Its 24-hour
    # step is genuinely sent first; the two-hour step becomes due below.
    resource = later.space
    resource.approval_mode = "instant"
    resource.save(update_fields=["approval_mode"])
    earlier = reserve(resource, owner, clock[0] + timedelta(hours=3))
    assert run_reminder_sweep(now=clock[0], limit=1, source_keys=[SOURCE])["dispatched"] == 1
    assert NotificationEnvelope.objects.get(makerspace=tenant, source_kind="bookings.reminder").source_id == str(earlier.pk)
    legacy = schedule_reminders(
        makerspace=tenant, source=SOURCE, subject=occurrence_subject(later.pk, later.starts_at),
        kind="starts", due_at=later.starts_at, offsets=(-86400, -7200),
    )
    if replacement:
        schedule_reminders(makerspace=tenant, source=SOURCE, subject=identity(later),
                           kind="starts", due_at=later.starts_at, offsets=(-86400, -7200))
    clock[0] += timedelta(hours=2)
    send.reset_mock()
    # Claims order by remind_at: later's legacy 24-hour step precedes earlier's
    # two-hour step even though discovery cannot reach the later booking.
    assert run_reminder_sweep(now=clock[0], limit=1, source_keys=[SOURCE]) == {
        "dispatched": 1, "skipped": 0, "failed": 0,
    }
    assert send.call_count == 1
    log = NotificationEnvelope.objects.get(makerspace=tenant, source_kind="bookings.reminder", source_id=str(later.pk))
    assert log.deliveries.get(channel="email").state == "sent" and log.revision == str(later.calendar_sequence)
    assert not ReminderSchedule.objects.filter(pk=legacy[0].pk).exists()
    assert ReminderSchedule.objects.get(
        makerspace=tenant, source=SOURCE, subject=identity(later), offset_seconds=-86400,
    ).state == "completed"
    for _ in range(4):
        assert run_reminder_sweep(now=clock[0], limit=1, source_keys=[SOURCE])["failed"] == 0
    assert send.call_count == 2  # earlier's later step, with no duplicate of later
    assert NotificationEnvelope.objects.filter(makerspace=tenant, source_kind="bookings.reminder", source_id=str(later.pk)).count() == 1


@pytest.mark.parametrize("state", ["pending", "claimed", "completed", "failed"])
def test_claim_normalization_deduplicates_and_preserves_replacement_fences(monkeypatch, state):
    tenant, owner, booking, clock, send = _world(monkeypatch)
    canonical, = schedule_reminders(
        makerspace=tenant, source=SOURCE, subject=identity(booking), kind="starts",
        due_at=booking.starts_at, offsets=(-86400,),
    )
    if state != "pending":
        claimed, = claim_reminders(makerspace=tenant, source=SOURCE, now=clock[0])
        if state != "claimed":
            assert complete_reminder(makerspace=tenant, reminder_id=claimed.pk,
                                     claim_token=claimed.claim_token, now=clock[0], failed=state == "failed")
    canonical.refresh_from_db()
    fence = (canonical.state, canonical.claim_token, canonical.claimed_at, canonical.completed_at)
    legacy, = schedule_reminders(
        makerspace=tenant, source=SOURCE, subject=occurrence_subject(booking.pk, booking.starts_at),
        kind="starts", due_at=booking.starts_at, offsets=(-86400,),
    )
    claims = claim_reminders(makerspace=tenant, source=SOURCE, now=clock[0],
                            normalize_claim=normalize_booking_claim)
    assert not ReminderSchedule.objects.filter(pk=legacy.pk).exists()
    canonical.refresh_from_db()
    if state == "pending":
        assert len(claims) == 1 and claims[0].pk == canonical.pk
        assert canonical.state == "claimed" and canonical.claim_token == claims[0].claim_token
    else:
        assert claims == ()
        assert (canonical.state, canonical.claim_token, canonical.claimed_at, canonical.completed_at) == fence
    assert not send.called


def test_normalization_failure_rolls_back_legacy_replacement_and_claim(monkeypatch):
    tenant, owner, booking, clock, send = _world(monkeypatch)
    legacy, = schedule_reminders(
        makerspace=tenant, source=SOURCE, subject=occurrence_subject(booking.pk, booking.starts_at),
        kind="starts", due_at=booking.starts_at, offsets=(-86400,),
    )

    def fail_after_upgrade(makerspace, schedule):
        current = normalize_booking_claim(makerspace, schedule)
        assert current.pk != legacy.pk
        raise RuntimeError("interrupted before claim")

    with pytest.raises(RuntimeError, match="interrupted before claim"):
        claim_reminders(makerspace=tenant, source=SOURCE, now=clock[0], normalize_claim=fail_after_upgrade)
    legacy.refresh_from_db()
    assert legacy.state == "pending" and legacy.claim_token is None
    assert not ReminderSchedule.objects.filter(makerspace=tenant, source=SOURCE, subject=identity(booking)).exists()
    assert run_reminder_sweep(now=clock[0], source_keys=[SOURCE])["dispatched"] == 1
    assert send.call_count == 1
