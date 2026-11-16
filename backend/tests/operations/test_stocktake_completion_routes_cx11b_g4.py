"""Count resolution, independent approval and actual availability adjustment effects."""
import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.boxes.models import QrCode
from apps.operations.models import InventoryAdjustment, StocktakeLedgerEntry, StocktakeLine, StocktakeSession
from tests.accounts.account_factories import make_staff
from tests.modules.switch_matrix_object_helpers import object_world
from tests.operations.route_support_cx11b_g4 import cycle, outsider, send
from tests.return_helpers import make_product

pytestmark = [pytest.mark.django_db, pytest.mark.area_stocktake, pytest.mark.area_inventory]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["stocktake", "loans.enabled"])
@pytest.mark.parametrize("name", ["stocktake-resolve-scan", "stocktake-approve", "stocktake-apply-adjustments"])
def test_stocktake_terminal_commands_prove_real_effects(native, key, name):
    space, client, objects = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    counter = make_staff(space, username="g4-independent-counter", access_status="active")
    row = objects["stocktake"]
    row.started_by = counter
    row.variance_threshold = 1
    row.approval_required = True
    row.status = "completed" if name.endswith("approve") else "approved" if name.endswith("adjustments") else "counting"
    row.save(update_fields=["started_by", "variance_threshold", "approval_required", "status"])
    product = make_product(space)
    line = StocktakeLine.objects.create(stocktake=row, product=product, expected_quantity=10,
                                       counted_quantity=8, variance_quantity=-2)
    qr = QrCode.objects.create(makerspace=space, target_type="product", target_id=product.pk)
    body = {"payload": qr.payload} if name.endswith("scan") else {}
    url = reverse(name, kwargs={"pk": row.pk})

    def check(response):
        row.refresh_from_db()
        if name.endswith("scan"):
            assert response.data == {"type": "product", "product_id": product.pk, "name": product.name}
        elif name.endswith("approve"):
            assert (row.status, row.approved_by_id) == ("approved", actor.pk)
            assert row.approved_at is not None
        else:
            assert row.status == StocktakeSession.Status.APPLIED
            product.refresh_from_db()
            assert (product.available_quantity, product.total_quantity) == (8, 8)
            ledger = StocktakeLedgerEntry.objects.get(stocktake=row)
            assert (ledger.line_id, ledger.product_id, ledger.bucket, ledger.delta) == (line.pk, product.pk, "available", -2)
            adjustment = InventoryAdjustment.objects.get(stocktake=row)
            assert (adjustment.product_id, adjustment.delta_available, adjustment.created_by_id) == (product.pk, -2, actor.pk)
    foreign = outsider(native)
    audit = () if name.endswith("scan") else ("stocktake.approved",) if name.endswith("approve") else ("stocktake.adjustments_applied",)
    cycle(space, key, lambda: send(client, "POST", url, body), check,
          audit=audit, refusal_key="stocktake", foreign=lambda: send(foreign, "POST", url, body), foreign_native=native)
