"""Account-only booking owners retain channels when the inbox is uninstalled."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.bookings.communication_recipients import notification_account
from apps.bookings.models import BookableSpace, Booking
from apps.bookings.notifications import _emit, LIFECYCLE_SOURCE
from apps.bookings.notification_sources import lifecycle_eligible
from apps.integrations.models_contract import NotificationEnvelope
from apps.makerspaces.models import MakerspaceMembership
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db


def setup_booking():
    space = make_space("recon-booking")
    space.enabled_modules = sorted((set(space.enabled_modules) | {"bookings"}) - {"notifications", "membership"})
    space.booking_requester_notifications_enabled = True
    space.save(update_fields=["enabled_modules", "booking_requester_notifications_enabled"])
    owner = make_user("recon-booking-owner", access_status="active")
    resource = BookableSpace.objects.create(makerspace=space, name="Room", is_public=True)
    start = timezone.now() + timedelta(hours=2)
    row = Booking.objects.create(space=resource, member=owner, name="Owner", email=owner.email, phone="+15550100",
                                 starts_at=start, ends_at=start + timedelta(hours=1), status="confirmed")
    return space, owner, row


def test_booking_account_does_not_require_membership_or_optional_inbox():
    space, owner, _ = setup_booking()
    assert notification_account(space, owner.pk, "reminder").pk == owner.pk
    membership = MakerspaceMembership.objects.create(makerspace=space, user=owner, role="custom", status="revoked",
                                                     assigned_role=space.roles.get(slug="member"))
    assert notification_account(space, owner.pk, "reminder") is None
    membership.status, membership.receives_notifications = "active", False
    membership.save(update_fields=["status", "receives_notifications"])
    assert notification_account(space, owner.pk, "reminder") is None


def test_booking_source_rechecks_revision_owner_and_source_existence(monkeypatch):
    space, owner, row = setup_booking()
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    for _ in range(2):
        assert _emit(row, "confirmed", owner.pk, "requester", LIFECYCLE_SOURCE, {"subject": "Confirmed", "text": "Confirmed"})
    envelope = NotificationEnvelope.objects.get(recipient=owner)
    assert envelope.context["booking.id"] == row.pk
    assert lifecycle_eligible(envelope)
    Booking.objects.filter(pk=row.pk).update(calendar_sequence=row.calendar_sequence + 1)
    assert not lifecycle_eligible(envelope)
    Booking.objects.filter(pk=row.pk).update(calendar_sequence=row.calendar_sequence, member=None)
    assert not lifecycle_eligible(envelope)
    row.delete()
    assert not lifecycle_eligible(envelope)
