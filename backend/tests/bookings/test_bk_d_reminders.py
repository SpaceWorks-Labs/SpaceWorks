"""BR1-4 upgrade backlog: old EmailLog source rows, deferred releases and built digests.

New envelopes are covered by test_bk_d_reminder_review and test_reminder_envelopes.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.bookings.models import Booking, BookableSpace
from apps.integrations.delivery_content import content
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.models import EmailLog
from apps.operations.models import ReminderSchedule
from apps.operations.reminder_sweeper import run_reminder_sweep
from tests.bookings.bk_d_helpers import reserve
from tests.bookings.bk_d_reminder_helpers import cancel, move, release, reminder

pytestmark = pytest.mark.django_db(transaction=True)


def test_account_only_reminder_real_discovery_and_delivery_once(monkeypatch):
    world, clock, due, send, log, result = reminder(monkeypatch)
    tenant, _, _, _, _, user, booking = world
    assert "membership" not in tenant.enabled_modules and "events" not in tenant.enabled_modules
    assert send.call_count == 1 and log.status == "sent" and result["dispatched"] == 1
    assert log.recipient_id == user.pk and log.source_id == booking.pk
    assert content(log).to_email == user.email
    assert log.source_metadata["calendar_sequence"] == booking.calendar_sequence
    assert str(booking.public_token) not in str(log.source_metadata)
    assert run_reminder_sweep(now=clock[0], source_keys=["bookings.booking"])["dispatched"] == 0
    assert send.call_count == 1


# "notifications" is not a stale-source mutation: the inbox module is optional for
# account-owned booking channels (reconciliation lane W; pinned by
# tests/bookings/test_reconciliation_envelopes.py).
@pytest.mark.parametrize("mutation", ["cancel", "move", "passed", "owner", "unverified", "module", "requester", "offset", "preference", "membership"])
@pytest.mark.parametrize("phase", ["quiet", "retry", "digest", "assembled"])
def test_stale_booking_never_sends_after_enqueue_or_summary(monkeypatch, mutation, phase):
    world, clock, due, send, log, result = reminder(monkeypatch, mode="digest" if phase in {"digest", "assembled"} else "quiet")
    tenant, manager, sender, resource, grant, user, booking = world
    assert log.status == "pending" and not send.called
    if phase == "assembled":
        release(clock, due)
        log = EmailLog.objects.get(makerspace=tenant, source_kind="notification_digest")
        assert log.source_metadata["entries"]
    elif phase == "retry":
        send.side_effect = RuntimeError("transport unavailable")
        release(clock, due)
        log.refresh_from_db()
        assert log.status == "failed" and send.call_count == 1
        send.reset_mock(); send.side_effect = None
    if mutation == "cancel":
        cancel(booking, user)
    elif mutation == "move":
        move(booking, user)
    elif mutation == "passed":
        clock[0] = booking.starts_at + timedelta(seconds=1)
    elif mutation == "owner":
        Booking.objects.filter(pk=booking.pk).update(member=sender)
    elif mutation == "unverified":
        User.objects.filter(pk=user.pk).update(email_verified_at=None)
    elif mutation in {"module", "notifications"}:
        tenant.enabled_modules.remove("bookings" if mutation == "module" else "notifications"); tenant.save()
    elif mutation == "requester":
        resource.requester_notifications_enabled = False; resource.save()
    elif mutation == "offset":
        tenant.booking_reminder_lead_hours = [2]; tenant.save()
    elif mutation == "preference":
        from apps.notifications.models_inbox import MemberNotificationPreference
        MemberNotificationPreference.objects.create(makerspace=tenant, user=user, feature="bookings", channel="email", enabled=False)
        tenant.enabled_features += ["notifications.member_preferences"]; tenant.save()
    else:
        from apps.makerspaces.models import MakerspaceMembership
        MakerspaceMembership.objects.create(makerspace=tenant, user=user, receives_notifications=False, role="custom", assigned_role=tenant.roles.get(slug="member"))
    if phase in {"quiet", "digest"}:
        clock[0] = max(clock[0], due + timedelta(seconds=1))
        run_reminder_sweep(now=clock[0], source_keys=["notifications.deferred"])
    else:
        _deliver(log)
    assert not send.called
    log.refresh_from_db()
    assert log.status == "skipped"
    if phase == "digest":
        assert not EmailLog.objects.filter(makerspace=tenant, source_kind="notification_digest").exists()


def test_mixed_assembled_digest_rebuilds_on_retry_and_keeps_only_current_entries(monkeypatch):
    world, clock, due, send, stale, result = reminder(monkeypatch, mode="digest")
    tenant, _, _, resource, _, user, booking = world
    other_resource = BookableSpace.objects.create(makerspace=tenant, name="Surviving resource", approval_mode="instant")
    other = reserve(other_resource, user, booking.starts_at + timedelta(minutes=20))
    run_reminder_sweep(now=clock[0], source_keys=["bookings.booking"])
    release(clock, due)
    summary = EmailLog.objects.get(makerspace=tenant, source_kind="notification_digest")
    assert len(summary.source_metadata["entries"]) == 2
    assert set(summary.source_metadata["entries"]) == set(EmailLog.objects.filter(
        makerspace=tenant, source_kind="bookings.booking").values_list("pk", flat=True))
    send.side_effect = RuntimeError("temporary transport error")
    _deliver(summary)
    assert summary.status == "failed"
    cancel(booking, user)
    send.reset_mock(); send.side_effect = None
    _deliver(summary)
    assert summary.status == "sent" and send.call_count == 1
    assert "Surviving resource" in content(summary).text_body
    assert resource.name not in content(summary).text_body


@pytest.mark.parametrize("phase", ["quiet", "digest", "retry"])
def test_unchanged_occurrence_survives_every_delivery_path(monkeypatch, phase):
    world, clock, due, send, log, result = reminder(monkeypatch, mode="digest" if phase == "digest" else "quiet")
    if phase == "retry":
        send.side_effect = RuntimeError("temporary SMTP failure")
    release(clock, due)
    if phase == "digest":
        log = EmailLog.objects.get(makerspace=world[0], source_kind="notification_digest")
        _deliver(log)
    elif phase == "retry":
        log.refresh_from_db(); assert log.status == "failed"
        send.side_effect = None
        _deliver(log)
    log.refresh_from_db()
    assert log.status == "sent"


def test_new_occurrence_never_reuses_previous_claim_even_when_start_returns(monkeypatch):
    world, clock, due, send, old, result = reminder(monkeypatch, mode="quiet")
    tenant, _, _, _, _, user, booking = world
    moved = move(booking, user)
    run_reminder_sweep(now=clock[0], source_keys=["bookings.booking"])
    from apps.bookings.services_reschedule import reschedule_booking
    reschedule_booking(moved, actor=user, starts_at=booking.starts_at, ends_at=booking.ends_at)
    run_reminder_sweep(now=clock[0], source_keys=["bookings.booking"])
    assert ReminderSchedule.objects.filter(makerspace=tenant, source="bookings.booking").count() == 3
    logs = EmailLog.objects.filter(makerspace=tenant, source_kind="bookings.booking")
    assert logs.count() == 3
    release(clock, due)
    assert send.call_count == 1
    assert logs.filter(status="sent").count() == 1 and logs.filter(status="skipped").count() == 2


def test_legacy_sourceless_booking_reminders_fail_closed(monkeypatch):
    world, clock, due, send, log, result = reminder(monkeypatch, mode="quiet")
    log.source_kind = ""; log.save(update_fields=["source_kind"])
    release(clock, due)
    assert not send.called
    log.refresh_from_db(); assert log.status == "skipped"


@pytest.mark.parametrize("key", ["makerspace_id", "space_id", "booking_id", "recipient_id", "calendar_sequence", "ends_at"])
def test_forged_or_mismatched_source_snapshot_skips(monkeypatch, key):
    world, clock, due, send, log, result = reminder(monkeypatch, mode="quiet")
    value = log.source_metadata[key]
    log.source_metadata[key] = value+1 if type(value) is int else "2099-01-01T00:00:00+00:00"
    log.save(update_fields=["source_metadata"])
    release(clock, due)
    assert not send.called
    log.refresh_from_db(); assert log.status == "skipped"


def test_legacy_completed_initial_occurrence_claim_is_not_resent_on_upgrade(monkeypatch):
    world, clock, due, send, log, result = reminder(monkeypatch)
    from apps.operations.reminder_members import occurrence_subject
    booking = world[-1]
    # The receipt came from real discovery and SMTP. Re-express its old-version
    # subject, without inventing a delivery or changing the committed claim state.
    ReminderSchedule.objects.filter(makerspace=world[0], source="bookings.booking").update(
        subject=occurrence_subject(booking.pk, booking.starts_at))
    assert run_reminder_sweep(now=clock[0], source_keys=["bookings.booking"])["dispatched"] == 0
    assert send.call_count == 1


def test_copied_booking_contact_never_becomes_reminder_recipient(monkeypatch):
    world, clock, due, send, log, result = reminder(monkeypatch, mode="quiet")
    Booking.objects.filter(pk=world[-1].pk).update(email="different-account@example.test")
    release(clock, due)
    assert send.call_count == 1 and send.call_args.args[0].to == [world[-2].email]
