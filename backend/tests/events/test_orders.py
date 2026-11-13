"""L6 G27: multi-ticket orders, one registration per attendee, claims need a signed-in account."""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.events.models import EventOrder, EventOrderSeat, EventRegistration
from apps.events.orders_attendees import token_digest
from apps.payments.models import Payment
from tests.events.collab_helpers import client_for
from tests.events.orders_helpers import (
    l6_space, order_payment, place, quote, settle_offline, ticketed_event, verified,
)

pytestmark = pytest.mark.django_db


def _claim(user, token):
    return client_for(user).post(reverse("member-ticket-claim", kwargs={"token": token}), {}, format="json")


def _mint(seat):
    import secrets
    token = secrets.token_urlsafe(16)
    EventOrderSeat.objects.filter(pk=seat.pk).update(claim_token_digest=token_digest(token))
    return token


def test_free_order_seats_the_buyer_and_holds_named_seats(django_capture_on_commit_callbacks):
    space, event, _staff, ticket = ticketed_event(amount=0)
    buyer = verified("buyer")
    with django_capture_on_commit_callbacks(execute=True):
        response = place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 3}],
                         attendees=["friend@example.test"])
    assert response.status_code == 201, response.data
    order = EventOrder.objects.get()
    assert order.status == "paid" and order.total == 0
    seats = list(order.seats.order_by("pk"))
    assert len(seats) == 3
    assert seats[0].status == "claimed" and seats[0].registration.member == buyer
    assert seats[0].registration.quoted_amount == 0
    assert seats[1].attendee_email == "friend@example.test" and seats[1].invited_at is not None
    assert seats[2].attendee_email == "" and seats[2].status == "unclaimed"
    # Nobody is registered without an account: only the buyer has a registration.
    assert EventRegistration.objects.filter(event=event).count() == 1
    assert not Payment.objects.exists()


def test_paid_order_raises_one_payment_and_settles_into_registrations(django_capture_on_commit_callbacks):
    space, event, staff, ticket = ticketed_event(amount=12)
    buyer = verified("buyer")
    response = place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 2}])
    assert response.status_code == 201, response.data
    order = EventOrder.objects.get()
    payment = order_payment(order)
    assert order.status == "pending" and payment.amount == Decimal("24.00") and payment.member == buyer
    assert order.hold.seats == 2 and order.seats.count() == 2
    assert not EventRegistration.objects.exists()
    with django_capture_on_commit_callbacks(execute=True):
        settle_offline(payment, staff)
    order.refresh_from_db()
    assert order.status == "paid"
    registration = EventRegistration.objects.get(event=event)
    assert registration.member == buyer and registration.quoted_amount == 0
    # The order's Payment carries the money; the seat's registration raises no charge of its own.
    assert Payment.objects.filter(subject_type="event_registration").count() == 0
    order.hold.refresh_from_db()
    assert order.hold.release_reason == "paid"


def test_claim_requires_signed_in_matching_verified_account(django_capture_on_commit_callbacks):
    space, event, _staff, ticket = ticketed_event(amount=0)
    buyer, friend, stranger = verified("buyer"), verified("friend"), verified("stranger")
    with django_capture_on_commit_callbacks(execute=True):
        place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 2}], attendees=[friend.email])
    seat = EventOrderSeat.objects.get(attendee_email=friend.email)
    token = _mint(seat)
    url = reverse("member-ticket-claim", kwargs={"token": token})
    from rest_framework.test import APIClient
    assert APIClient().post(url, {}, format="json").status_code in (401, 403)
    assert _claim(stranger, token).data["code"] == "claim_email_mismatch"
    with django_capture_on_commit_callbacks(execute=True):
        claimed = _claim(friend, token)
    assert claimed.status_code == 201, claimed.data
    seat.refresh_from_db()
    assert seat.status == "claimed" and seat.registration.member == friend
    # The token is spent: one seat, one registration, never twice.
    assert _claim(friend, token).status_code == 404


def test_unverified_email_cannot_claim(django_capture_on_commit_callbacks):
    from tests.events.ticketing_helpers import account
    space, event, _staff, ticket = ticketed_event(amount=0)
    buyer, friend = verified("buyer"), account("friend")
    with django_capture_on_commit_callbacks(execute=True):
        place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 2}], attendees=[friend.email])
    token = _mint(EventOrderSeat.objects.get(attendee_email=friend.email))
    assert _claim(friend, token).data["code"] == "claim_email_mismatch"


def test_buyer_assigns_and_chases_attendees(django_capture_on_commit_callbacks):
    space, event, _staff, ticket = ticketed_event(amount=0)
    buyer = verified("buyer")
    with django_capture_on_commit_callbacks(execute=True):
        place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 2}])
    order = EventOrder.objects.get()
    seat = order.seats.get(status="unclaimed")
    url = reverse("member-order-attendees", kwargs={"makerspace_id": space.pk, "order_id": order.pk})
    with django_capture_on_commit_callbacks(execute=True):
        response = client_for(buyer).post(url, {"assignments": {str(seat.pk): "pal@example.test"}}, format="json")
    assert response.status_code == 200, response.data
    seat.refresh_from_db()
    assert seat.attendee_email == "pal@example.test" and seat.invited_at is not None
    detail = client_for(buyer).get(reverse("member-order-detail", kwargs={"makerspace_id": space.pk,
                                                                          "order_id": order.pk}))
    assert [row["status"] for row in detail.data["seats"]] == ["claimed", "unclaimed"]
    other = verified("other")
    assert client_for(other).get(reverse("member-order-detail", kwargs={
        "makerspace_id": space.pk, "order_id": order.pk})).status_code == 404


def test_orders_off_is_refused_and_quote_matches_charge():
    space = l6_space(features=[])
    _space, event, _staff, ticket = ticketed_event(space, amount=5)
    buyer = verified("buyer")
    assert place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 1}]).status_code == 404
    space.enabled_features = sorted({*space.enabled_features, "events.orders"})
    space.save(update_fields=["enabled_features"])
    preview = quote(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 2}])
    assert preview.status_code == 200 and preview.data["quote"]["total"] == "10.00"
    stale = place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 3}], digest=preview.data["quote"]["digest"])
    assert stale.status_code == 409 and stale.data["code"] == "price_changed"
    fresh = place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 2}], digest=preview.data["quote"]["digest"])
    assert fresh.status_code == 201
    assert not EventOrder.objects.filter(status="pending").exclude(pk=fresh.data["order"]["id"]).exists()


def test_buyer_already_registered_must_buy_for_others(django_capture_on_commit_callbacks):
    space, event, _staff, ticket = ticketed_event(amount=0)
    buyer = verified("buyer")
    with django_capture_on_commit_callbacks(execute=True):
        place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 1}])
    again = place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 1}])
    assert again.status_code == 409 and again.data["code"] == "already_registered"
    with django_capture_on_commit_callbacks(execute=True):
        others = place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 1}], buyer_attends=False)
    assert others.status_code == 201
