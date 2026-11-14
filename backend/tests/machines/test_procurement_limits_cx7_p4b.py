"""Received printers consume machine capacity through the real procurement workflow."""
import pytest
from django.db import connection
from rest_framework.exceptions import APIException

from apps.audit.models import AuditLog
from apps.machines.models import Machine
from apps.procurement.models import ToBuyItem
from apps.procurement.services import move_to_printing
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.procurement.test_mark_bought import space_with
from tests.return_helpers import make_member
from tests.test_procurement_move_to_inventory import received_item, move_printing_url

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines, pytest.mark.area_inventory]


def setup():
    space = space_with("cx7-p4b-printer-received")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"machines", "machine_service"})
    space.resource_limit_overrides = {"machines": 1}
    space.save(update_fields=["enabled_modules", "resource_limit_overrides"])
    items = [received_item(space, kind="printing", name=f"Printer {index}") for index in range(2)]
    return space, items


def snapshot():
    return [list(model.objects.order_by("pk").values()) for model in (Machine, ToBuyItem, AuditLog)]


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_procurement_printer_max_next_refusal_keeps_received_source(surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, items = setup()
    client = callers(space, surface, settings, monkeypatch)[0]
    body = {"target": "printer", "name": "Received printer", "model": "MK4"}
    assert client.post(move_printing_url(items[0]), body, format="json").status_code == 200
    before = snapshot()
    refused = client.post(move_printing_url(items[1]), body, format="json")
    assert (refused.status_code, refused.json()["code"]) == (400, "limit_reached")
    assert snapshot() == before


@pytest.mark.django_db(transaction=True)
def test_independent_procurement_items_racing_for_last_machine_slot_admit_one(settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space, items = setup()
    actor = make_member("cx7-p4b-receiver", space)
    assert race_creators(lambda index: move_to_printing(actor, items[index], target="printer",
        data={"name": f"Printer {index}", "model": "MK4"})) == [(201, "created"), (400, "limit_reached")]
    assert Machine.objects.filter(makerspace=space).count() == 1
    assert ToBuyItem.objects.filter(makerspace=space, moved_to_inventory_at__isnull=False).count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="procurement.moved_to_printing").count() == 1


def test_received_printer_requires_machines_and_restores_without_losing_source(settings):
    settings.MANAGED_PLANS_ENABLED = False
    space, items = setup()
    actor = make_member("cx7-p4b-receiver", space)
    space.enabled_modules = [key for key in space.enabled_modules if key != "machines"]
    space.save(update_fields=["enabled_modules"])
    before = snapshot()
    with pytest.raises(APIException) as failure:
        move_to_printing(actor, items[0], target="printer", data={"name": "Printer", "model": "MK4"})
    assert (failure.value.status_code, str(failure.value.detail["code"])) == (404, "module_disabled")
    assert snapshot() == before
    space.enabled_modules.append("machines")
    space.save(update_fields=["enabled_modules"])
    assert move_to_printing(actor, items[0], target="printer", data={"name": "Printer", "model": "MK4"}).pk
