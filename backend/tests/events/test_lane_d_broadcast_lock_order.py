"""Cancellation can finish while a batch/completion worker waits for its tenant."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event as ThreadEvent

import pytest
from django.db import close_old_connections, connection, transaction

from apps.audit.models import AuditLog
from apps.events.services_broadcasts import change, compose
from apps.integrations.broadcasts_worker import broadcast_batch, reconcile
from apps.integrations.delivery_services import retry_delivery
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.models import EmailLog
from apps.integrations.services import retry_email_log
from apps.makerspaces.models import Makerspace
from tests.events.lane_d_helpers import fixture, queued, smtp

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("worker", [broadcast_batch, reconcile], ids=["batch", "completion"])
def test_cancellation_and_worker_use_tenant_before_campaign(monkeypatch, worker):
    space, actor, _, event, _ = fixture(monkeypatch)
    campaign = compose(event, actor, subject="Update", body="Message", statuses=["registered"])
    change(campaign, actor, "queue")
    if worker is reconcile:
        campaign.status, campaign.recipients_complete = "sending", True
        campaign.save(update_fields=["status", "recipients_complete"])
    lock_reached = ThreadEvent()
    tenant_table = f'FROM "{Makerspace._meta.db_table}"'
    campaign_table = f'FROM "{type(campaign)._meta.db_table}"'

    def observe_lock(execute, sql, params, many, context):
        # Signal before waiting for the tenant. On the regressed path, signal
        # only AFTER acquiring the campaign, reproducing the inverted order.
        if "FOR UPDATE" in sql and tenant_table in sql:
            lock_reached.set()
        result = execute(sql, params, many, context)
        if "FOR UPDATE" in sql and campaign_table in sql:
            lock_reached.set()
        return result

    def run_worker():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
            with connection.execute_wrapper(observe_lock):
                worker("event_broadcast", campaign.pk)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '5s'")
            Makerspace.objects.select_for_update().get(pk=space.pk)
            future = pool.submit(run_worker)
            assert lock_reached.wait(timeout=10), "Worker did not reach its row lock"
            change(campaign, actor, "cancel")
        future.result(timeout=10)

    campaign.refresh_from_db()
    assert campaign.status == "cancelled"
    assert not campaign.deliveries.exists()
    assert not EmailLog.objects.filter(source_kind="event_broadcast").exists()
    assert AuditLog.objects.filter(action="event.broadcast.cancelled", makerspace=space).count() == 1
    assert not AuditLog.objects.filter(action="event.broadcast.sent", makerspace=space).exists()


@pytest.mark.parametrize("retry", [retry_delivery, retry_email_log])
def test_manual_retry_and_reconciliation_use_tenant_before_campaign(monkeypatch, retry):
    space, actor, _, event, _ = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    send = smtp(monkeypatch)
    send.side_effect = OSError("SMTP offline")
    _deliver(log)
    assert log.status == "failed"
    monkeypatch.setattr("apps.integrations.services._enqueue", lambda pk: None)
    monkeypatch.setattr("apps.integrations.dispatch._enqueue", lambda pk: None)
    lock_reached = ThreadEvent()
    tenant_table = f'FROM "{Makerspace._meta.db_table}"'
    campaign_table = f'FROM "{type(campaign)._meta.db_table}"'

    def observe_lock(execute, sql, params, many, context):
        if "FOR UPDATE" in sql and tenant_table in sql:
            lock_reached.set()
        result = execute(sql, params, many, context)
        # The old path takes this lock first, then blocks on the audit's tenant FK.
        if "FOR UPDATE" in sql and campaign_table in sql:
            lock_reached.set()
        return result

    def run_retry():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
            with connection.execute_wrapper(observe_lock):
                retry(actor, log)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '5s'")
            Makerspace.objects.select_for_update().get(pk=space.pk)
            future = pool.submit(run_retry)
            assert lock_reached.wait(timeout=10), "Retry did not reach its row lock"
            # Reconciliation must be able to lock the campaign while retry waits
            # for our tenant lock. The inverted order would time out/deadlock.
            reconcile("event_broadcast", campaign.pk)
        future.result(timeout=10)

    log.refresh_from_db()
    campaign.refresh_from_db()
    delivery.refresh_from_db()
    assert log.status == delivery.status == "pending"
    assert campaign.status == "sending"
    assert AuditLog.objects.filter(
        action="event.broadcast.delivery_requeued", makerspace=space, target_id=str(delivery.pk),
    ).count() == 1
