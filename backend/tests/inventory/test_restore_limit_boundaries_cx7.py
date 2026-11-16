"""Unarchiving must admit the product AND every asset that becomes counted."""
import pytest
from django.db import transaction
from django.urls import reverse

from apps.inventory.models import InventoryAsset, InventoryProduct
from tests.limits_0120.admin_capacity_helpers_cx7 import bound_form, form_errors
from tests.r2_superadmin_local.helpers import superadmin
from tests.return_helpers import authenticated_client, make_member, make_space
from tests.shop.test_native_shop_limits_cx7 import native_staff_client

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("surface", ["control", "browser", "apple", "android"])
@pytest.mark.parametrize("count", [1, 2])
def test_restore_counts_each_asset_and_returns_exact_error(surface, count, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("cx7-restore-capacity")
    space.resource_limit_overrides = {"products": 1, "assets": 1}
    space.save(update_fields=["resource_limit_overrides"])
    row = InventoryProduct.objects.create(makerspace=space, name="Archived", tracking_mode="individual", is_archived=True)
    InventoryAsset.objects.bulk_create([
        InventoryAsset(makerspace=space, product=row, asset_tag=f"A-{index}") for index in range(count)])
    if surface == "control":
        actor = superadmin("cx7-restore-root")
        form, model_admin, request, data = bound_form(row, actor, instance=row)
        data["is_archived"] = False
        form = type(form)(data=data, instance=row)
        with transaction.atomic():
            assert form.is_valid() is (count == 1)
            if count == 1:
                model_admin.save_model(request, form.save(commit=False), form, True)
            else:
                assert [code for code, _ in form_errors(form)] == ["limit_reached"]
                assert "assets" in str(form.non_field_errors())
    else:
        if surface == "browser":
            caller = authenticated_client(make_member("cx7-restore-manager", space))
        else:
            caller, _ = native_staff_client(space, surface, settings, monkeypatch)
        response = caller.patch(reverse("admin-inventory-detail", kwargs={"pk": row.pk}),
                                {"is_archived": False}, format="json")
        assert response.status_code == (200 if count == 1 else 400)
        if count == 2:
            assert response.json()["code"] == "limit_reached"
            assert "assets" in response.json()["detail"]
    row.refresh_from_db()
    assert row.is_archived is (count == 2)
    assert InventoryAsset.objects.filter(product=row).count() == count
