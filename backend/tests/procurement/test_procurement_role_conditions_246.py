"""Decision 246: To-Buy procurement across every built-in role, replay of money/stock moves and isolation.

The hardware stream belongs to `manage_makerspace` or `edit_inventory` (`procurement/access.py`); the
printing stream to `manage_printing` (implied by `manage_machines`). Expectations are derived from
`ROLE_CATALOG`. Marking an item bought writes one ledger expense once; moving a received item into
inventory stamps it once and raises stock once.
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.inventory.models import InventoryProduct
from apps.makerspaces.role_catalog import ROLE_BY_SLUG, ROLE_CATALOG
from apps.payments.models_ledger_entries import LedgerEntry
from apps.procurement.models import ToBuyItem
from tests.fixed_roles.helpers import staff_account
from tests.procurement.test_mark_bought import space_with
from tests.return_helpers import authenticated_client
from tests.test_procurement_move_to_inventory import create_payload, received_item

pytestmark = pytest.mark.django_db
SLUGS = [role.slug for role in ROLE_CATALOG]
HARDWARE_ACTIONS = {"manage_makerspace", "edit_inventory"}
ANY_STREAM = HARDWARE_ACTIONS | {"manage_printing", "manage_machines"}


def _holds(slug, wanted):
    return bool(set(ROLE_BY_SLUG[slug].granted_actions) & wanted)


def _list(space):
    return f"/api/v1/procurement/makerspace/{space.pk}/to-buy"


def _hardware_item(space, **kw):
    return ToBuyItem.objects.create(makerspace=space, kind="hardware", name="Glue", quantity=4, **kw)


@pytest.mark.parametrize("slug", SLUGS)
def test_hardware_rows_are_visible_and_writable_only_with_a_hardware_action(slug):
    space = space_with(f"pr-{slug}".replace("_", "-"))
    item = _hardware_item(space)
    client = authenticated_client(staff_account(space, f"pr-actor-{slug}", slug))
    listed = client.get(_list(space))
    patched = client.patch(f"/api/v1/procurement/to-buy/{item.pk}", {"name": "Edited"}, format="json")
    created = client.post(_list(space) + "?kind=hardware", {"name": "New", "quantity": 1}, format="json")
    if _holds(slug, HARDWARE_ACTIONS):
        assert listed.status_code == 200 and item.pk in [row["id"] for row in listed.json()]
        assert patched.status_code == 200, patched.content
        assert created.status_code == 201 and created.json()["kind"] == "hardware"
    else:
        assert not listed.status_code >= 500
        assert item.pk not in [row["id"] for row in listed.json()] if listed.status_code == 200 else True
        assert patched.status_code in (403, 404)
        item.refresh_from_db()
        assert item.name == "Glue"
        if not _holds(slug, ANY_STREAM):
            assert created.status_code in (403, 404)
            assert ToBuyItem.objects.filter(makerspace=space).count() == 1


@pytest.mark.parametrize("slug", SLUGS)
def test_mark_bought_follows_the_stream_authority_and_writes_one_expense(slug):
    space = space_with(f"prb-{slug}".replace("_", "-"))
    item = _hardware_item(space)
    actor = staff_account(space, f"prb-actor-{slug}", slug)
    body = {"amount": "20.00", "method": "cash", "reference": f"R-{slug}"}
    response = authenticated_client(actor).post(f"/api/v1/procurement/to-buy/{item.pk}/mark-bought", body, format="json")
    entries = LedgerEntry.objects.filter(source_kind="procurement.to_buy", source_id=str(item.pk))
    if _holds(slug, HARDWARE_ACTIONS):
        assert response.status_code == 200, response.content
        assert entries.count() == 1 and entries.get().amount == Decimal("20.00")
    else:
        assert response.status_code in (403, 404)
        assert not entries.exists()
        assert not AuditLog.objects.filter(makerspace=space, actor=actor, action="procurement.bought").exists()


@pytest.mark.parametrize("body", [{}, {"amount": "-1", "method": "cash"}, {"amount": "abc", "method": "cash"},
                                  {"amount": "10", "method": "barter"}, {"amount": "10"}])
def test_mark_bought_validation_records_no_expense(body):
    space = space_with("prb-valid")
    item = _hardware_item(space)
    boss = authenticated_client(staff_account(space, "prb-valid-boss", "space_manager"))
    response = boss.post(f"/api/v1/procurement/to-buy/{item.pk}/mark-bought", body, format="json")
    assert response.status_code == 400
    assert not LedgerEntry.objects.filter(source_kind="procurement.to_buy").exists()
    item.refresh_from_db()
    assert item.status != "received"


def test_marking_bought_twice_changes_nothing_the_second_time():
    space = space_with("prb-twice")
    item = _hardware_item(space)
    boss = authenticated_client(staff_account(space, "prb-twice-boss", "space_manager"))
    body = {"amount": "9.00", "method": "cash"}
    url = f"/api/v1/procurement/to-buy/{item.pk}/mark-bought"
    assert boss.post(url, body, format="json").status_code == 200
    assert boss.post(url, body, format="json").status_code in (400, 409)
    assert LedgerEntry.objects.filter(source_kind="procurement.to_buy", source_id=str(item.pk)).count() == 1
    assert AuditLog.objects.filter(action="procurement.bought", target_id=str(item.pk)).count() == 1


def test_moving_a_received_item_into_inventory_is_one_shot():
    space = space_with("prm-twice")
    item = received_item(space, quantity=3)
    boss = authenticated_client(staff_account(space, "prm-twice-boss", "space_manager"))
    url = f"/api/v1/procurement/to-buy/{item.pk}/move-to-inventory"
    first = boss.post(url, create_payload(quantity=3), format="json")
    second = boss.post(url, create_payload(quantity=3), format="json")
    assert first.status_code == 200, first.content
    assert second.status_code in (400, 409)
    assert InventoryProduct.objects.filter(makerspace=space, name="Soldering iron").count() == 1
    assert InventoryProduct.objects.get(makerspace=space, name="Soldering iron").total_quantity == 3


def test_a_pending_item_cannot_be_moved_into_inventory():
    space = space_with("prm-pending")
    item = _hardware_item(space)
    boss = authenticated_client(staff_account(space, "prm-pending-boss", "space_manager"))
    response = boss.post(f"/api/v1/procurement/to-buy/{item.pk}/move-to-inventory", create_payload(), format="json")
    assert response.status_code in (400, 409)
    assert not InventoryProduct.objects.filter(makerspace=space).exists()


def test_another_spaces_manager_and_anonymous_cannot_see_or_move_items():
    mine, theirs = space_with("pr-iso-a"), space_with("pr-iso-b")
    item = _hardware_item(mine)
    outsider = authenticated_client(staff_account(theirs, "pr-iso-out", "space_manager"))
    assert outsider.get(f"/api/v1/procurement/to-buy/{item.pk}").status_code in (403, 404)
    assert outsider.post(f"/api/v1/procurement/to-buy/{item.pk}/mark-bought", {"amount": "1", "method": "cash"},
                         format="json").status_code in (403, 404)
    listed = outsider.get(_list(mine))
    assert listed.status_code in (200, 403, 404)
    if listed.status_code == 200:
        assert listed.json() == []
    assert APIClient().get(_list(mine)).status_code in (401, 403)
    assert not LedgerEntry.objects.filter(source_kind="procurement.to_buy").exists()


def test_both_streams_are_hidden_when_their_switches_are_off():
    space = space_with("pr-off", features=())
    # Switches default ON for a new space, so "off" must be set explicitly (space_with only adds).
    space.enabled_features = [k for k in space.enabled_features if k not in ("inventory.tobuy", "machines.tobuy")]
    space.save(update_fields=["enabled_features"])
    boss = authenticated_client(staff_account(space, "pr-off-boss", "space_manager"))
    _hardware_item(space)
    response = boss.get(_list(space))
    assert response.status_code in (403, 404) or response.json() == []
    created = boss.post(_list(space), {"name": "x", "quantity": 1}, format="json")
    assert created.status_code in (403, 404)
