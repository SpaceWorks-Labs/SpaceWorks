"""To-Buy reads/writes: both parent streams and retained inventory handoff."""
import csv
import io

import pytest
from django.urls import reverse

from apps.procurement.models import ToBuyItem
from tests.machines.route_support_cx11b_g2 import prove, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_machines]
CASES = [("to-buy-list", "get"), ("to-buy-list", "post"), ("to-buy-detail", "get"),
         ("to-buy-detail", "patch"), ("to-buy-detail", "delete"), ("to-buy-export", "get")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("kind,key", [("hardware", "inventory.tobuy"), ("printing", "machines.tobuy"),
                                     ("printing", "machines"), ("hardware", "loans.enabled")])
@pytest.mark.parametrize("name,method", CASES)
def test_to_buy_route_effect_and_independent_parent_switch(native, kind, key, name, method):
    w = world(native)
    item = ToBuyItem.objects.create(makerspace=w.space, name="Retained G2 purchase", kind=kind,
        quantity=2, machine_type=w.machine_type if kind == "printing" else None, created_by=w.actor)
    args = [item.pk] if name == "to-buy-detail" else [w.space.pk]
    url = reverse(f"procurement:{name}", args=args) + f"?kind={kind}"
    body = {"name": "Restored purchase", "quantity": 3}

    def call(client):
        return getattr(client, method)(url, body if method != "get" else {}, format="json")

    def check(response):
        if name == "to-buy-export":
            table = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
            assert len(table) == 2
            assert (table[1][0], table[1][2], table[1][3]) == (kind, "Retained G2 purchase", "2")
        elif method == "delete":
            assert not ToBuyItem.objects.filter(pk=item.pk).exists()
        elif method in {"post", "patch"}:
            saved = ToBuyItem.objects.get(pk=response.data["id"])
            assert (saved.name, saved.quantity, saved.kind, saved.makerspace_id) == (
                "Restored purchase", 3, kind, w.space.pk)
            assert ToBuyItem.objects.filter(makerspace=w.space).count() == (2 if method == "post" else 1)
        else:
            data = response.data if name == "to-buy-list" else [response.data]
            assert [(r["id"], r["name"], r["quantity"]) for r in data] == [(item.pk, "Retained G2 purchase", 2)]

    def hidden(response):
        if name == "to-buy-export":
            assert len(list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))) == 1
        else:
            assert response.data == []

    # 481/494: browser staff errors conceal; the browser list returns an empty
    # projection outside authority. Native grants still refuse a different tenant (545).
    foreign_list = name == "to-buy-list" and method == "get"
    collection_read = name in {"to-buy-list", "to-buy-export"} and method == "get"
    prove(w, key, call, check, status=201 if method == "post" else 204 if method == "delete" else 200,
          audits={"post": ("procurement.item_added",), "patch": ("procurement.item_updated",),
                  "delete": ("procurement.item_removed",)}.get(method, ()),
          off=(200, None) if collection_read else (404, "capability_disabled" if method == "post" else "not_found"),
          off_check=hidden if collection_read else None, foreign=(403, "permission_denied") if native else (200, None) if foreign_list else (404, "not_found"),
          foreign_check=(lambda r: hidden(r)) if foreign_list else None)
