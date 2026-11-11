"""Decision 216: replacing a rejected or cancelled linked reservation keeps the link and old debt."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.rbac import Action
from apps.bookings import services_bookings
from apps.bookings.models import Booking
from apps.bookings.staff_price_confirmation import preview
from apps.events import booking_decision_service
from apps.events.models import Event
from apps.events.models_booking_decision import EventBookingDecision
from apps.payments.models import Payment
from tests.account_split_g2_helpers import staff_for_actions
from tests.encryption.conftest import enabled_encryption
from tests.events.orders_helpers import l6_space, make_staff
from tests.payments.test_track3_booking_event_charging import bookable, member_with_phone

pytestmark = pytest.mark.django_db(transaction=True)


def linked(slug, *, approval_mode="approve"):
    maker = l6_space(slug)
    maker.enabled_modules = sorted(set(maker.enabled_modules) | {"bookings"})
    maker.enabled_features = sorted(set(maker.enabled_features) | {"charges.enabled", "charges.bookings"})
    maker.save(update_fields=["enabled_modules", "enabled_features"])
    staff, member = make_staff(maker), member_with_phone(slug + "-member", maker)
    start = timezone.now() + timedelta(days=2)
    event = Event.objects.create(makerspace=maker, title="Workshop", starts_at=start,
                                 ends_at=start + timedelta(hours=1), status=Event.Status.DRAFT)
    room = bookable(maker, approval_mode=approval_mode, amount="12.50")
    with enabled_encryption():
        original = services_bookings.create_booking(room, starts_at=start, ends_at=event.ends_at,
                                                    member=member, actor=member)
        decision, _ = booking_decision_service.create_decision(
            staff, maker, event.pk, booking_id=original.pk, operation_id=uuid4(), expected_generation=None,
            expected_revision=0, expected_events_epoch=maker.loan_context_generations["events"],
            expected_bookings_epoch=maker.loan_context_generations["bookings"])
    client = APIClient()
    client.force_authenticate(staff)
    return maker, staff, member, event, room, original, decision, client


def body(room, member, original, **overrides):
    with enabled_encryption():
        shown = preview(room, member, original.starts_at, original.ends_at)
    return {"expected_booking_id": original.pk, "space_id": room.pk, "member_id": member.pk,
            "starts_at": original.starts_at.isoformat(), "ends_at": original.ends_at.isoformat(),
            "price_confirmation": shown["price_confirmation"], **overrides}


def replace(client, maker, event, data):
    url = reverse("admin-event-booking-replacement", kwargs={"makerspace_id": maker.pk, "event_id": event.pk})
    with enabled_encryption():
        return client.post(url, data, format="json")


def link_state(client, maker, event):
    url = reverse("admin-event-booking-link", kwargs={"makerspace_id": maker.pk, "event_id": event.pk})
    with enabled_encryption():
        return client.get(url).data


def test_rejected_reservation_is_replaced_through_normal_admission_and_keeps_the_link():
    maker, staff, member, event, room, original, decision, client = linked("replace-rejected")
    with enabled_encryption():
        services_bookings.reject_booking(original, actor=staff, reason="Room double booked")
    assert link_state(client, maker, event)["replaceable"] is True
    response = replace(client, maker, event, body(room, member, original))
    assert response.status_code == 201, response.data
    replacement = Booking.objects.get(pk=response.data["booking_id"])
    assert replacement.replaces_id == original.pk and replacement.status == Booking.Status.PENDING
    decision.refresh_from_db()
    assert decision.booking_id == original.pk  # the retained link is never rewritten
    state = link_state(client, maker, event)
    assert state["booking_id"] == original.pk and state["current_booking_id"] == replacement.pk
    assert state["history"] == [{"booking_id": original.pk, "status": "rejected"}]
    assert state["reservation_state"] == "pending" and state["replaceable"] is False
    assert not Payment.objects.filter(makerspace=maker, subject_type="event_venue_fee").exists()


def test_cancelled_reservation_keeps_its_own_debt_and_the_replacement_raises_one_room_charge():
    maker, staff, member, event, room, original, _decision, client = linked("replace-cancelled",
                                                                            approval_mode="instant")
    old_debt = Payment.objects.get(makerspace=maker, subject_type=Payment.SubjectType.BOOKING,
                                   subject_id=original.pk)
    with enabled_encryption():
        services_bookings.cancel_booking(original, actor=staff)
    old_debt.refresh_from_db()
    old_state = (old_debt.pk, old_debt.status, old_debt.amount)
    response = replace(client, maker, event, body(room, member, original))
    assert response.status_code == 201, response.data
    old_debt.refresh_from_db()
    assert (old_debt.pk, old_debt.status, old_debt.amount) == old_state
    new_debt = Payment.objects.get(makerspace=maker, subject_type=Payment.SubjectType.BOOKING,
                                   subject_id=response.data["booking_id"])
    assert new_debt.amount == Decimal("12.50")
    assert not Payment.objects.filter(makerspace=maker, subject_type="event_venue_fee").exists()


@pytest.mark.parametrize("case", ["stale_booking", "not_replaceable", "stale_price"])
def test_refusals_create_no_booking_and_no_debt(case):
    maker, staff, member, event, room, original, _decision, client = linked("replace-refuse-" + case)
    if case != "not_replaceable":
        with enabled_encryption():
            services_bookings.reject_booking(original, actor=staff, reason="No")
    data = body(room, member, original)
    if case == "stale_booking":
        data["expected_booking_id"] = original.pk + 1000
    if case == "stale_price":
        room.payment_amount = "30.00"
        room.save(update_fields=["payment_amount"])
    before = (Booking.objects.count(), Payment.objects.filter(makerspace=maker).count())
    response = replace(client, maker, event, data)
    assert response.status_code == 409
    expected = {"stale_booking": "stale_context", "not_replaceable": "replacement_not_allowed",
                "stale_price": "price_changed"}[case]
    assert expected in str(response.data)
    assert (Booking.objects.count(), Payment.objects.filter(makerspace=maker).count()) == before


def test_a_reservation_is_replaced_at_most_once():
    maker, staff, member, event, room, original, _decision, client = linked("replace-once")
    with enabled_encryption():
        services_bookings.reject_booking(original, actor=staff, reason="No")
    data = body(room, member, original)
    assert replace(client, maker, event, data).status_code == 201
    assert replace(client, maker, event, data).status_code == 409
    assert Booking.objects.filter(replaces=original).count() == 1


def test_replacement_requires_independent_event_and_room_authority():
    maker, staff, member, event, room, original, _decision, _client = linked("replace-authority")
    with enabled_encryption():
        services_bookings.reject_booking(original, actor=staff, reason="No")
    rooms_only, _ = staff_for_actions(maker, "replace-rooms-only", (Action.MANAGE_BOOKINGS,))
    events_only, _ = staff_for_actions(maker, "replace-events-only", (Action.MANAGE_EVENTS,))
    other_maker, other_staff, *_rest = linked("replace-authority-other")
    for actor in (rooms_only, events_only, other_staff):
        client = APIClient()
        client.force_authenticate(actor)
        assert replace(client, maker, event, body(room, member, original)).status_code in (403, 404)
    assert not Booking.objects.filter(replaces=original).exists()


def test_a_replacement_cannot_be_linked_to_another_event():
    maker, staff, member, event, room, original, _decision, client = linked("replace-relink")
    with enabled_encryption():
        services_bookings.reject_booking(original, actor=staff, reason="No")
    replacement = replace(client, maker, event, body(room, member, original)).data["booking_id"]
    other = Event.objects.create(makerspace=maker, title="Other", starts_at=event.starts_at,
                                 ends_at=event.ends_at, status=Event.Status.DRAFT)
    with enabled_encryption(), pytest.raises(booking_decision_service.DecisionConflict):
        booking_decision_service.create_decision(
            staff, maker, other.pk, booking_id=replacement, operation_id=uuid4(), expected_generation=None,
            expected_revision=0, expected_events_epoch=maker.loan_context_generations["events"],
            expected_bookings_epoch=maker.loan_context_generations["bookings"])
    assert not EventBookingDecision.objects.filter(event=other).exists()
