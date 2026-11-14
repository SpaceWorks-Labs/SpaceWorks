"""Cross-transport API and control creators use the same last product slot."""
from copy import copy
from itertools import combinations_with_replacement

import pytest
from django.db import connection
from django.test import Client
from django.urls import reverse

from apps.boxes.models import Box
from apps.inventory.models import InventoryProduct
from apps.admin_api.bulk_import import preview_import
from apps.inventory.admin_bulk_import import SESSION_KEY
from tests.inventory import test_alternative_creators_cx7_p4a as api
from tests.inventory.transfer_quota_helpers_cx7 import payload
from tests.limits_0120.admin_capacity_helpers_cx7 import bound_form, row_for, form_errors
from tests.makerspaces.test_daily_delivery_creator_races_cx7 import race
from tests.accounts.reauth_helpers import force_recent_control_login
from tests.r2_superadmin_local.helpers import superadmin

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_bulk_import,
              pytest.mark.area_stock_transfers]
KINDS = ["ordinary", "scanner", "import", "file_import", "procurement", "restore", "transfer",
         "control_add", "control_restore", "control_import", "control_transfer"]
# P4a covers ordinary API pairings already; this closes pairings involving a
# transfer or a control creator, including different native/browser transports.
PAIRS = [pair for pair in combinations_with_replacement(KINDS, 2)
         if any(k.startswith("control_") or k == "transfer" for k in pair)]


def control_command(space, actor, kind, index, source, destination):
    caller = Client()
    force_recent_control_login(caller, actor)
    if kind == "control_transfer":
        url = reverse("admin:operations_stocktransfer_add")
        data = {"source_makerspace": space.pk, "destination_makerspace": space.pk,
                "product": source.pk, "quantity": 1, "reason": "P5 mixed quota",
                "destination_container": destination.pk}
    elif kind == "control_import":
        rows = [{"name": f"Control import {index}", "total_quantity": "1", "available_quantity": "1"}]
        preview = preview_import(space, rows, {})
        assert preview["valid"] is True
        session = caller.session
        session[SESSION_KEY] = {"makerspace_id": space.pk, "rows": rows, "mapping": preview["mapping"]}
        session.save()
        url, data = reverse("admin:inventory_inventoryproduct_bulk_import"), {"apply": "1"}
    else:
        row = row_for("products", space, f"Control product {index}")
        if kind == "control_restore":
            row.is_archived = True
            row.save()
            original = copy(row)
            original.is_archived = False
            _, _, _, data = bound_form(original, actor, instance=original)
            url = reverse("admin:inventory_inventoryproduct_change", args=[row.pk])
        else:
            _, _, _, data = bound_form(row, actor)
            url = reverse("admin:inventory_inventoryproduct_add")
        page = caller.get(url)
        assert page.status_code == 200
        for inline in page.context["inline_admin_formsets"]:
            prefix = inline.formset.prefix
            data.update({f"{prefix}-TOTAL_FORMS": "0", f"{prefix}-INITIAL_FORMS": "0",
                         f"{prefix}-MIN_NUM_FORMS": "0", f"{prefix}-MAX_NUM_FORMS": "1000"})
    def send():
        response = caller.post(url, {**data, "_save": "Save"})
        if response.status_code == 302:
            return True, "created"
        assert response.status_code == 200
        form = response.context["form"] if kind in {"control_import", "control_transfer"} else response.context["adminform"].form
        assert [code for code, _ in form_errors(form)] == ["limit_reached"]
        return False, "limit_reached"
    return send


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kinds", PAIRS)
@pytest.mark.parametrize("surfaces", [("browser", "browser"), ("browser", "apple"), ("browser", "android")])
def test_transfer_control_and_api_creators_have_exactly_one_last_slot(kinds, surfaces, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space = api.world(settings)
    space.enabled_modules = sorted(set(space.enabled_modules) | {"stock_transfers"})
    space.resource_limit_overrides = {"products": 2}
    space.save(update_fields=["enabled_modules", "resource_limit_overrides"])
    source = InventoryProduct.objects.create(makerspace=space, name="Transfer source",
        total_quantity=10, available_quantity=10)
    boxes = [Box.objects.create(makerspace=space, label=f"P5 target {i}") for i in range(2)]
    transports = {surfaces[i] for i, kind in enumerate(kinds) if not kind.startswith("control_")}
    callers = {surface: api.callers(space, surface, settings, monkeypatch) for surface in sorted(transports)}
    root = superadmin("p5-product-control")
    commands = []
    for index, kind in enumerate(kinds):
        if kind.startswith("control_"):
            commands.append(control_command(space, root, kind, index, source, boxes[index]))
            continue
        cmd = ("post", reverse("stock-transfers", args=[space.pk]), payload(source, boxes[index]), 201) if kind == "transfer" else api.command(space, kind, index)
        def send(index=index, cmd=cmd):
            response = api.send(callers[surfaces[index]][index], cmd)
            if response.status_code == cmd[3]:
                return True, "created"
            assert (response.status_code, response.json()["code"]) == (400, "limit_reached")
            return False, "limit_reached"
        commands.append(send)
    assert sorted(race(lambda index: commands[index]())) == [(False, "limit_reached"), (True, "created")]
    assert InventoryProduct.objects.filter(makerspace=space, is_archived=False).count() == 2
