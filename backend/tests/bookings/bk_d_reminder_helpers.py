from datetime import timedelta

from django.utils import timezone

from apps.integrations.models import EmailLog
from apps.operations.reminder_sweeper import run_reminder_sweep
from tests.bookings.bk_d_helpers import fixture, smtp


def legacy_backlog(monkeypatch):
    """Replay historical EmailLog backlog without changing the modern producer.

    These rows remain durable after the Phase-2 upgrade. Discovery/claim identity,
    legacy source snapshot validation and digest privacy still need coverage.
    Only the dispatcher is replaced with the historical public dispatch seam.
    """
    from dataclasses import replace
    from apps.bookings import reminders
    from apps.bookings.communication_recipients import recipient_account
    from apps.bookings.reminder_delivery import context_for, snapshot
    from apps.integrations.dispatch_outbox import dispatch_email
    from apps.integrations.email_templates import render
    from apps.integrations.notify import NotificationResult

    def dispatch(tenant, schedule, message, now, local_tz):
        row = reminders._eligible(tenant, schedule, timezone.now())
        account = recipient_account(tenant, row.member_id, "reminder") if row else None
        if account is None:
            return NotificationResult(False)
        values = render(tenant, "bookings", "requester", "reminder", context_for(row))
        log = dispatch_email(makerspace=tenant, recipient_id=account.pk, to_email=account.email,
            feature="bookings", stream="bookings", event="reminder", audience="requester",
            source_kind="bookings.booking", source_id=row.pk, source_metadata=snapshot(row, schedule),
            sync=True, **values)
        return NotificationResult(True, {"email": 1})

    monkeypatch.setattr(reminders, "BOOKING_REMINDER_SOURCE",
                        replace(reminders.BOOKING_REMINDER_SOURCE, dispatch=dispatch))


def sweep_and_deliver(**kwargs):
    """Current production sweep, then the real personal outbox worker."""
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.integrations.notification_tasks import deliver_envelope
    result = run_reminder_sweep(**kwargs)
    for pk in NotificationEnvelope.objects.filter(source_kind="bookings.reminder").values_list("pk", flat=True):
        deliver_envelope(pk)
    return result


def reminder(monkeypatch, *, mode="immediate"):
    legacy_backlog(monkeypatch)
    # Exercise real booking mutations but isolate their ordinary lifecycle mail
    # from the reminder outbox, SMTP counts and digest membership under test.
    monkeypatch.setattr("apps.bookings.notifications.notify_booking_status", lambda *args, **kwargs: None)
    world = fixture(monkeypatch)
    now = timezone.now()
    clock = [now]
    monkeypatch.setattr(timezone, "now", lambda: clock[0])
    due = now + timedelta(hours=1)
    send = smtp(monkeypatch)
    if mode == "quiet":
        monkeypatch.setattr("apps.integrations.quiet_hours.quiet_until", lambda tenant, channel, at: due if at < due else None)
        monkeypatch.setattr("apps.integrations.timing_dispatch.quiet_until", lambda tenant, channel, at: due if at < due else None)
    elif mode == "digest":
        monkeypatch.setattr("apps.integrations.digests.digest_due", lambda tenant, user, feature, at: due if at < due else None)
    result = run_reminder_sweep(now=now, source_keys=["bookings.booking"])
    log = EmailLog.objects.get(makerspace=world[0], event="reminder", source_kind="bookings.booking")
    return world, clock, due, send, log, result


def release(clock, due):
    clock[0] = due + timedelta(seconds=1)
    return run_reminder_sweep(now=clock[0], source_keys=["notifications.deferred"])


def cancel(booking, owner):
    from apps.bookings.services_transitions import cancel_booking
    return cancel_booking(booking, actor=owner, member_cancel=True)


def move(booking, owner):
    from apps.bookings.services_reschedule import reschedule_booking
    return reschedule_booking(booking, actor=owner, starts_at=booking.starts_at+timedelta(minutes=10),
                              ends_at=booking.ends_at+timedelta(minutes=10))
