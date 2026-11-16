"""Late SMTP/recovery snapshots cannot overwrite a newer manual retry."""

from unittest.mock import Mock

import pytest
from django.db import connection

from apps.audit.models import AuditLog
from apps.integrations.broadcasts_delivery import RETRY_START, finished
from apps.integrations.delivery_services import retry_delivery
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.models import EmailLog
from apps.integrations.services import retry_email_log
from apps.integrations.tasks import _claim_log
from apps.makerspaces.models import Makerspace
from tests.events.lane_d_helpers import fixture, queued, smtp
from tests.integrations.test_lane_d_broadcast_retries import exhaust

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("retry", [retry_delivery, retry_email_log])
@pytest.mark.parametrize("current", ["pending", "sending", "failed", "sent"])
def test_stale_failure_callback_observes_current_retry(
    monkeypatch, django_capture_on_commit_callbacks, retry, current,
):
    space, actor, _, event, _ = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    send = smtp(monkeypatch)
    exhaust(log, send)
    stale = EmailLog.objects.get(pk=log.pk)
    enqueue = Mock()
    monkeypatch.setattr("apps.integrations.services._enqueue", enqueue)
    monkeypatch.setattr("apps.integrations.dispatch._enqueue", enqueue)
    with django_capture_on_commit_callbacks(execute=True):
        retry(actor, log)
    enqueue.assert_called_once_with(log.pk)
    log.refresh_from_db()
    if current == "sending":
        _claim_log(log.pk)
    elif current in {"failed", "sent"}:
        send.side_effect = OSError("temporary outage") if current == "failed" else None
        _deliver(log)
    failures = AuditLog.objects.filter(action="event.broadcast.delivery_failed", makerspace=space).count()

    finished(stale)

    log.refresh_from_db(); campaign.refresh_from_db(); delivery.refresh_from_db()
    assert log.status == current and log.source_metadata[RETRY_START] == 4
    assert log.attempts == (5 if current in {"failed", "sent"} else 4)
    assert delivery.status == ("sent" if current == "sent" else "pending")
    assert campaign.status == ("sent" if current == "sent" else "sending")
    assert AuditLog.objects.filter(action="event.broadcast.delivery_failed", makerspace=space).count() == failures
    # A retry queued before the stale callback must still pass prepare() and send.
    if current != "sent":
        send.side_effect = None
        _deliver(log)
        log.refresh_from_db(); campaign.refresh_from_db(); delivery.refresh_from_db()
        assert log.status == campaign.status == delivery.status == "sent"


def test_completion_locks_outbox_before_domain_rows(monkeypatch):
    space, actor, _, event, _ = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    send = smtp(monkeypatch)
    send.side_effect = OSError("offline")
    # Leave SMTP's fourth failure committed while the domain callback is lost.
    callback = Mock()
    monkeypatch.setattr("apps.integrations.delivery_sources.finished", callback)
    for _ in range(4):
        _deliver(log)
    assert callback.call_count == 4
    locks = []
    tables = [EmailLog._meta.db_table, Makerspace._meta.db_table,
              type(campaign)._meta.db_table, type(delivery)._meta.db_table]

    def observe(execute, sql, params, many, context):
        if "FOR UPDATE" in sql:
            locks.extend(table for table in tables if f'FROM "{table}"' in sql)
        return execute(sql, params, many, context)

    with connection.execute_wrapper(observe):
        finished(log)

    assert locks[:4] == tables
    campaign.refresh_from_db(); delivery.refresh_from_db()
    assert campaign.status == delivery.status == "failed"


@pytest.mark.parametrize("retry", [retry_delivery, retry_email_log])
def test_recovery_snapshot_fetched_before_manual_retry_cannot_fail_campaign(
    monkeypatch, django_capture_on_commit_callbacks, retry,
):
    from apps.integrations import broadcasts_worker

    space, actor, _, event, _ = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    send = smtp(monkeypatch)
    send.side_effect = OSError("offline")
    with monkeypatch.context() as patch:
        patch.setattr("apps.integrations.delivery_sources.finished", Mock())
        for _ in range(4):
            _deliver(log)
    # Recovery fetches the terminal outbox while its domain row is still pending.
    assert log.status == "failed" and log.attempts == 4
    recover = broadcasts_worker.recover_for_tenant
    manual_enqueue, recovered_enqueue = Mock(), Mock()
    monkeypatch.setattr("apps.integrations.services._enqueue", manual_enqueue)
    monkeypatch.setattr("apps.integrations.dispatch._enqueue", manual_enqueue)
    monkeypatch.setattr("apps.integrations.dispatch_outbox._enqueue", recovered_enqueue)
    fetched = []

    def retry_after_fetch(makerspace_id, **kwargs):
        if kwargs["operation"] == "broadcast_reconcile":
            stale = kwargs["args"][0]
            fetched.append(stale.pk)
            assert stale.status == "failed" and stale.attempts == 4
            with django_capture_on_commit_callbacks(execute=True):
                retry(actor, log)
        return recover(makerspace_id, **kwargs)

    monkeypatch.setattr(broadcasts_worker, "recover_for_tenant", retry_after_fetch)
    broadcasts_worker.resume_broadcasts()
    assert fetched == [log.pk]
    manual_enqueue.assert_called_once_with(log.pk)
    recovered_enqueue.assert_called_once_with(log.pk)
    log.refresh_from_db(); campaign.refresh_from_db(); delivery.refresh_from_db()
    assert log.status == delivery.status == "pending" and campaign.status == "sending"
    send.side_effect = None
    _deliver(log)
    log.refresh_from_db(); campaign.refresh_from_db(); delivery.refresh_from_db()
    assert log.status == campaign.status == delivery.status == "sent"
