"""One report, two independent parent switches; 481/494 staff standing."""
import pytest

from apps.inventory.models import InventoryAsset, InventoryProduct
from apps.warranty.models import Warranty
from tests.machines.route_support_cx11b_g2 import command, prove, rows, toggle, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_machines]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["inventory.warranty", "machines.warranty", "machines", "loans.enabled"])
def test_warranty_report_hides_only_the_disabled_parent_and_restores_same_rows(native, key):
    w = world(native)
    product = InventoryProduct.objects.create(makerspace=w.space, name="Drill", tracking_mode="individual")
    asset = InventoryAsset.objects.create(makerspace=w.space, product=product, asset_tag="G2-REPORT")
    Warranty.objects.create(makerspace=w.space, asset=asset, vendor_name="Asset supplier")
    Warranty.objects.create(makerspace=w.space, machine=w.machine, vendor_name="Machine supplier")
    expected = [("asset", asset.pk, "Asset supplier"), ("machine", w.machine.pk, "Machine supplier")]

    def check(response):
        assert [(r["host_kind"], r["host_id"], r["vendor_name"]) for r in rows(response)] == expected
        assert response.data["count"] == 2

    def hidden(response):
        wanted = expected[1:] if key in {"inventory.warranty", "loans.enabled"} else expected[:1]
        assert [(r["host_kind"], r["host_id"], r["vendor_name"]) for r in rows(response)] == wanted
        assert response.data["count"] == 1

    prove(w, key, lambda c: command(c, "admin-makerspace-warranties", "get", [w.space.pk]), check,
          off=(200, None), off_check=hidden)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key,other", [("inventory.warranty", "machines.warranty"),
                                     ("machines.warranty", "inventory.warranty")])
def test_report_refuses_when_last_warranty_parent_is_off_and_restores_retained_host(native, key, other):
    w = world(native)
    toggle(w.space, other)
    product = InventoryProduct.objects.create(makerspace=w.space, name="Drill", tracking_mode="individual")
    asset = InventoryAsset.objects.create(makerspace=w.space, product=product, asset_tag="G2-LAST")
    subject = asset if key == "inventory.warranty" else w.machine
    host = "asset" if key == "inventory.warranty" else "machine"
    Warranty.objects.create(makerspace=w.space, **{host: subject}, vendor_name="Sole supplier")

    def check(response):
        assert [(r["host_kind"], r["host_id"], r["vendor_name"]) for r in rows(response)] == [
            (host, subject.pk, "Sole supplier")]

    prove(w, key, lambda c: command(c, "admin-makerspace-warranties", "get", [w.space.pk]), check,
          off=(404, "capability_disabled"))
