"""A transfer actually moves the asset and records its child line; off never starts a move."""
import pytest
from django.urls import reverse

from apps.boxes.models import Box
from apps.inventory.models import InventoryAsset
from apps.operations.models import StockTransfer
from tests.modules.switch_matrix_object_helpers import object_world
from tests.operations.route_support_cx11b_g4 import contains, cycle, outsider, send
from tests.return_helpers import make_product

pytestmark = [pytest.mark.django_db, pytest.mark.area_stock_transfers, pytest.mark.area_inventory]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["stock_transfers", "loans.enabled"])
@pytest.mark.parametrize("name,method", [("stock-transfers", "GET"), ("stock-transfers", "POST"), ("stock-transfer-detail", "GET")])
def test_transfer_route_retains_subject_and_moves_the_selected_asset(native, key, name, method):
    space, client, objects = object_world(native)
    source = objects["box"]
    destination = Box.objects.create(makerspace=space, label="Destination shelf")
    product = make_product(space, tracking_mode="individual", total_quantity=1, available_quantity=1)
    asset = InventoryAsset.objects.create(makerspace=space, product=product, asset_tag="G4-ASSET", box=source)
    row = objects["transfer"]
    kwargs = {"makerspace_id": space.pk} if name == "stock-transfers" else {"pk": row.pk}
    url = reverse(name, kwargs=kwargs)
    body = {"source_container_id": source.pk, "destination_container_id": destination.pk,
            "reason": "Move to teaching shelf", "lines": [{"asset_id": asset.pk, "quantity": 1}]}

    def check(response):
        if method == "GET":
            if name == "stock-transfers":
                contains(response, row.pk)
            else:
                assert (response.data["id"], response.data["reason"]) == (row.pk, "Retained transfer")
            asset.refresh_from_db()
            assert asset.box_id == source.pk
        else:
            moved = StockTransfer.objects.get(pk=response.data["id"])
            asset.refresh_from_db()
            assert asset.box_id == destination.pk
            assert (moved.source_container_id, moved.destination_container_id, moved.reason) == (source.pk, destination.pk, body["reason"])
            line = moved.lines.get()
            assert (line.asset_id, line.product_id, line.quantity) == (asset.pk, None, 1)
            assert StockTransfer.objects.filter(makerspace=space).count() == 2
    foreign = outsider(native)
    cycle(space, key, lambda: send(client, method, url, body if method == "POST" else {}), check,
          on=(201 if method == "POST" else 200, None), refusal_key="stock_transfers",
          audit=("stock_transfer.applied",) if method == "POST" else (),
          foreign=lambda: send(foreign, method, url, body if method == "POST" else {}), foreign_native=native)
