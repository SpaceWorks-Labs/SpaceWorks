"""Decision 216: the staff room price is previewed, bound and verified under the create lock."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.rbac import Action
from apps.bookings.models import BookableSpace, Booking
from apps.payments.models import Payment
from tests.machines.certification_helpers import _manager, _member, _space

pytestmark = pytest.mark.django_db


def setup(slug="staff-price", *, charges=True, amount="12.50", approval="instant"):
    maker = _space(slug, modules=("bookings",), certifications=False)
    # Both switches default ON for a new space, so "charges off" must remove them explicitly.
    switches = {"charges.enabled", "charges.bookings"}
    features = set(maker.enabled_features)
    maker.enabled_features = sorted(features | switches if charges else features - switches)
    maker.save(update_fields=["enabled_features"])
    actor, _ = _manager(maker, slug + "-desk", actions=(Action.MANAGE_BOOKINGS,))
    member, _ = _member(maker, slug + "-member")
    room = BookableSpace.objects.create(makerspace=maker, name="Room", approval_mode=approval,
                                        payment_amount=amount)
    client = APIClient()
    client.force_authenticate(actor)
    return maker, actor, member, room, client


def window(member):
    start = (timezone.now() + timedelta(days=1)).replace(microsecond=0)
    return {"member_id": member.pk, "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=1)).isoformat()}


def preview(client, room, body):
    return client.post(reverse("admin-space-booking-quote", kwargs={"pk": room.pk}), body, format="json")


def create(client, room, body):
    return client.post(reverse("admin-space-booking-list", kwargs={"pk": room.pk}), body, format="json")


def booking_debts(maker):
    return Payment.objects.filter(makerspace=maker, subject_type=Payment.SubjectType.BOOKING)


def test_confirmed_positive_quote_creates_one_booking_owned_debt_matching_the_preview():
    maker, _, member, room, client = setup()
    body = window(member)
    shown = preview(client, room, body)
    assert shown.status_code == 200 and shown.data["charges"] == "tracked"
    assert Decimal(shown.data["quote"]["total"]) == Decimal("12.50")
    assert not Booking.objects.exists() and not booking_debts(maker).exists()
    response = create(client, room, {**body, "price_confirmation": shown.data["price_confirmation"]})
    assert response.status_code == 201
    debt = booking_debts(maker).get()
    assert debt.subject_id == response.data["id"] and debt.amount == Decimal(shown.data["quote"]["total"])
    assert debt.provider == "unclaimed"  # the online rail is off: the core ledger still records it
    assert debt.pricing_snapshot["digest"] == shown.data["quote"]["digest"]


def test_stale_digest_creates_neither_booking_nor_debt():
    maker, _, member, room, client = setup("staff-price-stale")
    body = window(member)
    shown = preview(client, room, body)
    room.payment_amount = "20.00"
    room.save(update_fields=["payment_amount"])
    response = create(client, room, {**body, "price_confirmation": shown.data["price_confirmation"]})
    assert response.status_code == 409 and response.data["code"] == "price_changed"
    assert Decimal(response.data["confirmation"]["quote"]["total"]) == Decimal("20.00")
    assert not Booking.objects.exists() and not booking_debts(maker).exists()


@pytest.mark.parametrize("change", ["window", "member", "charges_on"])
def test_changed_inputs_or_charge_mode_force_a_fresh_confirmation(change):
    maker, actor, member, room, client = setup("staff-price-" + change, charges=change != "charges_on")
    body = window(member)
    shown = preview(client, room, body)
    if change == "charges_on":
        assert shown.data["charges"] == "off" and shown.data["quote"] is None
        maker.enabled_features = sorted(set(maker.enabled_features) | {"charges.enabled", "charges.bookings"})
        maker.save(update_fields=["enabled_features"])
    elif change == "window":
        body["ends_at"] = (timezone.now() + timedelta(days=1, hours=3)).replace(microsecond=0).isoformat()
    else:
        other, _ = _member(maker, "staff-price-other")
        body["member_id"] = other.pk
    response = create(client, room, {**body, "price_confirmation": shown.data["price_confirmation"]})
    assert response.status_code == 409 and response.data["code"] == "price_changed"
    assert not Booking.objects.exists() and not booking_debts(maker).exists()


def test_zero_quote_and_charges_off_create_the_booking_without_debt():
    for slug, kwargs in (("staff-price-zero", {"amount": "0.00"}), ("staff-price-off", {"charges": False})):
        maker, _, member, room, client = setup(slug, **kwargs)
        body = window(member)
        shown = preview(client, room, body)
        response = create(client, room, {**body, "price_confirmation": shown.data["price_confirmation"]})
        assert response.status_code == 201
        assert not booking_debts(maker).exists()


def test_pending_booking_freezes_the_confirmed_quote_for_approval():
    maker, _, member, room, client = setup("staff-price-pending", approval="approve")
    body = window(member)
    shown = preview(client, room, body)
    response = create(client, room, {**body, "price_confirmation": shown.data["price_confirmation"]})
    assert response.status_code == 201
    booking = Booking.objects.get(pk=response.data["id"])
    assert booking.status == Booking.Status.PENDING
    assert booking.pricing_snapshot["digest"] == shown.data["quote"]["digest"]
    assert not booking_debts(maker).exists()


def test_create_without_confirmation_keeps_the_existing_contract():
    maker, _, member, room, client = setup("staff-price-legacy")
    assert create(client, room, window(member)).status_code == 201
    assert booking_debts(maker).get().amount == Decimal("12.50")


def test_preview_denies_other_tenants_unknown_members_and_unauthorized_staff():
    maker, _, member, room, client = setup("staff-price-deny")
    other_maker, _, outsider, other_room, _ = setup("staff-price-deny-other")
    assert preview(client, other_room, window(outsider)).status_code == 404
    assert preview(client, room, window(outsider)).status_code == 404
    clerk, _ = _manager(maker, "staff-price-clerk", actions=(Action.MANAGE_EVENTS,))
    other = APIClient()
    other.force_authenticate(clerk)
    assert preview(other, room, window(member)).status_code in (403, 404)
    malformed = {**window(member), "price_confirmation": "not-a-digest"}
    assert create(client, room, malformed).status_code == 400
    assert not Booking.objects.exists()
