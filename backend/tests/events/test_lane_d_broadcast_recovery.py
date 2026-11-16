"""Recovery budgets belong to tenants, not a global fixed prefix of rows."""

from unittest.mock import Mock

import pytest

from apps.events.models_broadcasts import EventBroadcast, EventBroadcastDelivery
from apps.integrations import broadcasts_worker, delivery_sources, dispatch_outbox
from apps.integrations.broadcasts_registry import ADAPTERS
from apps.integrations.models import EmailLog
from tests.events.ticketing_helpers import account, event_space, open_event
from tests.tenant_migration.source_gate_helpers import close_gate

pytestmark = pytest.mark.django_db


def campaigns(space, event, actor, count, *, complete=False):
    return [EventBroadcast.objects.create(
        makerspace=space, event=event, created_by=actor, subject="Notice", body="Hello",
        status="sending", recipients_complete=complete,
    ) for _ in range(count)]


@pytest.mark.parametrize("operation", ["terminal", "completion", "campaign", "delivery"])
def test_frozen_prefix_cannot_starve_other_tenants(monkeypatch, operation):
    frozen, healthy = event_space("recovery-frozen"), event_space("recovery-healthy")
    actor = account("recovery-actor")
    expected = []
    frozen_campaigns = []
    # A complete global batch from the frozen tenant used to hide the healthy rows.
    for space, count in ((frozen, broadcasts_worker.BATCH_SIZE + 1), (healthy, 2)):
        event = open_event(space)
        rows = campaigns(space, event, actor, count, complete=operation in {"terminal", "completion"})
        for campaign in rows:
            if space == frozen:
                frozen_campaigns.append(campaign.pk)
            if operation in {"terminal", "delivery"}:
                log = EmailLog.objects.create(
                    makerspace=space, recipient=actor, to_email=actor.email,
                    subject="Notice", status="sent" if operation == "terminal" else "failed",
                    attempts=1, source_kind="event_broadcast",
                )
                delivery = EventBroadcastDelivery.objects.create(campaign=campaign, recipient=actor, outbox=log)
                EmailLog.objects.filter(pk=log.pk).update(source_id=delivery.pk)
                if space == healthy:
                    expected.append(log.pk)
            elif space == healthy:
                expected.append(campaign.pk)
    close_gate(frozen, actor)
    terminal, completion, campaign, delivery = Mock(), Mock(), Mock(), Mock()
    monkeypatch.setattr(delivery_sources, "finished", terminal)
    monkeypatch.setattr(broadcasts_worker, "reconcile", completion)
    monkeypatch.setattr(broadcasts_worker, "enqueue", campaign)
    monkeypatch.setattr(dispatch_outbox, "_enqueue", delivery)
    monkeypatch.setattr(broadcasts_worker, "ADAPTERS", {"event_broadcast": ADAPTERS["event_broadcast"]})
    callback = {"terminal": terminal, "completion": completion, "campaign": campaign, "delivery": delivery}[operation]
    # A frozen prefix must not monopolize later sweeps either.
    for _ in range(2):
        callback.reset_mock()
        broadcasts_worker.resume_broadcasts()
        actual = [call.args[0].pk if operation == "terminal" else call.args[-1]
                  for call in callback.call_args_list]
        assert actual == expected
    assert EventBroadcast.objects.filter(pk__in=frozen_campaigns, status="sending").count() == len(frozen_campaigns)
    assert not EventBroadcastDelivery.objects.filter(campaign_id__in=frozen_campaigns).exclude(status="pending").exists()


def test_recovery_budget_is_bounded_and_ordered_for_each_tenant(monkeypatch):
    actor = account("recovery-budget-actor")
    expected = []
    for slug in ("recovery-budget-first", "recovery-budget-second"):
        space = event_space(slug)
        rows = campaigns(space, open_event(space), actor, 3)
        expected.extend(row.pk for row in rows[:2])
    monkeypatch.setattr(broadcasts_worker, "BATCH_SIZE", 2)
    rows = EventBroadcast.objects.filter(status="sending").values("pk", "makerspace_id")
    assert [row["pk"] for row in broadcasts_worker.recovery_rows(rows, "makerspace_id")] == expected
