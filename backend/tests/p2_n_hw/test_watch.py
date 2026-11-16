from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.inventory.models import InventoryProduct
from apps.inventory import notify_me, availability
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.models import NotificationDeliveryLog
from apps.integrations.notification_sources import source_eligible
from apps.integrations.notification_resolution import resolve
from apps.makerspaces.models import MakerspaceMembership

pytestmark = pytest.mark.django_db


def setup_watch(world):
    MakerspaceMembership.objects.create(makerspace=world.space, user=world.owner,
        role=MakerspaceMembership.Role.CUSTOM, assigned_role=world.space.roles.get(slug="member"))
    product = InventoryProduct.objects.create(makerspace=world.space, name="Drill")
    return product, notify_me.subscribe(product, world.owner)


def dispatch(world, watch):
    watch.refresh_from_db()
    reminder = SimpleNamespace(subject=f"{watch.pk}:{watch.ready_at.isoformat()}", due_at=watch.ready_at)
    message = notify_me.build(world.space, reminder, timezone.now(), ZoneInfo("UTC"))
    notify_me.dispatch(world.space, reminder, message, timezone.now(), ZoneInfo("UTC"))


def test_back_available_lifecycle_once_and_no_rooms(equipment):
    product, watch = setup_watch(equipment)
    availability.adjust_quantities(product, delta_available=1, delta_damaged=0, delta_lost=0,
                                    reason="restock", actor=equipment.manager)
    dispatch(equipment, watch)
    envelopes = NotificationEnvelope.objects.filter(source_kind="inventory.watch")
    envelope = envelopes.get()
    assert envelope.recipient_id == equipment.owner.pk and envelope.audience == "requester"
    assert {target.channel for target in resolve(envelope)} == {"telegram"}
    assert not NotificationDeliveryLog.objects.filter(event="back_available").exists()
    watch.refresh_from_db()
    assert watch.notified_at is not None
    assert not list(notify_me.discover(equipment.space, timezone.now(), 10, ZoneInfo("UTC")))
    availability.adjust_quantities(product, delta_available=1, delta_damaged=0, delta_lost=0,
                                    reason="more stock", actor=equipment.manager)
    assert envelopes.count() == 1
    notify_me.unsubscribe(product, equipment.owner)
    assert not source_eligible(envelope)


def test_watch_rollback_does_not_close_or_emit(equipment):
    product, watch = setup_watch(equipment)
    availability.adjust_quantities(product, delta_available=1, delta_damaged=0, delta_lost=0,
                                    reason="restock", actor=equipment.manager)
    with pytest.raises(RuntimeError), transaction.atomic():
        dispatch(equipment, watch)
        raise RuntimeError("rollback")
    watch.refresh_from_db()
    assert watch.notified_at is None
    assert not NotificationEnvelope.objects.filter(source_kind="inventory.watch").exists()


@pytest.mark.parametrize("change", ["is_public", "is_archived", "public_availability_mode"])
def test_watch_rechecks_public_visibility(equipment, change):
    product, watch = setup_watch(equipment)
    availability.adjust_quantities(product, delta_available=1, delta_damaged=0, delta_lost=0,
                                    reason="restock", actor=equipment.manager)
    dispatch(equipment, watch)
    envelope = NotificationEnvelope.objects.get(source_kind="inventory.watch")
    setattr(product, change, {"is_public": False, "is_archived": True, "public_availability_mode": "hidden"}[change])
    product.save(update_fields=[change])
    assert not source_eligible(envelope)


def test_watch_rejects_available_and_hidden_stock(equipment):
    product, watch = setup_watch(equipment)
    product.public_availability_mode = "hidden"
    product.save(update_fields=["public_availability_mode"])
    with pytest.raises(ValidationError):
        notify_me.subscribe(product, equipment.owner)
    product.public_availability_mode = "status_only"
    product.available_quantity = product.total_quantity = 1
    product.save(update_fields=["public_availability_mode", "available_quantity", "total_quantity"])
    with pytest.raises(ValidationError):
        notify_me.subscribe(product, equipment.owner)


def test_inventory_reorder_point_coverage(equipment):
    from apps.inventory.notifications_p2 import notify_stock
    product = InventoryProduct.objects.create(makerspace=equipment.space, name="Drill", reorder_point=2)
    assert notify_stock(product).scheduled
    envelope = NotificationEnvelope.objects.get(source_kind="inventory.threshold")
    assert envelope.recipient_id == equipment.manager.pk and envelope.audience == "staff"
    assert {target.channel for target in resolve(envelope)} == {"telegram"}
    product.available_quantity = product.total_quantity = 5
    product.save(update_fields=["available_quantity", "total_quantity", "updated_at"])
    assert not source_eligible(envelope)
