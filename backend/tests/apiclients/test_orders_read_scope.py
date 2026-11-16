"""L6 G35: `orders:read` signed server reads, keyset-paginated, no contacts."""

import pytest

from apps.events.models import EventOrder
from tests.apiclients.test_staff_reads_lane_f import issue, read
from tests.events.orders_helpers import l6_space, place, ticketed_event, verified

pytestmark = pytest.mark.django_db


@pytest.fixture
def api(settings):
    settings.API_CLIENT_AUTH_REQUIRED = False
    settings.APICLIENT_REQUIRE_NONCE = False
    settings.API_CLIENT_ENC_KEY = __import__("cryptography.fernet", fromlist=["Fernet"]).Fernet.generate_key().decode()


def _space_with_order():
    space = l6_space()
    space.enabled_features = sorted({*space.enabled_features, "events.api_read"})
    space.save(update_fields=["enabled_features"])
    _space, event, _staff, ticket = ticketed_event(space, amount=8)
    place(verified("buyer"), event, [{"ticket_type_id": ticket.pk, "quantity": 2}])
    return space, EventOrder.objects.get()


def test_orders_read_lists_and_details_without_contacts(api):
    space, order = _space_with_order()
    client, secret = issue(space, ["orders:read"])
    listing = read(client, secret, "/api/v1/events/orders/")
    assert listing.status_code == 200, listing.data
    row = listing.data["results"][0]
    assert row["id"] == order.pk and row["total"] == "16.00" and row["seats"] == 2
    assert not {"buyer", "attendee_email", "email"} & set(row)
    detail = read(client, secret, f"/api/v1/events/orders/{order.pk}/")
    assert detail.status_code == 200 and detail.data["lines"][0]["quantity"] == 2


def test_orders_read_needs_its_scope_and_the_switches(api):
    space, order = _space_with_order()
    client, secret = issue(space, ["events:read"])
    assert read(client, secret, "/api/v1/events/orders/").status_code == 401  # registry: missing scope is 401
    client, secret = issue(space, ["orders:read"])
    space.enabled_features = [key for key in space.enabled_features if key != "events.orders"]
    space.save(update_fields=["enabled_features"])
    assert read(client, secret, "/api/v1/events/orders/").status_code == 404
