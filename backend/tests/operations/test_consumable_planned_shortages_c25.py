"""Open item C25: upcoming events/bookings short of planned consumables (read-only roll-up)."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.events.models import Event
from apps.inventory.models import InventoryProduct
from apps.makerspaces.models import MakerspaceMembership
from apps.operations.consumable_shortages import planned_shortages
from tests.operations.test_consumable_context_reports import setup_activity
from tests.test_request_workflow import make_member, make_space

pytestmark = pytest.mark.django_db(transaction=True)


def _get(actor, space):
    client = APIClient()
    client.force_authenticate(actor)
    return client.get(reverse("admin-consumable-planned-shortages", kwargs={"makerspace_id": space.pk}))


def test_lists_event_and_booking_shortages_without_booker_names():
    space, actor, product, event, booking = setup_activity("c25-shortages")
    response = _get(actor, space)
    assert response.status_code == 200
    kinds = {(row["subject_kind"], row["subject_id"]) for row in response.data}
    assert kinds == {("event", event.pk), ("booking", booking.pk)}
    row = next(row for row in response.data if row["subject_kind"] == "event")
    assert (row["product_id"], row["shortage_quantity"], row["replenishment_quantity"]) == (product.pk, 2, 10)
    assert row["subject_title"] == "Workshop"
    booked = next(row for row in response.data if row["subject_kind"] == "booking")
    # The room name, never the booker's personal name.
    assert booked["subject_title"] == "Room"
    assert "Booker" not in str(response.data)


def test_stocked_product_and_past_activities_are_not_listed():
    space, actor, product, event, booking = setup_activity("c25-stocked")
    InventoryProduct.objects.filter(pk=product.pk).update(available_quantity=100, total_quantity=100)
    assert planned_shortages(actor, space) == []
    InventoryProduct.objects.filter(pk=product.pk).update(available_quantity=1, total_quantity=1)
    past = timezone.now() - timedelta(days=3)
    Event.objects.filter(pk=event.pk).update(starts_at=past, ends_at=past + timedelta(hours=1))
    assert {row["subject_kind"] for row in planned_shortages(actor, space)} == {"booking"}


def test_module_and_feature_off():
    space, actor, product, event, booking = setup_activity("c25-modules")
    space.enabled_modules = [key for key in space.enabled_modules if key != "events"]
    space.save(update_fields=["enabled_modules"])
    assert {row["subject_kind"] for row in _get(actor, space).data} == {"booking"}
    space.enabled_features = [key for key in space.enabled_features if key != "inventory.consumables"]
    space.save(update_fields=["enabled_features"])
    assert _get(actor, space).status_code in (403, 404)


def test_role_without_inventory_and_foreign_space_are_refused():
    space, actor, product, event, booking = setup_activity("c25-roles")
    machines = make_member("c25-machines", space,
        membership_role=MakerspaceMembership.Role.MACHINE_MANAGER, role=User.Role.REQUESTER)
    assert _get(machines, space).status_code in (403, 404)
    foreign = make_space("c25-foreign")
    outsider = make_member("c25-outsider", foreign)
    assert _get(outsider, space).status_code == 404


def test_inventory_manager_without_event_authority_sees_no_event_rows():
    space, actor, product, event, booking = setup_activity("c25-inventory")
    inventory = make_member("c25-inventory-manager", space,
        membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER, role=User.Role.REQUESTER)
    response = _get(inventory, space)
    assert response.status_code == 200
    # Each activity is re-checked with its own view permission and skipped when refused.
    assert all(row["subject_kind"] != "event" for row in response.data)
