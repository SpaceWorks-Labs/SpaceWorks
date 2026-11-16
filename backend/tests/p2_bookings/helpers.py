from datetime import timedelta
from types import SimpleNamespace

from django.utils import timezone

from apps.bookings.services_bookings import create_booking
from tests.bookings.staff_grant_helpers import client_for, grant_fixture  # noqa: F401


def world(slug, permission="manage_reservations", approval="approve", start_in=timedelta(days=2)):
    tenant, manager, grantee, space, grant, member = grant_fixture(permission, slug)
    space.approval_mode = approval
    space.booking_lead_time_minutes = 0  # departure tests book slots that start within the hour
    space.save(update_fields=["approval_mode", "booking_lead_time_minutes"])
    start = timezone.now() + start_in
    booking = create_booking(space, member=member, actor=member, starts_at=start, ends_at=start + timedelta(hours=1))
    return SimpleNamespace(tenant=tenant, manager=manager, grantee=grantee, space=space, grant=grant,
                           member=member, booking=booking)


def envelopes(**filters):
    from apps.integrations.models_contract import NotificationEnvelope
    return NotificationEnvelope.objects.filter(**filters)
