"""Duplicate Celery tasks preserve exhausted failures and both manual retry paths."""

from unittest.mock import Mock

import pytest

from apps.audit.models import AuditLog
from apps.integrations.broadcasts_delivery import RETRY_START, attempt_limit
from apps.integrations.delivery_services import retry_delivery
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.models import EmailLog
from apps.integrations.services import retry_email_log
from apps.integrations.tasks import _claim_log, deliver_email_task
from tests.events.lane_d_helpers import fixture, queued, smtp
from tests.integrations.test_lane_d_broadcast_retries import exhaust

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("retry", [retry_delivery, retry_email_log])
@pytest.mark.parametrize("renewed", [False, True])
def test_duplicate_tasks_preserve_exhausted_failure_and_manual_retry(
    monkeypatch, django_capture_on_commit_callbacks, retry, renewed,
):
    space, actor, _, event, _ = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    send = smtp(monkeypatch)
    exhaust(log, send)
    enqueue = Mock()
    monkeypatch.setattr("apps.integrations.services._enqueue", enqueue)
    monkeypatch.setattr("apps.integrations.dispatch._enqueue", enqueue)
    monkeypatch.setattr("apps.integrations.tasks.record_worker_heartbeat", lambda: None)
    if renewed:
        with django_capture_on_commit_callbacks(execute=True):
            retry(actor, log)
        log.refresh_from_db()
        assert log.source_metadata[RETRY_START] == 4
        send.side_effect = OSError("SMTP still offline")
        for _ in range(4):
            _deliver(log)
        send.reset_mock()
        send.side_effect = None
    log.refresh_from_db(); campaign.refresh_from_db(); delivery.refresh_from_db()
    before = (log.attempts, log.error, log.updated_at, log.retry_generation, log.source_metadata)
    completed_at = campaign.completed_at
    audits = AuditLog.objects.filter(makerspace=space).count()
    assert log.attempts == attempt_limit(log)

    assert _claim_log(log.pk) is None
    for _ in range(2):
        deliver_email_task.run(log.pk)

    log.refresh_from_db(); campaign.refresh_from_db(); delivery.refresh_from_db()
    assert log.status == campaign.status == delivery.status == "failed"
    assert (log.attempts, log.error, log.updated_at, log.retry_generation, log.source_metadata) == before
    assert campaign.completed_at == completed_at
    assert AuditLog.objects.filter(makerspace=space).count() == audits
    send.assert_not_called()
    enqueue.reset_mock()
    with django_capture_on_commit_callbacks(execute=True):
        retry(actor, log)
    enqueue.assert_called_once_with(log.pk)
    log.refresh_from_db()
    assert log.source_metadata[RETRY_START] == before[0]
    assert log.status == "pending"
    deliver_email_task.run(log.pk)
    log.refresh_from_db(); campaign.refresh_from_db(); delivery.refresh_from_db()
    assert log.attempts == before[0] + 1 and send.call_count == 1
    assert log.status == campaign.status == delivery.status == "sent"


def test_failed_broadcast_with_budget_remaining_is_still_claimed(monkeypatch):
    _, actor, _, event, _ = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    send = smtp(monkeypatch)
    send.side_effect = OSError("temporary outage")
    _deliver(log)
    send.reset_mock(); send.side_effect = None
    monkeypatch.setattr("apps.integrations.tasks.record_worker_heartbeat", lambda: None)

    deliver_email_task.run(log.pk)

    log.refresh_from_db(); campaign.refresh_from_db(); delivery.refresh_from_db()
    assert log.attempts == 2 and send.call_count == 1
    assert log.status == campaign.status == delivery.status == "sent"


def test_non_campaign_failure_does_not_inherit_broadcast_budget(monkeypatch):
    space, _, user, _, _ = fixture(monkeypatch)
    log = EmailLog.objects.create(makerspace=space, to_email=user.email, subject="Ordinary mail",
                                  text_body="Stored content", status="failed", attempts=4)
    claimed = _claim_log(log.pk)
    assert claimed is not None and claimed.status == "sending"
