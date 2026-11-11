"""#135 Q-S18 follow-up: shop merch offered at an event, bought as an ordinary shop order."""

from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.payments.models import Payment
from apps.shop.models import ShopEventOffer, ShopOrder
from tests.events.ticketing_helpers import open_event

from .helpers import (
    BASE, client, line, manager, member, module_off, payment_for, product, shop_manager, shop_space, staff, switch,
)

pytestmark = pytest.mark.django_db


def _space(slug):
    return switch(shop_space(slug, "shop.online", "shop.event_pickup"), modules=("events",))


def _staff_url(space, event=None):
    tail = f"{event.pk}/" if event is not None else ""
    return f"/api/v1/admin/makerspaces/{space.pk}/shop/event-offers/{tail}"


def _public_url(space, event):
    return f"/api/v1/public/m/{space.slug}/shop/events/{event.public_token}/offers/"


def _offer(space, actor, event, *variants):
    return client(actor).put(_staff_url(space, event), {"variant_ids": [row.pk for row in variants]}, format="json")


def test_staff_offer_list_shows_only_the_offered_variants_on_the_event_page():
    space = _space("offer-basic")
    sm = manager(space)
    event = open_event(space)
    _shirt, shirt = product(space, sm, name="Shirt", price="20.00", kind="merch")
    _mug, mug = product(space, sm, name="Mug", price="9.00", kind="merch")
    saved = _offer(space, sm, event, shirt)
    assert saved.status_code == 200, saved.content
    assert saved.json() == {"variant_ids": [shirt.pk]}
    rows = client(sm).get(_staff_url(space)).json()
    assert [row["variant_ids"] for row in rows if row["id"] == event.pk] == [[shirt.pk]]
    public = client().get(_public_url(space, event))
    assert public.status_code == 200, public.content
    body = public.json()
    assert body["event"]["id"] == event.pk
    assert [product["name"] for product in body["products"]] == ["Shirt"]
    assert [variant["id"] for variant in body["products"][0]["variants"]] == [shirt.pk]
    assert mug.pk not in {variant["id"] for product in body["products"] for variant in product["variants"]}
    record = AuditLog.objects.get(makerspace=space, action="shop.event_offers_set")
    assert record.actor_id == sm.pk and record.meta["event_id"] == event.pk and record.meta["added"] == 1
    # Replacing with the same list writes nothing new; an empty list clears it.
    assert _offer(space, sm, event, shirt).status_code == 200
    assert AuditLog.objects.filter(makerspace=space, action="shop.event_offers_set").count() == 1
    assert _offer(space, sm, event).json() == {"variant_ids": []}
    assert client().get(_public_url(space, event)).json()["products"] == []


def test_offers_are_scoped_to_the_space_and_the_shop_roles():
    space, other = _space("offer-scope"), _space("offer-scope-other")
    sm, foreign_sm = manager(space), manager(other)
    event, foreign_event = open_event(space), open_event(other)
    _row, variant = product(space, sm, name="Badge")
    _foreign, foreign_variant = product(other, foreign_sm, name="Foreign badge")
    assert _offer(space, shop_manager(space), event, variant).status_code == 200
    assert _offer(space, staff(space, "inventory_manager"), event, variant).status_code == 404
    assert _offer(space, foreign_sm, event, variant).status_code == 404
    assert client(member(space)).put(_staff_url(space, event), {"variant_ids": []}, format="json").status_code in (
        403, 404)
    cross_variant = _offer(space, sm, event, foreign_variant)
    assert cross_variant.status_code == 400 and cross_variant.json()["code"] == "variant_invalid"
    cross_event = _offer(space, sm, foreign_event, variant)
    assert cross_event.status_code == 400 and cross_event.json()["code"] == "pickup_event_invalid"
    # Another space's event token under this space's shop is not found, never leaked.
    assert client().get(_public_url(space, foreign_event)).status_code == 404
    assert list(ShopEventOffer.objects.values_list("makerspace_id", "event_id", "variant_id")) == [
        (space.pk, event.pk, variant.pk)]


def test_offers_hide_with_shop_events_or_event_pickup_off_and_return_when_back_on():
    space = _space("offer-switches")
    sm = manager(space)
    event = open_event(space)
    _row, variant = product(space, sm, name="Sticker")
    assert _offer(space, sm, event, variant).status_code == 200
    url = _public_url(space, event)
    switch(space, "shop.event_pickup", on=False)
    assert client().get(url).status_code == 404 and client(sm).get(_staff_url(space)).status_code == 404
    switch(space, "shop.event_pickup")
    Makerspace.objects.filter(pk=space.pk).update(
        enabled_modules=sorted(set(space.enabled_modules) - {"events"}))
    space.refresh_from_db()
    assert client().get(url).status_code == 404 and client(sm).get(_staff_url(space)).status_code == 404
    switch(space, modules=("events",))
    module_off(space)
    assert client().get(url).status_code == 404 and client(sm).get(_staff_url(space)).status_code == 404
    switch(space, modules=("shop",))
    assert ShopEventOffer.objects.filter(event=event).count() == 1  # switching off kept the list
    assert [p["name"] for p in client().get(url).json()["products"]] == ["Sticker"]
    type(event).objects.filter(pk=event.pk).update(status="cancelled")
    assert client().get(url).status_code == 404


def test_buying_an_offered_item_is_an_ordinary_shop_order_with_event_pickup():
    space = _space("offer-checkout")
    sm, buyer = manager(space), member(space)
    event = open_event(space)
    _row, variant = product(space, sm, name="Hoodie", price="30.00", stock=4, kind="merch")
    assert _offer(space, sm, event, variant).status_code == 200
    offered = client().get(_public_url(space, event)).json()
    placed = client(buyer).post(f"/api/v1/public/m/{space.slug}/shop/orders/", {
        "lines": [line(variant)], "pickup_at": "event", "pickup_event_id": offered["event"]["id"]}, format="json")
    assert placed.status_code == 201, placed.content
    order = ShopOrder.objects.get(pk=placed.json()["order"]["id"])
    assert order.pickup_at == ShopOrder.Pickup.EVENT and order.pickup_event_id == event.pk
    payment = payment_for(order)
    assert payment.amount == Decimal("30.00")
    assert not Payment.objects.filter(makerspace=space, subject_type="event_registration").exists()


def test_offers_never_change_the_registration_charge():
    from tests.events.orders_helpers import ticketed_event, verified
    from tests.events.ticketing_helpers import event_space, signup

    space = event_space("offer-registration")
    Makerspace.objects.filter(pk=space.pk).update(public_site_enabled=True)
    space = switch(space, *BASE, "shop.online", "shop.event_pickup", modules=("shop",))
    space, event, event_staff, ticket = ticketed_event(space, amount=15)
    _row, variant = product(space, event_staff, name="Tote", price="12.00", kind="merch")
    assert _offer(space, event_staff, event, variant).status_code == 200
    guest = verified("offer-guest")
    assert signup(event, guest, ticket_type_id=ticket.pk).status_code == 201
    registration = guest.event_registrations.get()
    charges = Payment.objects.filter(subject_type="event_registration", subject_id=registration.pk)
    assert [row.amount for row in charges] == [Decimal("15.00")]
    assert not Payment.objects.filter(makerspace=space, subject_type="shop_order").exists()
    assert not ShopOrder.objects.filter(makerspace=space).exists()
