"""Current reminder discovery reserves intent; real workers enforce every live gate."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.bookings.models import Booking
from apps.integrations.models import EmailLog
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_delivery import ensure_deliveries
from apps.integrations.notification_tasks import deliver_envelope
from apps.operations.reminder_sweeper import run_reminder_sweep
from tests.bookings.bk_d_helpers import fixture, smtp
from tests.bookings.bk_d_reminder_helpers import cancel, move

pytestmark = pytest.mark.django_db(transaction=True)


def queued(monkeypatch):
    monkeypatch.setattr("apps.bookings.notifications.notify_booking_status", lambda *args, **kwargs: None)
    world = fixture(monkeypatch)
    clock = [timezone.now()]
    monkeypatch.setattr(timezone, "now", lambda: clock[0])
    send = smtp(monkeypatch)
    result = run_reminder_sweep(now=clock[0], source_keys=["bookings.booking"])
    envelope = NotificationEnvelope.objects.get(makerspace=world[0], source_kind="bookings.reminder")
    assert result["dispatched"] == 1 and not send.called
    assert not EmailLog.objects.filter(makerspace=world[0], event="reminder").exists()
    return world, clock, send, envelope


def as_digest(tenant, owner, envelope, due):
    from apps.notifications.models_preferences import NotificationPreference

    tenant.enabled_features = sorted(set(tenant.enabled_features) | {"notifications.digests"})
    tenant.save(update_fields=["enabled_features"])
    NotificationPreference.objects.create(makerspace=tenant, user=owner, category="bookings", channels=["email"])
    envelope.timing_policy, envelope.available_at = "digest", due
    envelope.save(update_fields=["timing_policy", "available_at"])


def test_current_reminder_reserves_owner_intent_then_delivers_once(monkeypatch):
    world, clock, send, envelope = queued(monkeypatch)
    tenant, _, _, _, _, owner, booking = world
    assert envelope.recipient_id == owner.pk and envelope.source_id == str(booking.pk)
    assert envelope.revision == str(booking.calendar_sequence)
    # Source proof plus the reviewed scalar messaging projection (lane W): never a
    # contact, note, answer or bearer token.
    context = dict(envelope.context)
    assert (context.pop("booking_id"), context.pop("offset_seconds")) == (booking.pk, -86400)
    assert set(context) == {"booking.id", "booking.status", "booking.when", "makerspace.name"}
    assert (context["booking.id"], context["booking.status"]) == (booking.pk, "confirmed")
    assert context["makerspace.name"] == tenant.name
    for secret in (booking.public_token, booking.checkin_token, owner.email, booking.email):
        assert str(secret) not in str(envelope.context)
    deliver_envelope(envelope.pk)
    deliver_envelope(envelope.pk)
    assert send.call_count == 1 and send.call_args.args[0].to == [owner.email]
    assert envelope.deliveries.get(channel="email").state == "sent"
    assert run_reminder_sweep(now=clock[0], source_keys=["bookings.booking"])["dispatched"] == 0
    assert NotificationEnvelope.objects.filter(source_kind="bookings.reminder").count() == 1


def test_reminder_import_does_not_retain_a_temporary_template_renderer(monkeypatch):
    from importlib import reload
    from apps.bookings import reminder_envelopes

    try:
        # A lazily imported module must not capture another test's temporary
        # renderer and replace resource/time content in every later reminder.
        with monkeypatch.context() as patch:
            patch.setattr("apps.integrations.email_templates.render", lambda *_: {
                "subject": "Update", "text_body": "Body", "html_body": "",
            })
            reload(reminder_envelopes)
        world, _, send, envelope = queued(monkeypatch)
        deliver_envelope(envelope.pk)
        assert send.call_count == 1
        assert world[3].name in send.call_args.args[0].body
    finally:
        reload(reminder_envelopes)


# The optional inbox ("notifications" module) is deliberately not a reminder gate.
@pytest.mark.parametrize("phase", ["quiet", "retry", "digest", "assembled"])
@pytest.mark.parametrize("mutation", ["cancel", "move", "passed", "owner", "unverified", "module",
    "requester", "offset", "preference", "membership", "booking_id", "revision", "offset_type", "unknown_source"])
def test_current_reminder_rechecks_source_and_privacy_every_delivery_path(monkeypatch, phase, mutation):
    world, clock, send, envelope = queued(monkeypatch)
    tenant, _, sender, resource, _, owner, booking = world
    due = clock[0] + timedelta(hours=1)
    if phase in {"digest", "assembled"}:
        as_digest(tenant, owner, envelope, due)
    elif phase == "quiet":
        monkeypatch.setattr("apps.integrations.quiet_hours.quiet_until",
            lambda tenant, channel, at: due if at < due else None)
    ensure_deliveries(envelope)
    target = envelope
    if phase == "retry":
        send.side_effect = RuntimeError("temporary transport failure")
        deliver_envelope(envelope.pk)
        leg = envelope.deliveries.get(channel="email")
        assert leg.state == "retrying" and send.call_count == 1
        due = leg.next_attempt_at
        send.reset_mock(); send.side_effect = None
    elif phase == "assembled":
        clock[0] = due + timedelta(seconds=1)
        deliver_envelope(envelope.pk)
        target = NotificationEnvelope.objects.get(makerspace=tenant, source_kind="notification.digest")
        assert target.context["envelope_ids"] == [envelope.pk]
        ensure_deliveries(target)
    elif phase == "quiet":
        deliver_envelope(envelope.pk)
        assert not send.called
    if mutation == "cancel": cancel(booking, owner)
    elif mutation == "move": move(booking, owner)
    elif mutation == "passed": clock[0] = booking.starts_at + timedelta(seconds=1)
    elif mutation == "owner": Booking.objects.filter(pk=booking.pk).update(member=sender)
    elif mutation == "unverified": User.objects.filter(pk=owner.pk).update(email="unproven@example.test", email_verified_at=None)
    elif mutation in {"module", "notifications"}:
        tenant.enabled_modules.remove("bookings" if mutation == "module" else "notifications"); tenant.save()
    elif mutation == "requester": resource.requester_notifications_enabled = False; resource.save()
    elif mutation == "offset": tenant.booking_reminder_lead_hours = [2]; tenant.save()
    elif mutation == "preference":
        from apps.notifications.models_inbox import MemberNotificationPreference
        tenant.enabled_features += ["notifications.member_preferences"]; tenant.save()
        MemberNotificationPreference.objects.create(makerspace=tenant, user=owner, feature="bookings", channel="email", enabled=False)
    elif mutation == "membership":
        from apps.makerspaces.models import MakerspaceMembership
        MakerspaceMembership.objects.create(makerspace=tenant, user=owner, receives_notifications=False, role="custom", assigned_role=tenant.roles.get(slug="member"))
    else:
        if mutation == "booking_id": envelope.context["booking_id"] += 1
        elif mutation == "offset_type": envelope.context["offset_seconds"] = "-86400"
        elif mutation == "revision": envelope.revision = str(booking.calendar_sequence + 1)
        else: envelope.source_kind = "unknown.booking.reminder"
        envelope.save(update_fields=["context", "revision", "source_kind"])
    clock[0] = max(clock[0], due + timedelta(seconds=1))
    deliver_envelope(target.pk)
    if phase == "digest":
        summary = NotificationEnvelope.objects.get(makerspace=tenant, source_kind="notification.digest")
        deliver_envelope(summary.pk)
    assert not send.called
    assert not EmailLog.objects.filter(makerspace=tenant, event__in=["reminder", "daily_digest"], status="sent").exists()
    if phase != "digest":
        assert target.deliveries.get(channel="email").state == "skipped"


@pytest.mark.parametrize("phase", ["quiet", "retry", "digest", "assembled"])
def test_current_unchanged_reminder_survives_every_delivery_path(monkeypatch, phase):
    world, clock, send, envelope = queued(monkeypatch)
    tenant, _, _, resource, _, owner, booking = world
    due = clock[0] + timedelta(hours=1)
    if phase in {"digest", "assembled"}:
        as_digest(tenant, owner, envelope, due)
    elif phase == "quiet":
        monkeypatch.setattr("apps.integrations.quiet_hours.quiet_until",
            lambda tenant, channel, at: due if at < due else None)
    ensure_deliveries(envelope)
    if phase == "retry":
        send.side_effect = RuntimeError("temporary transport failure")
        deliver_envelope(envelope.pk)
        leg = envelope.deliveries.get(channel="email")
        assert leg.state == "retrying" and leg.attempt_count == 1
        assert send.call_count == 1 and send.call_args.args[0].to == [owner.email]
        assert EmailLog.objects.filter(makerspace=tenant, event="reminder", status="failed").count() == 1
        due = leg.next_attempt_at
        send.side_effect = None
    else:
        deliver_envelope(envelope.pk)
        assert not send.called
        assert not NotificationEnvelope.objects.filter(makerspace=tenant, source_kind="notification.digest").exists()
    clock[0] = due + timedelta(seconds=1)
    deliver_envelope(envelope.pk)
    target = envelope
    if phase in {"digest", "assembled"}:
        target = NotificationEnvelope.objects.get(makerspace=tenant, source_kind="notification.digest")
        assert target.context["envelope_ids"] == [envelope.pk]
        assert not send.called
        if phase == "assembled":
            ensure_deliveries(target)
            assert target.deliveries.get(channel="email").state == "retrying"
        deliver_envelope(target.pk)
    assert target.deliveries.get(channel="email").state == "sent"
    assert send.call_count == (2 if phase == "retry" else 1)
    assert all(call.args[0].to == [owner.email] for call in send.call_args_list)
    assert resource.name in send.call_args.args[0].body
    sent = EmailLog.objects.filter(makerspace=tenant, event__in=["reminder", "daily_digest"], status="sent")
    assert sent.count() == 1 and sent.get().to_email == owner.email
    deliver_envelope(envelope.pk)
    deliver_envelope(target.pk)
    assert send.call_count == (2 if phase == "retry" else 1)
    assert target.deliveries.get(channel="email").state == "sent"
    assert run_reminder_sweep(now=clock[0], source_keys=["bookings.booking"])["dispatched"] == 0


@pytest.mark.parametrize("assembled", [False, True])
def test_digest_switch_off_suppresses_due_or_assembled_envelopes(monkeypatch, assembled):
    world, clock, send, envelope = queued(monkeypatch)
    tenant, _, _, _, _, owner, _ = world
    due = clock[0] + timedelta(hours=1)
    as_digest(tenant, owner, envelope, due)
    clock[0] = due
    summaries = NotificationEnvelope.objects.filter(makerspace=tenant, source_kind="notification.digest")
    if assembled:
        deliver_envelope(envelope.pk)
        summary = summaries.get()
        ensure_deliveries(summary)
        assert summary.deliveries.get(channel="email").state == "retrying"
    tenant.enabled_features = [key for key in tenant.enabled_features if key != "notifications.digests"]
    tenant.save(update_fields=["enabled_features"])

    deliver_envelope(summary.pk if assembled else envelope.pk)

    envelope.refresh_from_db()
    assert envelope.processed_at is not None and envelope.context["booking_id"]
    if assembled:
        assert summary.context["envelope_ids"] == [envelope.pk]
        assert summary.deliveries.get(channel="email").state == "skipped"
    else:
        assert not summaries.exists()
    send.assert_not_called()
