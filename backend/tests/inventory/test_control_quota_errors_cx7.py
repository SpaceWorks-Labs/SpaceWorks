"""Custom /control/ inventory actions show quota errors instead of raising 500."""
import pytest
from django.urls import reverse

from apps.admin_api.bulk_import import preview_import
from apps.boxes.models import Box
from apps.inventory.admin_bulk_import import SESSION_KEY
from apps.inventory.models import InventoryProduct
from apps.makerspaces.models import Makerspace
from apps.operations.models import StockTransfer
from tests.accounts.reauth_helpers import force_recent_control_login
from tests.r2_superadmin_local.helpers import superadmin
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def test_control_bulk_import_last_slot_and_next_exact_form_error(client):
    space = make_space("cx7-control-bulk-quota")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"bulk_import"})
    space.resource_limit_overrides = {"products": 1}
    space.save(update_fields=["enabled_modules", "resource_limit_overrides"])
    actor = superadmin("cx7-bulk-root")
    force_recent_control_login(client, actor)
    url = reverse("admin:inventory_inventoryproduct_bulk_import")
    def stage(name):
        rows = [{"name": name, "total_quantity": "1", "available_quantity": "1"}]
        preview = preview_import(space, rows, {})
        assert preview["valid"] is True
        session = client.session
        session[SESSION_KEY] = {"makerspace_id": space.pk, "rows": rows, "mapping": preview["mapping"]}
        session.save()
    stage("Last")
    maximum = client.post(url, {"apply": "1"})
    assert maximum.status_code == 302
    stage("Excess")
    refused = client.post(url, {"apply": "1"})
    assert refused.status_code == 200
    errors = refused.context["form"].non_field_errors().as_data()
    assert [error.code for error in errors] == ["limit_reached"]
    assert list(InventoryProduct.objects.filter(makerspace=space).values_list("name", flat=True)) == ["Last"]
    assert SESSION_KEY in client.session
    # An operator increase admits the same retained preview.
    Makerspace.objects.filter(pk=space.pk).update(resource_limit_overrides={"products": 2})
    restored = client.post(url, {"apply": "1"})
    assert restored.status_code == 302
    assert InventoryProduct.objects.filter(makerspace=space).count() == 2


def test_control_stock_transfer_last_slot_and_next_exact_form_error(client):
    space = make_space("cx7-control-transfer-quota")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"stock_transfers"})
    space.resource_limit_overrides = {"stock_transfers_monthly": 1}
    space.save(update_fields=["enabled_modules", "resource_limit_overrides"])
    actor = superadmin("cx7-transfer-root")
    force_recent_control_login(client, actor)
    source = Box.objects.create(makerspace=space, label="Source")
    destination = Box.objects.create(makerspace=space, label="Destination")
    row = InventoryProduct.objects.create(makerspace=space, box=source, name="Moved", total_quantity=2, available_quantity=2)
    body = {"source_makerspace": space.pk, "source_container": source.pk, "destination_container": destination.pk,
            "product": row.pk, "quantity": 1, "reason": "Counted transfer"}
    url = reverse("admin:operations_stocktransfer_add")
    maximum = client.post(url, body)
    assert maximum.status_code == 302
    refused = client.post(url, body)
    assert refused.status_code == 200
    errors = refused.context["form"].non_field_errors().as_data()
    assert [error.code for error in errors] == ["stock_transfers_monthly_quota_reached"]
    assert StockTransfer.objects.filter(makerspace=space).count() == 1
