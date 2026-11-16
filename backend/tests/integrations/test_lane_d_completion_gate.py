"""Completion reuses boundary locks without weakening standalone write gates."""

import pytest

from apps.integrations import broadcasts_delivery, broadcasts_worker
from apps.integrations.dispatch_delivery import _deliver
from apps.tenant_migration import gate_runtime
from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
from tests.events.lane_d_helpers import fixture, queued, smtp
from tests.tenant_migration.source_gate_helpers import close_gate

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("stage", ["send", "terminal_recovery", "campaign_recovery"])
def test_completion_never_reacquires_the_application_lock_under_a_boundary(monkeypatch, caplog, stage):
    space, actor, _, event, _ = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    send = smtp(monkeypatch)
    if stage != "send":
        # Provider success committed before the completion callback ran.
        log.status = "sent"
        log.save(update_fields=["status"])
    if stage == "campaign_recovery":
        delivery.status = "sent"
        delivery.save(update_fields=["status"])

    def reacquire(*args, **kwargs):
        # A waiting migration writer would stall this second lock forever.
        raise AssertionError("Completion must reuse its dedicated boundary lock")

    monkeypatch.setattr(gate_runtime, "acquire_shared", reacquire)
    if stage == "send":
        with gate_runtime.boundary_tenant_write(space.pk):
            _deliver(log)
    else:
        broadcasts_worker.resume_broadcasts()
    campaign.refresh_from_db()
    delivery.refresh_from_db()
    assert campaign.status == delivery.status == "sent"
    assert send.call_count == (1 if stage == "send" else 0)
    assert not any(row.msg == "broadcast_recovery_failed" for row in caplog.records)


@pytest.mark.parametrize("stage", ["finished", "reconcile"])
@pytest.mark.parametrize("closed", [False, True])
def test_standalone_completion_still_takes_and_validates_the_gate(monkeypatch, stage, closed):
    space, actor, _, event, _ = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    log.status = "sent"
    log.save(update_fields=["status"])
    if stage == "reconcile":
        delivery.status = "sent"
        delivery.save(update_fields=["status"])
    if closed:
        close_gate(space, actor)
    acquired = []
    original = gate_runtime.acquire_shared

    def acquire(tenant):
        acquired.append(tenant)
        return original(tenant)

    monkeypatch.setattr(gate_runtime, "acquire_shared", acquire)
    callback = (lambda: broadcasts_delivery.finished(log)) if stage == "finished" else (
        lambda: broadcasts_worker.reconcile("event_broadcast", campaign.pk)
    )
    if closed:
        with pytest.raises(SourceMigrationGateClosed):
            callback()
    else:
        callback()
    assert acquired and set(acquired) == {space.pk}
    campaign.refresh_from_db()
    delivery.refresh_from_db()
    assert campaign.status == ("sending" if closed else "sent")
    assert delivery.status == ("pending" if closed and stage == "finished" else "sent")
