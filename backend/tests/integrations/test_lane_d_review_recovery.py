"""Campaign recovery keeps tenant failures out of the ordinary reminder sweep."""

from unittest.mock import Mock

import pytest

from apps.encryption.write_fence import close_makerspace, reopen
from apps.events.services_registration import register
from apps.integrations.models import NotificationPreference
from apps.operations.tasks_reminders import run_reminder_sweep_task
from tests.events.collab_helpers import make_staff
from tests.events.lane_d_helpers import fixture, queued
from tests.events.ticketing_helpers import event_space, open_event

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("stage", ["finished", "reconcile"])
def test_fenced_campaign_does_not_stop_other_tenants_or_reminders(monkeypatch, caplog, stage):
    space, actor, user, event, registration = fixture(monkeypatch)
    blocked, blocked_delivery, blocked_log = queued(event, actor, statuses=["registered"])
    peer = event_space("recovery-peer")
    peer.enabled_modules, peer.enabled_features = space.enabled_modules, space.enabled_features
    peer.save()
    # Enabling the email module does not opt this tenant into event email.
    NotificationPreference.objects.create(
        makerspace=peer, feature="events", channel="email", enabled=True,
    )
    peer_actor = make_staff(peer)
    peer_event = open_event(peer)
    register(peer_event, member=user, actor=user)
    healthy, healthy_delivery, healthy_log = queued(peer_event, peer_actor, statuses=["registered"])
    for log in (blocked_log, healthy_log):
        # Simulate SMTP success committed just before a worker died.
        log.status = "sent"
        log.save(update_fields=["status"])
    if stage == "reconcile":
        for delivery in (blocked_delivery, healthy_delivery):
            delivery.status = "sent"
            delivery.save(update_fields=["status"])
    sweep = Mock(return_value={"dispatched": 2, "skipped": 0, "failed": 0})
    monkeypatch.setattr("apps.operations.tasks_reminders.run_reminder_sweep", sweep)
    operation = close_makerspace(space.pk, "decrypt_rollback", actor.pk)
    try:
        result = run_reminder_sweep_task.run()
        sweep.assert_called_once_with()
        assert result == {"dispatched": 2, "skipped": 0, "failed": 0}
        blocked.refresh_from_db()
        healthy.refresh_from_db()
        assert blocked.status == "sending" and healthy.status == "sent"
        failures = [row for row in caplog.records if row.msg == "broadcast_recovery_failed"]
        assert any(row.makerspace_id == space.pk and row.failure_type == "PiiWriteFenced"
                   and row.operation == ("broadcast_reconcile" if stage == "finished" else "broadcast_completion")
                   for row in failures)
    finally:
        reopen(operation, actor.pk)
