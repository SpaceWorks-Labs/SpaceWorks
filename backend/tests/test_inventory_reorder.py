from unittest.mock import Mock

import pytest
from django.db import transaction

from apps.audit.models import AuditLog
from apps.integrations.models_contract import NotificationEnvelope
from apps.inventory import availability
from apps.inventory.models import InventoryProduct
from apps.procurement.models import ToBuyItem
from tests.return_helpers import authenticated_client, make_member, make_product, make_space

pytestmark = pytest.mark.django_db


def setup_stock(slug="stock", available=5):
    space = make_space(slug)
    actor = make_member(f"staff-{slug}", space)
    product = make_product(space, available_quantity=available, total_quantity=available,
        manufacturer="Example Tools", model="Driver 12", sku="PRIVATE-SKU", barcode="PRIVATE-BARCODE",
        supplier="Private Supplier Ltd", reorder_point=3, reorder_quantity=6)
    return space, actor, product


# Notifications v2: the low-stock crossing is an envelope source (inventory.threshold)
# fanned out by apps.inventory.notifications_p2, no longer a legacy notify_family call.
FANOUT = "apps.inventory.notifications_p2.fanout"


def assert_low_stock(call, space, product):
    assert (call.kwargs["space"], call.kwargs["feature"], call.kwargs["event"]) == (space, "stock", "low_stock")
    assert call.kwargs["context"] == {"product_id": product.pk}


def adjust(actor, product, delta):
    return availability.adjust_quantities(product, delta_available=delta, delta_damaged=0,
                                         delta_lost=0, reason="Stock inspection", actor=actor)


def test_low_stock_crossing_alerts_once_and_recovery_rearms(monkeypatch):
    space, actor, product = setup_stock()
    notify = Mock()
    monkeypatch.setattr(FANOUT, notify)
    product = adjust(actor, product, -2)  # equality is the crossing
    assert notify.call_count == 1
    assert_low_stock(notify.call_args, space, product)
    product = adjust(actor, product, -1)
    product = adjust(actor, product, 0)
    assert notify.call_count == 1
    product = adjust(actor, product, 3)  # above the threshold; no low-stock alert
    assert notify.call_count == 1
    product = adjust(actor, product, -2)
    assert notify.call_count == 2


def test_crossing_callback_is_discarded_on_transaction_rollback(monkeypatch, django_capture_on_commit_callbacks):
    space, actor, product = setup_stock()
    deliver = Mock()
    # Route the staff summary to the acting manager; delivery is the outbox's on-commit enqueue.
    monkeypatch.setattr("apps.hardware_requests.notifications_p2.staff_user_ids_for_feature",
                        lambda *args, **kwargs: [actor.pk])
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", deliver)
    threshold = NotificationEnvelope.objects.filter(source_kind="inventory.threshold", source_id=str(product.pk))
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError), transaction.atomic():
            adjust(actor, product, -2)
            raise RuntimeError("Rollback")
    assert not deliver.called
    assert not threshold.exists()
    product.refresh_from_db()
    assert product.available_quantity == 5
    with django_capture_on_commit_callbacks(execute=True):
        adjust(actor, product, -2)
    envelope = threshold.get()
    assert (envelope.makerspace_id, envelope.recipient_id, envelope.feature, envelope.event) == (
        space.pk, actor.pk, "stock", "low_stock")
    deliver.assert_called_once_with(envelope.pk)


def test_zero_point_disabled_and_delivery_failure_cannot_undo_quantity_change(monkeypatch):
    _space, actor, product = setup_stock()
    notify = Mock(side_effect=RuntimeError("Provider unavailable"))
    monkeypatch.setattr(FANOUT, notify)
    product = adjust(actor, product, -2)
    assert product.available_quantity == 3
    assert notify.call_count == 1
    product.reorder_point = 0
    product.save(update_fields=["reorder_point"])
    product = adjust(actor, product, 5)
    product = adjust(actor, product, -8)
    assert product.available_quantity == 0
    assert notify.call_count == 1


def test_direct_issue_return_and_stocktake_crossings_use_the_same_observer(monkeypatch):
    _space, _actor, product = setup_stock()
    notify = Mock()
    monkeypatch.setattr(FANOUT, notify)
    with transaction.atomic():
        product = InventoryProduct.objects.select_for_update().get(pk=product.pk)
        availability.issue_available(product, 2)
        availability.return_to_available(product, 2)
        availability.apply_stocktake_delta(product, delta_available=-2)
    assert notify.call_count == 2


def test_reorder_suggestions_scoped_and_procurement_creation_audited_idempotently():
    space, actor, product = setup_stock(available=2)
    _other, _other_actor, foreign = setup_stock("foreign-stock", available=2)
    client = authenticated_client(actor)
    base = f"/api/v1/admin/makerspace/{space.pk}/inventory"
    response = client.get(f"{base}/reorder-suggestions")
    assert response.status_code == 200
    assert [row["id"] for row in response.data["results"]] == [product.pk]
    first = client.post(f"{base}/reorder-draft", {"product_id": product.pk}, format="json")
    assert first.status_code == 201
    repeated = client.post(f"{base}/reorder-draft", {"product_id": product.pk}, format="json")
    assert repeated.status_code == 200
    assert first.data["id"] == repeated.data["id"]
    draft = ToBuyItem.objects.get(pk=first.data["id"])
    assert draft.status == ToBuyItem.Status.REQUESTED
    assert draft.quantity == 6
    assert draft.vendor_name == product.supplier
    assert draft.source_product_id == product.pk
    assert draft.created_by_id == actor.pk
    assert AuditLog.objects.filter(action="procurement.item_added", makerspace=space).count() == 1
    refused = client.post(f"{base}/reorder-draft", {"product_id": foreign.pk}, format="json")
    assert refused.status_code == 404
    assert ToBuyItem.objects.count() == 1


def test_reorder_refuses_foreign_makerspace_and_module_off():
    space, actor, product = setup_stock(available=2)
    other, _other_actor, _foreign = setup_stock("foreign-stock", available=2)
    client = authenticated_client(actor)
    foreign_url = f"/api/v1/admin/makerspace/{other.pk}/inventory/reorder-suggestions"
    assert client.get(foreign_url).status_code in (403, 404)
    space.enabled_features = [key for key in space.enabled_features if key != "inventory.tobuy"]
    space.save(update_fields=["enabled_features"])
    response = client.post(f"/api/v1/admin/makerspace/{space.pk}/inventory/reorder-draft",
                           {"product_id": product.pk}, format="json")
    assert response.status_code == 404  # L17 (#97): inventory.tobuy off
    assert not ToBuyItem.objects.exists()


@pytest.mark.parametrize("field,value", [("reorder_point", -1), ("reorder_quantity", -1)])
def test_reorder_settings_validate_nonnegative_counts(field, value):
    _space, actor, product = setup_stock()
    response = authenticated_client(actor).patch(f"/api/v1/admin/inventory/{product.pk}",
                                                 {field: value}, format="json")
    assert response.status_code == 400


def test_public_inventory_never_exposes_private_master_or_reorder_fields():
    space, actor, product = setup_stock(available=2)
    response = authenticated_client(actor).get(f"/api/v1/public/{space.slug}/inventory/")
    assert response.status_code == 200
    row = next(row for row in response.data["results"] if row["id"] == product.pk)
    assert not {"manufacturer", "model", "sku", "barcode", "supplier", "reorder_point",
                "reorder_quantity", "kit_components"} & set(row)
    assert "PRIVATE-SKU" not in str(response.data)
    assert "Private Supplier" not in str(response.data)
