"""A saved vendor link is a real extra warranty PUT dependency, including the creator branch."""
import pytest

from apps.inventory.models import InventoryAsset, InventoryProduct
from apps.procurement.models import Vendor
from apps.warranty.models import Warranty
from tests.machines.route_support_cx11b_g2 import command, prove, world

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_machines]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("host", ["asset", "machine"])
@pytest.mark.parametrize("existing", [False, True], ids=["create", "update"])
def test_warranty_vendor_gate_precedes_creation_or_update(native, host, existing):
    w = world(native)
    if host == "asset":
        product = InventoryProduct.objects.create(makerspace=w.space, name="Drill", tracking_mode="individual")
        subject = InventoryAsset.objects.create(makerspace=w.space, product=product, asset_tag="G2-VENDOR")
    else:
        subject = w.machine
    vendor = Vendor.objects.create(makerspace=w.space, name="Saved supplier", created_by=w.actor)
    if existing:
        Warranty.objects.create(makerspace=w.space, **{host: subject}, vendor_name="Retained supplier")

    def check(response):
        saved = Warranty.objects.get(**{host: subject})
        assert (saved.vendor_id, saved.vendor_name, response.data["id"]) == (vendor.pk, "New supplier", saved.pk)
        assert Warranty.objects.filter(makerspace=w.space).count() == 1

    # 520: resolve the scoped host before either its warranty or vendor switch.
    prove(w, "inventory.vendors", lambda c: command(c, f"admin-{host}-warranty", "put", [subject.pk],
          {"vendor_id": vendor.pk, "vendor_name": "New supplier"}), check,
          audits=("warranty.updated" if existing else "warranty.created",), off=(404, "capability_disabled"))
