"""Decision 216 (P1-1/P2-4): a linked venue booking changed -- the event's organizers are told.

Moves, cancellations and rejections of the decision booking (or a replacement descending from
it) reach Event/Space Managers and per-event `publish_schedule` delegates, once per booking
revision, without the booker's details, and never while Events or Bookings is off. The event
itself is never changed.
"""
from datetime import timedelta

import pytest

from apps.accounts.models import User
from apps.bookings import services_bookings
from apps.bookings.services_staff_edit import edit_booking_time
from apps.events.event_permissions import PUBLISH_SCHEDULE
from apps.events.models import Event
from apps.integrations.models_contract import NotificationEnvelope
from tests.encryption.conftest import enabled_encryption
from tests.events.manual_grant_fixture import create_manual_grant
from tests.events.test_booking_decision_replacement import linked
from tests.module_helpers import disable_module

pytestmark = pytest.mark.django_db(transaction=True)


def notices(**filters):
    return list(NotificationEnvelope.objects.filter(feature="events", event="linked_booking_changed", **filters)
                .order_by("pk"))


def test_rejecting_a_linked_booking_tells_event_staff_once_without_the_booker():
    maker, staff, member, event, _room, booking, _decision, _client = linked("lbc-reject")
    before = Event.objects.values("starts_at", "ends_at", "status").get(pk=event.pk)
    with enabled_encryption():
        services_bookings.reject_booking(booking, actor=staff, reason="Room double booked")
    rows = notices()
    assert staff.pk in {row.recipient_id for row in rows if row.audience == "staff"}
    assert member.pk not in {row.recipient_id for row in rows}
    assert {row.source_id for row in rows} == {str(event.pk)}
    assert rows[0].context["change"] == "rejected" and rows[0].context["booking_id"] == booking.pk
    for row in rows:
        assert member.username not in row.message_body and "@" not in row.message_body
        assert f"events?event={event.pk}" in row.message_body  # the event's venue panel
    assert Event.objects.values("starts_at", "ends_at", "status").get(pk=event.pk) == before
    from apps.events.linked_booking_notices import notify_organizers
    booking.refresh_from_db()
    notify_organizers(booking, "rejected")
    assert len(notices()) == len(rows)


def test_a_staff_time_edit_tells_an_event_delegate_holding_publish_schedule():
    maker, staff, _member, event, room, booking, _decision, _client = linked("lbc-move", approval_mode="instant")
    maker.enabled_features = sorted(set(maker.enabled_features) | {"bookings.staff_tools"})
    maker.save(update_fields=["enabled_features"])
    Event.objects.filter(pk=event.pk).update(status=Event.Status.PUBLISHED)
    delegate = User.objects.create_user(username="lbc-move-delegate", access_status="active")
    create_manual_grant(makerspace=maker, event=event, user=delegate, permissions=[PUBLISH_SCHEDULE])
    bystander = User.objects.create_user(username="lbc-move-bystander", access_status="active")
    create_manual_grant(makerspace=maker, event=event, user=bystander, permissions=["check_in"])
    with enabled_encryption():
        edit_booking_time(booking, actor=staff, starts_at=booking.starts_at + timedelta(hours=1),
                          ends_at=booking.ends_at + timedelta(hours=1))
    member_rows = notices(audience="member")
    assert [row.recipient_id for row in member_rows] == [delegate.pk]
    assert member_rows[0].source_kind == "events.linked_booking_change_grant"
    from apps.events.linked_booking_notices import grant_eligible
    assert grant_eligible(member_rows[0]) is True


def test_cancelling_a_linked_booking_is_told_and_an_unlinked_one_is_not():
    maker, staff, member, event, room, booking, _decision, _client = linked("lbc-cancel")
    with enabled_encryption():
        other = services_bookings.create_booking(room, starts_at=booking.starts_at + timedelta(days=1),
                                                 ends_at=booking.ends_at + timedelta(days=1),
                                                 member=member, actor=member)
        services_bookings.cancel_booking(other, actor=staff)
        assert notices() == []
        services_bookings.cancel_booking(booking, actor=staff)
    assert {row.context["change"] for row in notices()} == {"cancelled"}


def test_events_off_is_silent():
    maker, staff, _member, _event, _room, booking, _decision, _client = linked("lbc-events-off")
    disable_module(maker, "events")
    with enabled_encryption():
        services_bookings.reject_booking(booking, actor=staff, reason="Closed")
    assert notices() == []
