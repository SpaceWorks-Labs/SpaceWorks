import pytest
from django.utils import timezone

from apps.bookings.notification_owner_mailbox import KIND, needs_direct, notify_owner, prepare
from apps.bookings.notifications import notify_booking_status
from apps.integrations.models import EmailLog
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_resolution import resolve

pytestmark = pytest.mark.django_db


def owner_envelope(world):
    return NotificationEnvelope.objects.get(makerspace=world.space, recipient=world.owner, audience="requester")


def test_booking_contact_mail_survives_unverified_account_and_emits_once(world):
    notify_booking_status(world.booking, "confirmed")
    envelope = owner_envelope(world)
    log = EmailLog.objects.get(source_kind=KIND, source_id=envelope.pk)
    assert log.to_email == world.booking.email and log.recipient_id == world.owner.pk
    assert not any(target.channel == "email" for target in resolve(envelope))
    notify_booking_status(world.booking, "confirmed")
    assert EmailLog.objects.filter(source_kind=KIND, source_id=envelope.pk).count() == 1
    from apps.integrations.dispatch import _deliver
    assert _deliver(log).status == "sent"


def test_verified_account_keeps_only_the_envelope_email(world):
    world.owner.email_verified_at = timezone.now()
    world.owner.save(update_fields=["email_verified_at"])
    notify_booking_status(world.booking, "confirmed")
    envelope = owner_envelope(world)
    assert any(target.channel == "email" for target in resolve(envelope))
    assert not EmailLog.objects.filter(source_kind=KIND).exists()


def test_contact_must_prove_the_same_owned_mailbox(world):
    world.booking.email = "someone-else@example.test"
    world.booking.save(update_fields=["email"])
    notify_booking_status(world.booking, "confirmed")
    assert not needs_direct(owner_envelope(world))
    assert not EmailLog.objects.filter(source_kind=KIND).exists()


@pytest.mark.parametrize("withdrawal", ["toggle", "revision", "owner", "account_inactive", "membership_revoked", "consent",
    "matrix", "module", "configuration", "preference", "suppression", "verified", "mailbox"])
def test_pending_and_failed_contact_mail_recheck_live_rules(world, withdrawal):
    from apps.integrations.models import NotificationPreference as Matrix
    from apps.integrations.models_endpoints import ChannelConfiguration
    from apps.integrations.models_suppression import EmailSuppression
    from apps.integrations.email_preferences import address_hash
    from apps.notifications.models_preferences import NotificationPreference
    notify_booking_status(world.booking, "confirmed")
    envelope = owner_envelope(world)
    log = EmailLog.objects.get(source_kind=KIND, source_id=envelope.pk)
    assert prepare(log)
    if withdrawal == "toggle":
        world.resource.requester_notifications_enabled = False
        world.resource.save(update_fields=["requester_notifications_enabled"])
    elif withdrawal == "revision":
        world.booking.calendar_sequence += 1
        world.booking.save(update_fields=["calendar_sequence"])
    elif withdrawal == "owner":
        world.booking.member = world.other
        world.booking.save(update_fields=["member"])
    elif withdrawal == "account_inactive":
        world.owner.is_active = False
        world.owner.save(update_fields=["is_active"])
    elif withdrawal == "membership_revoked":
        world.owner.makerspace_memberships.filter(makerspace=world.space).update(status="revoked")
    elif withdrawal == "consent":
        world.owner.makerspace_memberships.filter(makerspace=world.space).update(receives_notifications=False)
    elif withdrawal == "matrix":
        Matrix.objects.create(makerspace=world.space, feature="bookings", channel="email", enabled=False)
    elif withdrawal == "module":
        world.space.enabled_modules = [key for key in world.space.enabled_modules if key != "email"]
        world.space.save(update_fields=["enabled_modules"])
    elif withdrawal == "configuration":
        ChannelConfiguration.objects.create(makerspace=world.space, channel="email", enabled=False)
    elif withdrawal == "preference":
        NotificationPreference.objects.create(makerspace=world.space, user=world.owner, category="bookings",
                                              channels=["in_app"], email_fallback=False)
    elif withdrawal == "suppression":
        EmailSuppression.objects.create(makerspace=world.space, address_hash=address_hash(world.space.pk, world.owner.email),
                                        reason="bounce")
    elif withdrawal == "verified":
        world.owner.email_verified_at = timezone.now()
        world.owner.save(update_fields=["email_verified_at"])
    else:
        world.owner.email = "changed@example.test"
        world.owner.save(update_fields=["email"])
    assert not prepare(log)
    log.status, log.attempts = "failed", 1
    log.save(update_fields=["status", "attempts"])
    assert not prepare(log)


def test_delivered_contact_email_is_not_resent_after_account_verification(world):
    from apps.integrations.dispatch import _deliver
    notify_booking_status(world.booking, "confirmed")
    envelope = owner_envelope(world)
    log = EmailLog.objects.get(source_kind=KIND, source_id=envelope.pk)
    assert _deliver(log).status == "sent"
    world.owner.email_verified_at = timezone.now()
    world.owner.save(update_fields=["email_verified_at"])
    assert not any(target.channel == "email" for target in resolve(envelope))


def test_booking_campaigns_never_gain_contact_mail_fallback(world):
    envelope = world.envelope(source_kind="bookings.broadcast", event="broadcast", source_id="999")
    assert not needs_direct(envelope) and notify_owner(envelope) is None


def test_booking_reminder_contact_source_is_registered_and_rechecked(world):
    from apps.bookings.reminder_envelopes import emit_reminder
    from apps.integrations.delivery_sources import prepare as prepare_delivery
    from types import SimpleNamespace
    from apps.makerspaces.reminder_policy import reminder_offsets
    # The source only accepts an offset the makerspace actually schedules.
    offset = reminder_offsets(world.space, "booking")[0]
    assert emit_reminder(world.booking, SimpleNamespace(pk=99, offset_seconds=offset), world.owner)
    log = EmailLog.objects.get(source_kind=KIND, event="reminder")
    assert prepare_delivery(log)
    world.booking.status = "cancelled"
    world.booking.save(update_fields=["status"])
    assert not prepare_delivery(log)


def test_booking_fallback_is_rolled_back_with_the_decision(world):
    from django.db import transaction
    with pytest.raises(RuntimeError), transaction.atomic():
        notify_booking_status(world.booking, "confirmed")
        assert EmailLog.objects.filter(source_kind=KIND).exists()
        raise RuntimeError("rollback")
    assert not EmailLog.objects.filter(source_kind=KIND).exists()
    assert not NotificationEnvelope.objects.filter(makerspace=world.space).exists()


def test_booking_module_purge_removes_its_compatibility_mail_only(world):
    from apps.makerspaces.module_purge_collectors_single_model import bookings_delete
    notify_booking_status(world.booking, "confirmed")
    foreign = EmailLog.objects.create(makerspace=world.space, to_email="other@example.test", subject="Other", source_kind="other.domain")
    bookings_delete(world.space, None)
    assert not EmailLog.objects.filter(makerspace=world.space, source_kind=KIND).exists()
    assert EmailLog.objects.filter(pk=foreign.pk).exists()


def test_verification_releases_unsent_contact_reservation_and_wakes_envelope(world):
    from apps.integrations.dispatch import _deliver
    from apps.integrations.notification_tasks import deliver_envelope
    notify_booking_status(world.booking, "confirmed")
    envelope = owner_envelope(world)
    log = EmailLog.objects.get(source_kind=KIND, source_id=envelope.pk)
    NotificationEnvelope.objects.filter(pk=envelope.pk).update(processed_at=timezone.now())
    world.owner.email_verified_at = timezone.now()
    world.owner.save(update_fields=["email_verified_at"])
    # Pending SMTP owns this intent until it either succeeds or yields explicitly.
    assert not any(target.channel == "email" for target in resolve(envelope))
    assert _deliver(log).status == "skipped"
    envelope.refresh_from_db()
    assert envelope.processed_at is None
    assert any(target.channel == "email" for target in resolve(envelope))
    # A worker that started before the handoff may finish its inbox leg later.
    NotificationEnvelope.objects.filter(pk=envelope.pk).update(processed_at=timezone.now())
    assert envelope.deliveries.filter(channel="email", state="retrying", next_attempt_at__isnull=False).exists()
    deliver_envelope(envelope.pk)
    assert EmailLog.objects.filter(source_kind="notification.envelope", source_id=envelope.pk, status="sent").count() == 1
