"""Decision 246 (lane T4): service-level conditions for the link webhooks (interconnection 18).

Calls `link_webhooks.link_webhook` and `link_changes` directly with the channel captured as a
`NotificationDeliveryLog` row: ids and `occurred_at` only (no title, person or amount), the gate
(every required module on, the webhook cell on), unknown events refused, a failed insert fails
safe, and no row is written for another space.
"""
import pytest
from django.db import DatabaseError, transaction

from apps.integrations.link_webhooks import LINK_EVENTS, link_changes, link_webhook
from apps.integrations.models import NotificationDeliveryLog
from apps.makerspaces.models import Makerspace
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db(transaction=True)

IDS = {"event_id": 11, "booking_id": 12, "request_id": 13}


@pytest.fixture
def cell_on(monkeypatch):
    from apps.integrations import notification_catalog
    monkeypatch.setattr(notification_catalog, "is_notification_enabled", lambda *args: True)


def set_modules(space, *, on=(), off=()):
    mods = (set(space.enabled_modules or []) | set(on)) - set(off)
    Makerspace.objects.filter(pk=space.pk).update(enabled_modules=sorted(mods))
    space.refresh_from_db()
    return space


def all_on(slug):
    return set_modules(make_space(slug), on={"events", "bookings", "request_workflow"})


@pytest.mark.parametrize("event", sorted(LINK_EVENTS))
def test_payload_is_ids_and_time_only(cell_on, event):
    space = all_on(f"t246-lw-{event}")
    assert link_webhook(space, event, title="Secret workshop", member="Jo", amount="12.50", **IDS) is True
    row = NotificationDeliveryLog.objects.get(makerspace=space, event=event)
    allowed = set(LINK_EVENTS[event][2]) | {"occurred_at"}
    assert set(row.payload) == allowed
    assert "Secret workshop" not in str(row.payload) and "Jo" not in row.text_body
    assert row.channel == "webhook" and row.feature == LINK_EVENTS[event][0]


def test_unknown_event_is_refused():
    with pytest.raises(ValueError):
        link_webhook(make_space("t246-lw-unknown"), "event_exploded", **IDS)


@pytest.mark.parametrize("event", sorted(LINK_EVENTS))
def test_each_required_module_gates_the_webhook(cell_on, event):
    for module in LINK_EVENTS[event][1]:
        space = set_modules(all_on(f"t246-lw-{event}-{module}"), off={module})
        assert link_webhook(space, event, **IDS) is False
        assert not NotificationDeliveryLog.objects.filter(makerspace=space, event=event).exists()


def test_the_webhook_cell_off_queues_nothing(monkeypatch):
    from apps.integrations import notification_catalog
    monkeypatch.setattr(notification_catalog, "is_notification_enabled", lambda *args: False)
    space = all_on("t246-lw-cell-off")
    assert link_webhook(space, "event_booking_linked", **IDS) is False
    assert not NotificationDeliveryLog.objects.filter(makerspace=space).exists()


def test_a_row_is_written_for_the_named_space_only(cell_on):
    space, other = all_on("t246-lw-a"), all_on("t246-lw-b")
    link_webhook(space, "event_loan_linked", **IDS)
    assert NotificationDeliveryLog.objects.filter(makerspace=space).count() == 1
    assert not NotificationDeliveryLog.objects.filter(makerspace=other).exists()


def test_a_failed_insert_fails_safe_and_keeps_the_callers_transaction(cell_on, monkeypatch):
    from apps.integrations import dispatch_channels

    def explode(**kwargs):
        raise DatabaseError("insert failed")

    monkeypatch.setattr(dispatch_channels, "dispatch_channel", explode)
    space = all_on("t246-lw-fail")
    with transaction.atomic():
        assert link_webhook(space, "event_booking_linked", **IDS) is False
        Makerspace.objects.filter(pk=space.pk).update(name="Still writable")
    assert Makerspace.objects.get(pk=space.pk).name == "Still writable"


def test_link_changes_unlinks_the_old_activity_then_links_the_new_one():
    assert link_changes("event_loan", None, 5, delete=False) == [("event_loan_linked", 5)]
    assert link_changes("event_loan", 4, 5, delete=False) == [("event_loan_unlinked", 4), ("event_loan_linked", 5)]
    assert link_changes("event_loan", 5, 5, delete=False) == []
    assert link_changes("event_loan", 4, None, delete=True) == [("event_loan_unlinked", 4)]
    assert link_changes("event_loan", None, None, delete=True) == []
