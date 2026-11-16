"""Decision 246: the staff inventory surface across every built-in role, with money-like quantity rules.

Listing needs `view_inventory`; create, edit and quantity adjustment need `edit_inventory`. Quantity math
lives in `inventory/availability.py`, so the invariants asserted here are: buckets never go below zero,
a refused or invalid call changes nothing, and another space's product is 404 before permission.
"""
import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.inventory.models import InventoryProduct
from apps.operations.models import InventoryAdjustment
from apps.makerspaces.role_catalog import ROLE_BY_SLUG, ROLE_CATALOG
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_product, make_space

pytestmark = pytest.mark.django_db
SLUGS = [role.slug for role in ROLE_CATALOG]
NEW = {"name": "Logic Analyzer", "tracking_mode": "quantity", "total_quantity": 4, "available_quantity": 4,
       "description": "USB analyzer", "is_public": True, "public_self_checkout_enabled": False}


def _granted(slug, action):
    return action in ROLE_BY_SLUG[slug].granted_actions


@pytest.mark.parametrize("slug", SLUGS)
def test_list_create_and_adjust_follow_view_and_edit_inventory(slug):
    space = make_space(f"inv-{slug}".replace("_", "-"))
    product = make_product(space, name="Wire", total_quantity=10, available_quantity=10)
    client = authenticated_client(staff_account(space, f"inv-actor-{slug}", slug))
    base = f"/api/v1/admin/makerspace/{space.pk}/inventory"
    listed = client.get(base)
    created = client.post(base, NEW, format="json")
    adjusted = client.post(f"/api/v1/admin/inventory/{product.pk}/adjust-quantity",
                           {"delta_available": -1, "delta_damaged": 1, "delta_lost": 0, "reason": "Count"}, format="json")
    can_edit = _granted(slug, "edit_inventory")
    assert (created.status_code == 201) is can_edit
    assert (adjusted.status_code == 200) is can_edit
    assert (listed.status_code == 200) is (_granted(slug, "view_inventory") or can_edit)
    if not can_edit:
        assert created.status_code in (403, 404) and adjusted.status_code in (403, 404)
        assert InventoryProduct.objects.filter(makerspace=space).count() == 1
        assert not InventoryAdjustment.objects.exists()
        assert not AuditLog.objects.filter(makerspace=space, action__startswith="inventory.").exists()


@pytest.mark.parametrize("delta", [
    {"delta_available": -11, "delta_damaged": 0, "delta_lost": 0},
    {"delta_available": 0, "delta_damaged": -1, "delta_lost": 0},
    {"delta_available": 0, "delta_damaged": 0, "delta_lost": -1},
    {"delta_available": "many", "delta_damaged": 0, "delta_lost": 0},
])
def test_an_adjustment_that_would_go_below_zero_or_is_malformed_changes_nothing(delta):
    space = make_space("inv-floor")
    product = make_product(space, total_quantity=10, available_quantity=10)
    boss = authenticated_client(staff_account(space, "inv-floor-boss", "space_manager"))
    response = boss.post(f"/api/v1/admin/inventory/{product.pk}/adjust-quantity", {**delta, "reason": "Test"}, format="json")
    assert response.status_code in (400, 409)
    product.refresh_from_db()
    assert (product.available_quantity, product.damaged_quantity, product.lost_quantity, product.total_quantity) == (10, 0, 0, 10)
    assert not InventoryAdjustment.objects.exists()


def test_an_adjustment_without_a_reason_is_rejected():
    space = make_space("inv-reason")
    product = make_product(space)
    boss = authenticated_client(staff_account(space, "inv-reason-boss", "space_manager"))
    response = boss.post(f"/api/v1/admin/inventory/{product.pk}/adjust-quantity", {"delta_available": 1}, format="json")
    assert response.status_code == 400


@pytest.mark.parametrize("body", [{}, {"name": ""}, {**NEW, "total_quantity": -1}, {**NEW, "available_quantity": 99},
                                  {**NEW, "tracking_mode": "telepathy"}])
def test_create_validation_rejects_bad_names_quantities_and_modes(body):
    space = make_space("inv-valid")
    boss = authenticated_client(staff_account(space, "inv-valid-boss", "space_manager"))
    response = boss.post(f"/api/v1/admin/makerspace/{space.pk}/inventory", body, format="json")
    assert response.status_code == 400
    assert not InventoryProduct.objects.filter(makerspace=space).exists()


def test_another_spaces_product_is_404_for_read_edit_and_adjust_and_anonymous_is_refused():
    mine, theirs = make_space("inv-iso-a"), make_space("inv-iso-b")
    foreign = make_product(theirs, name="Theirs")
    boss = authenticated_client(staff_account(mine, "inv-iso-boss", "space_manager"))
    assert boss.get(f"/api/v1/admin/inventory/{foreign.pk}").status_code == 404
    assert boss.patch(f"/api/v1/admin/inventory/{foreign.pk}", {"name": "Taken"}, format="json").status_code == 404
    assert boss.post(f"/api/v1/admin/inventory/{foreign.pk}/adjust-quantity",
                     {"delta_available": 1, "reason": "x"}, format="json").status_code == 404
    assert boss.get(f"/api/v1/admin/makerspace/{theirs.pk}/inventory").status_code in (403, 404)
    assert APIClient().get(f"/api/v1/admin/makerspace/{mine.pk}/inventory").status_code in (401, 403)
    foreign.refresh_from_db()
    assert foreign.name == "Theirs" and foreign.available_quantity == 10
