"""Decision 221(f): the linked-change gaps -- restored bookings, per-room grant holders, guest bookers.

A restored linked booking tells the event's organizers; a per-room `manage_reservations` grant
holder (not tenant staff) hears that the event a room booking holds moved; an account-less guest
booker gets one email to the booking's own address. Nothing is changed by any of them.
"""
from datetime import timedelta

import pytest
from django.core import mail

from apps.bookings.models import Booking, BookingSpaceStaffGrant
from apps.bookings.services_restore import restore_booking
from apps.events import services
from apps.events.models import Event
from apps.integrations.models_contract import NotificationEnvelope
from tests.encryption.conftest import enabled_encryption
from tests.events.test_booking_decision_replacement import linked
from tests.machines.certification_helpers import _member

pytestmark = pytest.mark.django_db(transaction=True)


def move(event, staff):
    with enabled_encryption():
        return services.update_event(event, actor=staff, starts_at=event.starts_at + timedelta(hours=1),
                                     ends_at=event.ends_at + timedelta(hours=1))


def grants_on(maker):
    """Per-room staff grants are an opt-in capability of the space (`bookings.staff_grants`)."""
    maker.enabled_features = sorted(set(maker.enabled_features) | {"bookings.staff_grants"})
    maker.save(update_fields=["enabled_features"])


def test_restoring_a_cancelled_linked_booking_tells_the_event_organizers():
    maker, staff, member, event, _room, booking, _decision, _client = linked("g221-restore")
    # Undoing a cancellation is a staff reservation tool, an opt-in capability of the space.
    maker.enabled_features = sorted(set(maker.enabled_features) | {"bookings.staff_tools"})
    maker.save(update_fields=["enabled_features"])
    from apps.bookings import services_transitions
    with enabled_encryption():
        services_transitions.cancel_booking(booking, actor=staff)
        booking.refresh_from_db()
        restore_booking(booking, actor=staff)
    rows = NotificationEnvelope.objects.filter(feature="events", event="linked_booking_changed",
                                               context__change="restored")
    assert staff.pk in {row.recipient_id for row in rows}
    assert {row.source_id for row in rows} == {str(event.pk)}
    assert Event.objects.get(pk=event.pk).status == event.status  # the event itself is never changed


def test_a_room_grant_holder_who_is_not_staff_hears_the_event_moved():
    maker, staff, member, event, room, booking, _decision, _client = linked("g221-grant")
    grants_on(maker)
    holder, _ = _member(maker, "g221-grant-holder")
    BookingSpaceStaffGrant.objects.create(makerspace=maker, space=room, user=holder, granted_by=staff,
                                          permissions=["manage_reservations"])
    other, _ = _member(maker, "g221-grant-other")
    BookingSpaceStaffGrant.objects.create(makerspace=maker, space=room, user=other, granted_by=staff,
                                          permissions=["view_reservations"])
    move(event, staff)
    rows = NotificationEnvelope.objects.filter(feature="bookings", event="linked_event_changed",
                                               source_kind="events.linked_booking_notice_grant")
    assert [row.recipient_id for row in rows] == [holder.pk]
    assert "Workshop" not in rows[0].message_body  # the grant holder gets the staff wording, no event title


def test_a_revoked_grant_is_no_longer_eligible_at_send():
    from django.utils import timezone

    from apps.events.linked_change_recipients import grant_eligible
    maker, staff, _member_row, event, room, _booking, _decision, _client = linked("g221-revoked")
    grants_on(maker)
    holder, _ = _member(maker, "g221-revoked-holder")
    grant = BookingSpaceStaffGrant.objects.create(makerspace=maker, space=room, user=holder, granted_by=staff,
                                                  permissions=["manage_reservations"])
    move(event, staff)
    envelope = NotificationEnvelope.objects.get(source_kind="events.linked_booking_notice_grant",
                                                recipient=holder)
    assert grant_eligible(envelope)
    BookingSpaceStaffGrant.objects.filter(pk=grant.pk).update(revoked_at=timezone.now())
    assert not grant_eligible(envelope)


@pytest.mark.parametrize("toggle, expected", [(True, 1), (False, 0)])
def test_a_guest_booker_email_follows_the_rooms_requester_toggle(toggle, expected):
    maker, staff, _member_row, event, room, booking, _decision, _client = linked(f"g221-guest-{int(toggle)}")
    Booking.objects.filter(pk=booking.pk).update(member=None, email="guest-booker@example.org")
    room.requester_notifications_enabled = toggle  # the room's own override beats the space default
    room.save(update_fields=["requester_notifications_enabled"])
    mail.outbox.clear()
    from django.test import override_settings
    with override_settings(CELERY_TASK_ALWAYS_EAGER=True):
        move(event, staff)
    from apps.integrations.models import EmailLog
    logs = EmailLog.objects.filter(makerspace=maker, event="linked_event_changed")
    assert logs.count() == expected  # exactly one email per event version when on, none when off
