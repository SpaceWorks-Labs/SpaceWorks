"""Availability owns the edge; the watch reserves one canonical source intent."""
from types import SimpleNamespace

import pytest
from django.db import transaction
from django.utils import timezone

from apps.integrations.models_contract import NotificationEnvelope
from apps.inventory.availability import return_to_available
from apps.inventory.models import InventoryProduct
from apps.inventory.models_watch import InventoryWatch
from apps.inventory.notifications_p2 import eligible_watch
from apps.inventory.notify_me import dispatch, subscribe
from apps.makerspaces.models import MakerspaceMembership
from apps.operations.reminder_types import ReminderMessage
from tests.return_helpers import make_product, make_space, make_user

pytestmark = pytest.mark.django_db


def test_stock_return_latches_once_and_hidden_stock_invalidates_watch(monkeypatch):
    space = make_space("recon-watch")
    space.public_inventory_enabled = True
    space.enabled_features = sorted(set(space.enabled_features) | {"inventory.notify_when_back"})
    space.save(update_fields=["enabled_features", "public_inventory_enabled"])
    user = make_user("recon-watch-owner", access_status="active")
    MakerspaceMembership.objects.create(makerspace=space, user=user, role="custom",
                                        assigned_role=space.roles.get(slug="member"))
    product = make_product(space, total_quantity=1, available_quantity=0, issued_quantity=1,
                           public_availability_mode="status_only")
    watch = subscribe(product, user)
    with transaction.atomic():
        locked = InventoryProduct.objects.select_for_update().get(pk=product.pk)
        return_to_available(locked, 1)
    watch.refresh_from_db()
    assert watch.ready_at is not None
    reminder = SimpleNamespace(subject=f"{watch.pk}:{watch.ready_at.isoformat()}", due_at=watch.ready_at)
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    message = ReminderMessage("Available", "available", "An item you follow is available again.")
    for _ in range(2):
        dispatch(space, reminder, message, timezone.now(), None)
    assert InventoryWatch.objects.get(pk=watch.pk).notified_at is not None
    envelope = NotificationEnvelope.objects.get(source_kind="inventory.watch", recipient=user)
    assert eligible_watch(envelope)
    InventoryProduct.objects.filter(pk=product.pk).update(public_availability_mode="hidden")
    assert not eligible_watch(envelope)
