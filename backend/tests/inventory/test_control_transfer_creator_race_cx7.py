"""Custom stock-transfer /control/ POSTs retain the product quota until commit."""
from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connection, connections
from django.test import Client
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.inventory.models import InventoryProduct
from apps.operations.models import StockTransfer
from tests.accounts.reauth_helpers import force_recent_control_login
from tests.inventory.transfer_quota_helpers_cx7 import transfer_world
from tests.r2_superadmin_local.helpers import superadmin

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory]


@pytest.mark.parametrize("cross", [False, True])
def test_two_control_transfers_at_last_product_slot_admit_one(cross, client, settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    source, destination, first, boxes = transfer_world(cross)
    second = InventoryProduct.objects.create(makerspace=source, name="Other tools",
                                             total_quantity=6, available_quantity=6)
    if not cross:
        source.resource_limit_overrides = {"products": 3}
        source.save(update_fields=["resource_limit_overrides"])
    actor = superadmin("cx7-control-transfer-race")
    force_recent_control_login(client, actor)
    url = reverse("admin:operations_stocktransfer_add")
    barrier = Barrier(2)

    def create(index):
        close_old_connections()
        try:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
            caller = Client()
            caller.cookies = client.cookies.copy()
            body = {"source_makerspace": source.pk, "destination_makerspace": destination.pk,
                    "destination_container": boxes[index].pk, "product": [first, second][index].pk,
                    "quantity": 1, "reason": "Quota race"}
            barrier.wait(timeout=15)
            response = caller.post(url, body)
            if response.status_code == 200:
                return response.status_code, [error.code for error in response.context["form"].non_field_errors().as_data()]
            return response.status_code, []
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(create, index) for index in range(2)]
        results = sorted(future.result(timeout=30) for future in futures)
    assert results == [(200, ["limit_reached"]), (302, [])]
    assert InventoryProduct.objects.filter(makerspace=destination).count() == (1 if cross else 3)
    assert StockTransfer.objects.filter(makerspace=source).count() == 1
    assert AuditLog.objects.filter(makerspace=source, action="stock_transfer.applied").count() == 1
    first.refresh_from_db()
    second.refresh_from_db()
    assert sorted([first.available_quantity, second.available_quantity]) == [5, 6]
