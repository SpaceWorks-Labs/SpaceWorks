"""MOD-1: the To-Buy refill-consumable endpoint over HTTP (service path is proven in test_auto_tobuy)."""
from decimal import Decimal

import pytest
from django.db import transaction

from apps.audit.models import AuditLog
from apps.machines.models import Machine, MachineConsumable, MachineType
from apps.machines.services_consumables import log_consumption
from apps.procurement.models import ToBuyItem
from tests.return_helpers import authenticated_client, make_member, make_print_manager, make_space as _make_space

pytestmark = pytest.mark.django_db


def _setup(slug):
    space = _make_space(slug)
    space.enabled_features = sorted(set(space.enabled_features or []) | {"inventory.tobuy", "machines.tobuy"})
    space.save(update_fields=["enabled_features"])
    boss = make_member(f"{slug}-boss", space)
    machine = Machine.objects.create(
        makerspace=space, name="Laser", machine_type=MachineType.objects.get(makerspace__isnull=True, slug="laser_cutter"))
    row = MachineConsumable.objects.create(machine=machine, measurement="grams", label="Wipes",
                                           remaining=Decimal("50"), low_threshold=Decimal("10"))
    with transaction.atomic():
        log_consumption(machine, boss, row, Decimal("45"))
    return space, boss, row, ToBuyItem.objects.get(source_consumable=row)


def _url(item):
    return f"/api/v1/procurement/to-buy/{item.pk}/refill-consumable"


def test_refill_needs_received_status_then_credits_exactly_once_and_audits():
    space, boss, row, item = _setup("m1-refill")
    client = authenticated_client(boss)
    assert client.post(_url(item), {"amount": "100"}, format="json").status_code == 400  # not received yet
    ToBuyItem.objects.filter(pk=item.pk).update(status=ToBuyItem.Status.RECEIVED)
    ok = client.post(_url(item), {"amount": "100"}, format="json")
    assert ok.status_code == 200
    row.refresh_from_db()
    assert row.remaining == Decimal("105")
    again = client.post(_url(item), {"amount": "100"}, format="json")  # retry / double click
    assert again.status_code == 400
    row.refresh_from_db()
    assert row.remaining == Decimal("105")
    assert AuditLog.objects.filter(action="procurement.consumable_refilled").count() == 1


@pytest.mark.parametrize("amount", ["0", "-5", "abc", ""])
def test_refill_rejects_non_positive_and_garbage_amounts_without_crediting(amount):
    space, boss, row, item = _setup("m1-refill-amt-" + str(abs(hash(amount)) % 10**5))
    ToBuyItem.objects.filter(pk=item.pk).update(status=ToBuyItem.Status.RECEIVED)
    response = authenticated_client(boss).post(_url(item), {"amount": amount}, format="json")
    assert response.status_code == 400
    row.refresh_from_db()
    assert row.remaining == Decimal("5")
    assert not AuditLog.objects.filter(action="procurement.consumable_refilled").exists()


def test_refill_is_refused_for_other_tenants_signed_out_and_when_machines_tobuy_is_off():
    space, boss, row, item = _setup("m1-refill-ten")
    ToBuyItem.objects.filter(pk=item.pk).update(status=ToBuyItem.Status.RECEIVED)
    other = _make_space("m1-refill-ten-o")
    foreign = authenticated_client(make_member("m1-refill-ten-foreign", other))
    assert foreign.post(_url(item), {"amount": "10"}, format="json").status_code in (403, 404)
    from rest_framework.test import APIClient
    assert APIClient().post(_url(item), {"amount": "10"}, format="json").status_code in (401, 403)
    space.enabled_features = [f for f in space.enabled_features if f != "machines.tobuy"]
    space.save(update_fields=["enabled_features"])
    off = authenticated_client(boss).post(_url(item), {"amount": "10"}, format="json")
    assert off.status_code in (400, 404) and off.data.get("code") != "ok"
    row.refresh_from_db()
    assert row.remaining == Decimal("5")
