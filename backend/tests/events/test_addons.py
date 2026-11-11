"""L6 G30: add-ons with event-local stock and variants; hardware inventory untouched."""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.events.addons import create_addon
from apps.events.models import EventOrder
from apps.inventory.models import InventoryProduct
from tests.events.collab_helpers import client_for
from tests.events.orders_helpers import l6_space, place, quote, ticketed_event, verified

pytestmark = pytest.mark.django_db


def test_addon_stock_and_variants():
    space, event, staff, ticket = ticketed_event(amount=10)
    lunch = create_addon(event, actor=staff, name="Lunch", kind="meal", amount=Decimal(6), stock=1)
    shirt = create_addon(event, actor=staff, name="T-shirt", kind="merch", amount=Decimal(15),
                         variants=[{"label": "M", "stock": 1}, {"label": "L", "stock": 5}])
    medium = shirt.variants.get(label="M")
    buyer = verified("buyer")
    no_size = quote(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 1}],
                    addons=[{"addon_id": shirt.pk, "quantity": 1}])
    assert no_size.data["code"] == "addon_unavailable"
    ok = place(buyer, event, [{"ticket_type_id": ticket.pk, "quantity": 1}],
               addons=[{"addon_id": lunch.pk, "quantity": 1}, {"addon_id": shirt.pk, "variant_id": medium.pk,
                                                                "quantity": 1}])
    assert ok.status_code == 201, ok.data
    assert EventOrder.objects.get().total == Decimal("31.00")
    again = quote(verified("two"), event, [{"ticket_type_id": ticket.pk, "quantity": 1}],
                  addons=[{"addon_id": lunch.pk, "quantity": 1}])
    assert again.data["code"] == "sold_out"
    assert not InventoryProduct.objects.exists()


def test_staff_addon_api_and_feature_switch():
    space = l6_space(features=["events.orders"])
    _space, event, staff, _ticket = ticketed_event(space)
    url = reverse("admin-event-addons", kwargs={"pk": event.pk})
    assert client_for(staff).post(url, {"name": "Kit", "amount": "4.00"}, format="json").status_code == 400
    space.enabled_features = sorted({*space.enabled_features, "events.addons"})
    space.save(update_fields=["enabled_features"])
    created = client_for(staff).post(url, {"name": "Kit", "amount": "4.00", "kind": "kit", "stock": 3,
                                           "variants": [{"label": "Basic", "stock": 2}]}, format="json")
    assert created.status_code == 201, created.data
    listing = client_for(staff).get(url)
    assert listing.data["results"][0]["variants"][0]["remaining"] == 2
    public = client_for(verified("visitor")).get(reverse("public-event-ticket-shop", kwargs={
        "makerspace_slug": space.slug, "public_token": event.public_token}))
    assert public.status_code == 200 and public.data["addons"][0]["sold_out"] is False
    assert "stock" not in public.data["addons"][0]
