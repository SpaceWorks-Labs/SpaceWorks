"""Booking-only fixtures driving ordinary creation and the shared outbox."""
from datetime import timedelta
from unittest.mock import Mock

from django.utils import timezone

from apps.accounts.models import User
from apps.bookings.services_bookings import create_booking
from apps.bookings.services_broadcasts import compose, change
from apps.integrations.broadcasts_worker import broadcast_batch
from apps.integrations.models import EmailLog
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.module_registry import core_module_keys
from tests.bookings.staff_grant_helpers import grant_fixture


def fixture(monkeypatch, slug="bk-d"):
    tenant, manager, sender, resource, grant, user = grant_fixture("manage_reservations", slug)
    tenant.enabled_modules = sorted(core_module_keys() | {"bookings", "notifications", "email"})
    tenant.enabled_features = ["bookings.staff_grants", "bookings.broadcasts", "notifications.digests"]  # digests are a capability
    tenant.booking_requester_notifications_enabled = True
    tenant.save()
    # Account-only bookings must work even with membership/presence/events/rail off.
    MakerspaceMembership.objects.filter(makerspace=tenant, user=user).delete()
    User.objects.filter(pk=user.pk).update(email_verified_at=timezone.now())
    user.refresh_from_db()
    monkeypatch.setattr("apps.integrations.dispatch_outbox._enqueue", lambda pk: None)
    monkeypatch.setattr("apps.integrations.broadcasts_worker.enqueue", lambda *args: None)
    monkeypatch.setattr("apps.integrations.digests.digest_due", lambda *args: None)
    monkeypatch.setattr("apps.integrations.quiet_hours.quiet_until", lambda *args: None)
    monkeypatch.setattr("apps.integrations.timing_dispatch.quiet_until", lambda *args: None)
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    booking = reserve(resource, user)
    return tenant, manager, sender, resource, grant, user, booking


def reserve(resource, user, start=None):
    start = start or timezone.now() + timedelta(hours=23)
    return create_booking(resource, actor=user, member=user, starts_at=start, ends_at=start+timedelta(hours=1))


def draft(resource, sender, **values):
    return compose(resource, sender, subject=values.pop("subject", "Hi {{ name }}"),
        body=values.pop("body", "{{ resource_name }} {{ booking_start }} {{ booking_url }}"),
        window_start=timezone.now(), window_end=timezone.now()+timedelta(days=7), **values)


def queued(resource, sender):
    campaign = draft(resource, sender)
    change(campaign, sender, "queue")
    broadcast_batch("booking_broadcast", campaign.pk)
    delivery = campaign.deliveries.get()
    return campaign, delivery, EmailLog.objects.get(pk=delivery.outbox_id)


def smtp(monkeypatch, **kwargs):
    send = Mock(return_value=1, **kwargs)
    monkeypatch.setattr("django.core.mail.EmailMultiAlternatives.send", lambda message: send(message))
    monkeypatch.setattr("apps.integrations.email.makerspace_mail_connection", lambda tenant: (None, "staff@example.test"))
    return send
