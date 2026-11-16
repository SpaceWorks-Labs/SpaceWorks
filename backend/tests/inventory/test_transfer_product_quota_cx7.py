"""Decision 519: transfer-created products consume the same slots as API creates."""
import pytest
from django.db import connection, transaction
from django.urls import reverse
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.inventory.models import InventoryProduct
from apps.operations.services_transfer_splits import _create_destination_product
from apps.operations.services_transfers import apply_stock_transfer
from tests.accounts.reauth_helpers import force_recent_control_login
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.inventory.transfer_quota_helpers_cx7 import payload, snapshot, transfer_world
from tests.limits_0120.concurrency_helpers_cx7 import race_posts
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.r2_superadmin_local.helpers import superadmin
from tests.return_helpers import authenticated_client, make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory]


def test_direct_split_helper_retains_the_shared_quota_through_its_insert(settings):
    settings.MANAGED_PLANS_ENABLED = False
    source, _, row, boxes = transfer_world()
    destination = _create_destination_product(row, boxes[0])
    assert InventoryProduct.objects.filter(makerspace=source).count() == 2
    assert (destination.total_quantity, destination.available_quantity) == (0, 0)
    before = snapshot()
    with pytest.raises(ValidationError) as raised:
        _create_destination_product(row, boxes[1])
    assert raised.value.status_code == 400
    assert str(raised.value.detail["code"]) == "limit_reached"
    assert snapshot() == before


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_split_transfer_max_then_max_plus_one_is_atomic(surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    source, _, row, boxes = transfer_world()
    caller = callers(source, surface, settings, monkeypatch)[0]
    url = reverse("stock-transfers", kwargs={"makerspace_id": source.pk})
    maximum = caller.post(url, payload(row, boxes[0]), format="json")
    assert maximum.status_code == 201
    row.refresh_from_db()
    assert (row.total_quantity, row.available_quantity) == (5, 5)
    assert InventoryProduct.objects.filter(makerspace=source).count() == 2
    before = snapshot()
    refused = caller.post(url, payload(row, boxes[1]), format="json")
    assert refused.status_code == 400
    assert refused.json()["code"] == "limit_reached"
    assert snapshot() == before


def test_cross_space_transfer_counts_destination_and_rolls_back_refusal(settings):
    settings.MANAGED_PLANS_ENABLED = False
    source, destination, row, boxes = transfer_world(cross=True)
    # The source is already over this limit; only destination capacity is consumed.
    source.resource_limit_overrides = {"products": 0}
    source.save(update_fields=["resource_limit_overrides"])
    caller = authenticated_client(superadmin("cx7-cross-quota-root"))
    url = reverse("stock-transfers", kwargs={"makerspace_id": source.pk})
    maximum = caller.post(url, payload(row, boxes[0]), format="json")
    assert maximum.status_code == 201
    assert InventoryProduct.objects.filter(makerspace=destination).count() == 1
    before = snapshot()
    refused = caller.post(url, payload(row, boxes[1]), format="json")
    assert refused.status_code == 400
    assert refused.json()["code"] == "limit_reached"
    assert snapshot() == before
    # An existing destination row consumes no new slot at capacity.
    merged = caller.post(url, payload(row, boxes[0]), format="json")
    assert merged.status_code == 201
    assert InventoryProduct.objects.get(makerspace=destination).available_quantity == 2
    assert InventoryProduct.objects.filter(makerspace=destination).count() == 1


@pytest.mark.parametrize("cross", [False, True])
def test_control_transfer_product_refusal_keeps_the_exact_api_code(cross, client, settings):
    settings.MANAGED_PLANS_ENABLED = False
    source, destination, row, boxes = transfer_world(cross)
    force_recent_control_login(client, superadmin("cx7-transfer-product-control"))
    url = reverse("admin:operations_stocktransfer_add")
    body = {"source_makerspace": source.pk, "destination_makerspace": destination.pk,
            "product": row.pk, "quantity": 1, "reason": "Quota regression"}
    assert client.post(url, {**body, "destination_container": boxes[0].pk}).status_code == 302
    before = snapshot()
    refused = client.post(url, {**body, "destination_container": boxes[1].pk})
    assert refused.status_code == 200
    assert [error.code for error in refused.context["form"].non_field_errors().as_data()] == ["limit_reached"]
    assert snapshot() == before


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_two_split_transfers_at_last_slot_have_one_winner(surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    source, _, row, boxes = transfer_world()
    # Different source products prevent a source-row lock from hiding a quota race.
    second = InventoryProduct.objects.create(makerspace=source, name="Second tools",
                                             total_quantity=6, available_quantity=6)
    source.resource_limit_overrides = {"products": 3}
    source.save(update_fields=["resource_limit_overrides"])
    pair = callers(source, surface, settings, monkeypatch)
    url = reverse("stock-transfers", kwargs={"makerspace_id": source.pk})
    results = race_posts(pair, url, [payload(row, boxes[0]), payload(second, boxes[1])])
    assert sorted(status for status, _ in results) == [201, 400]
    assert [body["code"] for status, body in results if status == 400] == ["limit_reached"]
    assert InventoryProduct.objects.filter(makerspace=source).count() == 3
    assert AuditLog.objects.filter(makerspace=source, action="stock_transfer.applied").count() == 1
    row.refresh_from_db()
    second.refresh_from_db()
    assert sorted([row.available_quantity, second.available_quantity]) == [5, 6]


def test_multi_line_transfer_rolls_back_an_earlier_successful_split(settings):
    settings.MANAGED_PLANS_ENABLED = False
    source, _, row, boxes = transfer_world()
    second = InventoryProduct.objects.create(makerspace=source, name="Second tools",
                                             total_quantity=2, available_quantity=2)
    source.resource_limit_overrides = {"products": 3}
    source.save(update_fields=["resource_limit_overrides"])
    body = payload(row, boxes[0])
    body["lines"].append({"product_id": second.pk, "quantity": 1})
    actor = superadmin("cx7-transfer-rollback")
    before = snapshot()
    with pytest.raises(ValidationError) as raised, transaction.atomic():
        apply_stock_transfer(actor, source, body)
    assert raised.value.status_code == 400
    assert str(raised.value.detail["code"]) == "limit_reached"
    assert snapshot() == before


@pytest.mark.django_db(transaction=True)
def test_cross_space_creators_from_different_sources_share_destination_capacity(settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    source, destination, first, boxes = transfer_world(cross=True)
    other_source = make_space("cx7-cross-other-source")
    second = InventoryProduct.objects.create(makerspace=other_source, name="Other tools",
                                             total_quantity=2, available_quantity=2)
    actor = superadmin("cx7-cross-race")
    products = [first, second]
    results = race_creators(lambda index: apply_stock_transfer(
        actor, [source, other_source][index], payload(products[index], boxes[index])))
    assert results == [(201, "created"), (400, "limit_reached")]
    assert InventoryProduct.objects.filter(makerspace=destination).count() == 1
    assert AuditLog.objects.filter(makerspace__in=[source, other_source], action="stock_transfer.applied").count() == 1


def test_whole_row_relocation_does_not_consume_another_product_slot(settings):
    settings.MANAGED_PLANS_ENABLED = False
    source, _, row, boxes = transfer_world()
    source.resource_limit_overrides = {"products": 1}
    source.save(update_fields=["resource_limit_overrides"])
    body = payload(row, boxes[0])
    body["lines"][0]["quantity"] = 6
    apply_stock_transfer(superadmin("cx7-whole-row"), source, body)
    row.refresh_from_db()
    assert (row.box_id, row.total_quantity, row.available_quantity) == (boxes[0].pk, 6, 6)
    assert InventoryProduct.objects.filter(makerspace=source).count() == 1
