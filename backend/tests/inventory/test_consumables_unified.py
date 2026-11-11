"""MI-40: one staff consumables list across items, machine consumables and pools."""

from decimal import Decimal

import pytest

from apps.machines.models import Machine, MachineConsumable, MachineConsumablePool, MachineType
from apps.procurement.models import ToBuyItem
from tests.return_helpers import authenticated_client, make_member, make_product, make_space, make_user

pytestmark = pytest.mark.django_db


def url(space):
    return f"/api/v1/admin/makerspace/{space.pk}/consumables"


def seed(slug):
    space = make_space(slug)
    space.enabled_features = sorted(set(space.enabled_features or []) | {"inventory.tobuy", "machines.tobuy", "inventory.consumables"})
    space.save(update_fields=["enabled_features"])
    staff = make_member(f"{slug}-staff", space)
    item = make_product(space, name="Glue sticks", is_consumable=True, reorder_point=5,
                        available_quantity=4, total_quantity=4, is_public=False)
    make_product(space, name="Drill")  # lendable, never listed
    machine_type = MachineType.objects.filter(makerspace__isnull=True).exclude(slug="3d_printer").first()
    machine = Machine.objects.create(makerspace=space, machine_type=machine_type, name="Cutter")
    grams = MachineConsumable.objects.create(machine=machine, measurement="grams", label="Wax",
                                             remaining=Decimal("80"), low_threshold=Decimal("10"))
    pool = MachineConsumablePool.objects.create(
        makerspace=space, material="PLA", color="Red", initial_grams=Decimal("1000"),
        remaining_grams=Decimal("900"), low_threshold_grams=Decimal("100"))
    return space, staff, item, grams, pool


def test_lists_every_consumable_kind_low_first():
    space, staff, item, grams, pool = seed("cons-list")
    response = authenticated_client(staff).get(url(space))
    assert response.status_code == 200, response.content
    rows = response.json()["results"]
    assert [(row["source"], row["id"]) for row in rows][0] == ("item", item.pk)
    assert {(row["source"], row["id"]) for row in rows} == {("item", item.pk), ("machine", grams.pk), ("pool", pool.pk)}
    assert rows[0]["status"] == "low"
    low = authenticated_client(staff).get(url(space), {"status": "low"}).json()["results"]
    assert [row["id"] for row in low] == [item.pk]


def test_open_to_buy_is_linked_and_other_tenants_are_hidden():
    space, staff, item, _grams, _pool = seed("cons-open")
    to_buy = ToBuyItem.objects.create(makerspace=space, kind="hardware", name="Glue", quantity=1,
                                      source_product=item)
    rows = authenticated_client(staff).get(url(space)).json()["results"]
    assert next(row for row in rows if row["source"] == "item")["open_to_buy_id"] == to_buy.pk
    # The item row's purchase is an inventory row: its switch alone hides it (#128 C-9).
    space.enabled_features = [key for key in space.enabled_features if key != "inventory.tobuy"]
    space.save(update_fields=["enabled_features"])
    rows = authenticated_client(staff).get(url(space)).json()["results"]
    assert next(row for row in rows if row["source"] == "item")["open_to_buy_id"] is None
    other, *_ = seed("cons-other")
    assert authenticated_client(staff).get(url(other)).status_code == 404


def test_members_cannot_list_and_use_logs_through_availability():
    space, staff, item, _grams, _pool = seed("cons-use")
    member = make_user("cons-use-member", access_status="active")
    assert authenticated_client(member).get(url(space)).status_code in (401, 403, 404)
    response = authenticated_client(staff).post(f"{url(space)}/{item.pk}/use", {"quantity": 3, "note": "class"},
                                                format="json")
    assert response.status_code == 200, response.content
    assert response.json()["remaining"] == "1"
    item.refresh_from_db()
    assert item.available_quantity == 1
    assert authenticated_client(staff).post(f"{url(space)}/{item.pk}/use", {"quantity": 5},
                                            format="json").status_code == 400


def test_consumables_never_reach_the_public_catalogue():
    space, *_ = seed("cons-public")
    space.public_site_enabled = True
    space.public_inventory_enabled = True
    space.save(update_fields=["public_site_enabled", "public_inventory_enabled"])
    make_product(space, name="Visible glue", is_consumable=True, is_public=True)
    response = authenticated_client(make_user("cons-public-anon")).get(f"/api/v1/public/{space.slug}/inventory/")
    names = [row["name"] for row in response.json().get("results", [])]
    assert "Visible glue" not in names
    assert "is_consumable" not in response.content.decode()


def test_switch_off_hides_the_screen_and_refuses_the_flag():
    space, staff, item, _grams, _pool = seed("cons-switch")
    space.enabled_features = [key for key in space.enabled_features if key != "inventory.consumables"]
    space.save(update_fields=["enabled_features"])
    assert authenticated_client(staff).get(url(space)).status_code == 404
    other = make_product(space, name="Tape")
    response = authenticated_client(staff).patch(f"/api/v1/admin/inventory/{other.pk}", {"is_consumable": True},
                                                 format="json")
    assert response.status_code in (400, 404)
    other.refresh_from_db()
    assert other.is_consumable is False
