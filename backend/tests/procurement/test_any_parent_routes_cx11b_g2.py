"""Shared collection admission: sole remaining To-Buy parent off, exact refusal and restoration."""
import csv
import io

import pytest

from apps.procurement.models import ToBuyItem
from tests.machines.route_support_cx11b_g2 import command, prove, toggle, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_machines]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key,kind,other", [("inventory.tobuy", "hardware", "machines.tobuy"),
                                         ("machines.tobuy", "printing", "inventory.tobuy"),
                                         ("loans.enabled", "hardware", "machines.tobuy")])
@pytest.mark.parametrize("name", ["to-buy-list", "to-buy-export", "to-buy-machine-type-options"])
def test_shared_collection_refuses_only_when_its_last_parent_is_disabled(native, key, kind, other, name):
    w = world(native)
    toggle(w.space, other)
    item = ToBuyItem.objects.create(makerspace=w.space, name="Retained sole-stream purchase", kind=kind,
                                   machine_type=w.machine_type if kind == "printing" else None)

    def check(response):
        if name == "to-buy-list":
            assert [(r["id"], r["name"]) for r in response.data] == [(item.pk, "Retained sole-stream purchase")]
        elif name == "to-buy-export":
            data = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
            assert len(data) == 2
            assert data[1][2] == "Retained sole-stream purchase"
        else:
            assert [(r["id"], r["name"]) for r in response.data["results"] if r["id"] == w.machine_type.pk] == [
                (w.machine_type.pk, w.machine_type.name)]

    # 481/494: the browser foreign list keeps its empty projection. A native
    # grant fixed to another tenant is refused before the view in every state (545).
    prove(w, key, lambda c: command(c, f"procurement:{name}", "get", [w.space.pk]), check,
          off=(404, "capability_disabled"), foreign=(403, "permission_denied") if native else (200, None) if name == "to-buy-list" else (404, "not_found"),
          foreign_check=(lambda r: _empty(r)) if name == "to-buy-list" else None)


def _empty(response):
    assert response.data == []
