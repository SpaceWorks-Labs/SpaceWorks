"""Asset-unit routes need real inventory rows: a missing ID cannot prove their module gate."""
import pytest
from django.urls import reverse

from apps.boxes.models import QrCode
from apps.inventory.models import InventoryAsset
from tests.return_helpers import authenticated_client, make_member, make_product, make_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("route", ["generate", "asset_qr", "external_qr"])
def test_asset_routes_refuse_off_restore_on_and_retain_rows(route):
    space = make_space("cx2-assets")
    actor = make_member("cx2-asset-manager", space)
    client = authenticated_client(actor)
    product = make_product(space)
    asset = InventoryAsset.objects.create(makerspace=space, product=product, asset_tag="CX2-1")
    if route == "generate":
        url, body = reverse("asset-generate", args=[product.pk]), {"count": 1}
    elif route == "asset_qr":
        url, body = reverse("asset-qr", args=[asset.pk]), {}
    else:
        url, body = reverse("qr-external-assign"), {
            "makerspace_id": space.pk, "asset_id": asset.pk, "value": "CX2-ASSET-QR"}
    first = client.post(url, body, format="json")
    assert first.status_code == 201, first.data
    before_assets = list(InventoryAsset.objects.filter(makerspace=space).order_by("pk").values())
    before_qr = list(QrCode.objects.filter(makerspace=space).order_by("pk").values())
    original = space.enabled_modules
    space.enabled_modules = [key for key in original if key != "asset_units"]
    space.save(update_fields=["enabled_modules"])
    response = client.post(url, body, format="json")
    assert (response.status_code, response.data["code"], response.data["module"]) == (404, "module_disabled", "asset_units")
    assert list(InventoryAsset.objects.filter(makerspace=space).order_by("pk").values()) == before_assets
    assert list(QrCode.objects.filter(makerspace=space).order_by("pk").values()) == before_qr
    space.enabled_modules = original
    space.save(update_fields=["enabled_modules"])
    assert list(InventoryAsset.objects.filter(makerspace=space).order_by("pk").values()) == before_assets
    assert list(QrCode.objects.filter(makerspace=space).order_by("pk").values()) == before_qr
    response = client.post(url, body, format="json")
    assert response.status_code == (200 if route == "external_qr" else 201), response.data
