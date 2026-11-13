import pytest

from apps.integrations.notification_resolution import resolve
from apps.operations.models import StocktakeSession
from apps.operations.notifications_p2_alerts import notify_stocktake
from tests.module_helpers import disable_module

pytestmark = pytest.mark.django_db


def test_stocktake_delivery_requires_its_own_module_without_procurement(lane):
    disable_module(lane.space, "procurement")
    row = StocktakeSession.objects.create(makerspace=lane.space, started_by=lane.manager, status="counting")
    notify_stocktake(row, "scheduled")
    envelope = lane.deliver("scheduled", lane.manager)
    assert lane.fake.calls
    assert {target.channel for target in resolve(envelope)} == {"telegram"}
    disable_module(lane.space, "stocktake")
    assert resolve(envelope) == []


def test_stocktake_selection_and_category_survive_without_procurement(lane):
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.integrations.models_recipients import NotificationRecipient
    from apps.integrations.notification_availability import available_channels
    from apps.notifications.preferences import preference_cells
    selected = lane.account("stocktake-selected-manager", "space_manager")
    NotificationRecipient.objects.create(makerspace=lane.space, feature="stock",
        event="scheduled", kind="user", user=selected)
    disable_module(lane.space, "procurement")
    lane.space.refresh_from_db()
    assert "telegram" in available_channels(lane.space, "stock")
    assert any(cell["feature"] == "stock" for cell in preference_cells(lane.space, selected))
    row = StocktakeSession.objects.create(makerspace=lane.space, started_by=lane.manager, status="counting")
    notify_stocktake(row, "scheduled")
    assert list(NotificationEnvelope.objects.filter(source_kind="operations.stocktake").values_list(
        "recipient_id", flat=True)) == [selected.pk]
    lane.deliver("scheduled", selected)
    assert lane.fake.calls
