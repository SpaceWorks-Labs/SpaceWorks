"""MOD-1: every endpoint of an optional inventory module refuses with `module_disabled` when it is off.

`test_offstate_inventory` proves one smallest surface per module. This proves the REST of each
module's routes (detail, move, contents, complete, approve, download ...) all sit behind the same
gate, that the refusal wins before payload validation, that nothing is written while off, and that
switching the module back on restores the very same rows (data is kept, not purged).
"""
import pytest

from apps.accounts.models import User
from apps.boxes.models import Box
from apps.inventory.models import InventoryProduct
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_registry import core_module_keys
from apps.operations.models import QrPrintBatch, StockTransfer, StocktakeSession
from tests.return_helpers import authenticated_client, make_user

pytestmark = pytest.mark.django_db

ADD_ONS = ("containers", "stock_transfers", "stocktake", "qr_print_batches", "bulk_import")
CORE = frozenset(core_module_keys())


def _build(slug):
    space = Makerspace.objects.create(
        name=slug, slug=slug, enabled_modules=sorted(CORE | set(ADD_ONS)), public_inventory_enabled=True)
    root = make_user(f"{slug}-root", role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE)
    box = Box.objects.create(makerspace=space, label="Shelf")
    product = InventoryProduct.objects.create(
        makerspace=space, name="Vise", total_quantity=5, available_quantity=5, is_public=True)
    transfer = StockTransfer.objects.create(
        makerspace=space, source_makerspace=space, destination_makerspace=space, reason="seed")
    stocktake = StocktakeSession.objects.create(makerspace=space, started_by=root)
    batch = QrPrintBatch.objects.create(makerspace=space, title="Seed", created_by=root)
    return space, authenticated_client(root), box, product, transfer, stocktake, batch


def _routes(space, box, transfer, stocktake, batch):
    base = f"/api/v1/admin/makerspace/{space.id}"
    return {
        "containers": [
            ("get", f"{base}/containers", None), ("post", f"{base}/containers", {}),
            ("get", f"/api/v1/admin/containers/{box.id}", None),
            ("patch", f"/api/v1/admin/containers/{box.id}", {"label": "X"}),
            ("post", f"/api/v1/admin/containers/{box.id}/move", {"label": "X"}),
            ("get", f"/api/v1/admin/containers/{box.id}/contents", None),
            ("get", f"/api/v1/admin/containers/{box.id}/history", None),
        ],
        "stock_transfers": [
            ("get", f"{base}/stock-transfers", None), ("post", f"{base}/stock-transfers", {}),
            ("get", f"/api/v1/admin/stock-transfers/{transfer.id}", None),
        ],
        "stocktake": [
            ("get", f"{base}/stocktakes", None), ("post", f"{base}/stocktakes", {}),
            ("get", f"/api/v1/admin/stocktakes/{stocktake.id}", None),
            ("post", f"/api/v1/admin/stocktakes/{stocktake.id}/count-lines", {}),
            ("post", f"/api/v1/admin/stocktakes/{stocktake.id}/resolve-scan", {}),
            ("post", f"/api/v1/admin/stocktakes/{stocktake.id}/complete", None),
            ("post", f"/api/v1/admin/stocktakes/{stocktake.id}/approve", None),
            ("post", f"/api/v1/admin/stocktakes/{stocktake.id}/apply-adjustments", None),
        ],
        "qr_print_batches": [
            ("get", f"{base}/qr-print-batches", None), ("post", f"{base}/qr-print-batches", {"title": "x"}),
            ("get", f"/api/v1/admin/qr-print-batches/{batch.id}", None),
            ("post", f"/api/v1/admin/qr-print-batches/{batch.id}/items", {}),
            ("get", f"/api/v1/admin/qr-print-batches/{batch.id}/download", None),
        ],
        "bulk_import": [
            ("post", f"{base}/inventory/import/preview", {"rows": []}),
            ("post", f"{base}/inventory/import/apply", {"rows": []}),
            ("post", f"{base}/inventory/import/sheet", {}),
            ("post", f"{base}/inventory/import/jobs", {"rows": [], "mode": "apply"}),
        ],
    }


def _call(client, method, url, body):
    return getattr(client, method)(url, body, format="json") if body is not None else getattr(client, method)(url)


@pytest.mark.parametrize("module", ADD_ONS)
def test_every_route_of_the_module_is_refused_when_off_writes_nothing_and_on_restores_it(module):
    space, client, box, product, transfer, stocktake, batch = _build(f"mod1-off-{module.replace('_', '-')}")
    routes = _routes(space, box, transfer, stocktake, batch)[module]
    counts_before = (Box.objects.count(), StockTransfer.objects.count(),
                     StocktakeSession.objects.count(), QrPrintBatch.objects.count(),
                     InventoryProduct.objects.count())

    space.enabled_modules = [key for key in space.enabled_modules if key != module]
    space.save(update_fields=["enabled_modules"])

    for method, url, body in routes:
        response = _call(client, method, url, body)
        assert response.status_code == 404, (method, url, response.status_code, getattr(response, "data", None))
        assert response.data["code"] == "module_disabled", (method, url, response.data)
        assert response.data["module"] == module, (method, url, response.data)
    assert counts_before == (Box.objects.count(), StockTransfer.objects.count(),
                             StocktakeSession.objects.count(), QrPrintBatch.objects.count(),
                             InventoryProduct.objects.count())
    box.refresh_from_db()
    assert box.label == "Shelf"  # the refused PATCH/move changed nothing

    space.enabled_modules = sorted(set(space.enabled_modules) | {module})
    space.save(update_fields=["enabled_modules"])
    for method, url, body in routes:
        response = _call(client, method, url, body)
        code = (getattr(response, "data", None) or {}).get("code") if hasattr(response, "data") else None
        assert code != "module_disabled", (method, url)
    # Data was kept through the off period: same rows, same ids.
    assert Box.objects.filter(pk=box.pk).exists() and StockTransfer.objects.filter(pk=transfer.pk).exists()
    assert StocktakeSession.objects.filter(pk=stocktake.pk).exists() and QrPrintBatch.objects.filter(pk=batch.pk).exists()


def test_turning_one_add_on_off_leaves_the_others_and_the_core_catalogue_working():
    space, client, box, product, transfer, stocktake, batch = _build("mod1-off-isolated")
    space.enabled_modules = [key for key in space.enabled_modules if key != "stocktake"]
    space.save(update_fields=["enabled_modules"])
    base = f"/api/v1/admin/makerspace/{space.id}"
    assert client.get(f"{base}/stocktakes").data["code"] == "module_disabled"
    assert client.get(f"{base}/containers").status_code == 200
    assert client.get(f"{base}/stock-transfers").status_code == 200
    assert client.get(f"{base}/inventory").status_code == 200
    assert client.get(f"/api/v1/admin/inventory/{product.id}").status_code == 200
