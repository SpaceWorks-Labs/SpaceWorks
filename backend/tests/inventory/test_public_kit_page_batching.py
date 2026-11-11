"""Review fix: a public kit page fetches its products in one query, not one per kit."""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIRequestFactory

from apps.inventory import equipment_public_kits as public
from apps.inventory.models_equipment_proposals import EquipmentKitTemplate, EquipmentKitVersion
from tests.return_helpers import make_product, make_space

pytestmark = pytest.mark.django_db


def _kits(maker, count, products):
    for index in range(count):
        template = EquipmentKitTemplate.objects.create(makerspace=maker, name=f"Kit {index}",
                                                       published_for_contexts=True)
        EquipmentKitVersion.objects.create(template=template, version=1, name=template.name, lines=[
            {"product_id": products[index % len(products)].pk, "quantity_per_person": 1, "kind": "returnable"}])


def _product_queries(maker):
    request = APIRequestFactory().get("/kits/")
    from rest_framework.request import Request
    with CaptureQueriesContext(connection) as queries:
        response = public.kit_page(Request(request), maker)
    sql = [q["sql"] for q in queries.captured_queries if 'FROM "inventory_inventoryproduct"' in q["sql"]
           and "inventory_equipmentkitversion" not in q["sql"]]
    return response, len(sql)


def test_product_lookup_is_one_query_for_the_whole_page(monkeypatch):
    monkeypatch.setattr(public, "module_enabled", lambda *_: True)
    monkeypatch.setattr(public, "feature_enabled", lambda *_: True)
    maker = make_space("kit-batch")
    tools = [make_product(maker, name=f"Tool {i}", is_public=True) for i in range(3)]
    _kits(maker, 24, tools)
    response, product_queries = _product_queries(maker)
    assert len(response.data["results"]) == 24
    assert product_queries == 1
    names = {line["display_name"] for kit in response.data["results"] for line in kit["lines"]}
    assert names == {"Tool 0", "Tool 1", "Tool 2"}
    first = response.data["results"][0]
    assert public.kit_detail(maker, first["id"]) == first
