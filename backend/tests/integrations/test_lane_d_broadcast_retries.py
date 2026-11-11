"""Manual outbox retries restore failed domain state and retain live checks."""
from tests.events.manual_grant_fixture import create_manual_grant

from unittest.mock import Mock

import pytest
from celery.result import allow_join_result, denied_join_result
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.events.models import EventRegistration, EventStaffGrant
from apps.events.services_broadcasts import change
from apps.integrations.delivery_services import retry_delivery
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.models import EmailLog
from apps.integrations.services import EmailRetryError, retry_email_log
from apps.integrations.broadcasts_delivery import RETRY_START
from apps.integrations.broadcasts_worker import resume_broadcasts
from tests.events.lane_d_helpers import fixture, queued, smtp
from tests.events.ticketing_helpers import account

pytestmark = pytest.mark.django_db


def exhaust(log, send):
    send.side_effect = OSError("SMTP offline")
    for _ in range(4):
        _deliver(log)
    assert log.status == "failed" and log.attempts == 4
    send.reset_mock()
    send.side_effect = None


@pytest.mark.parametrize("retry", [retry_delivery, retry_email_log])
def test_exhausted_campaign_manual_retry_restores_state_and_sends(
    monkeypatch, django_capture_on_commit_callbacks, retry,
):
    space, actor, user, event, registration = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    send = smtp(monkeypatch)
    exhaust(log, send)
    campaign.refresh_from_db(); delivery.refresh_from_db()
    assert campaign.status == delivery.status == "failed"
    assert campaign.completed_at is not None
    event.title = "Current retry title"
    event.save(update_fields=["title"])
    message = Mock(wraps=EmailMultiAlternatives)
    monkeypatch.setattr("apps.integrations.dispatch_delivery.EmailMultiAlternatives", message)

    def enqueue(pk):
        campaign.refresh_from_db(); delivery.refresh_from_db()
        assert campaign.status == "sending" and campaign.completed_at is None
        assert delivery.status == "pending"
        _deliver(EmailLog.objects.get(pk=pk))

    monkeypatch.setattr("apps.integrations.services._enqueue", enqueue)
    monkeypatch.setattr("apps.integrations.dispatch._enqueue", enqueue)
    with django_capture_on_commit_callbacks(execute=True):
        retry(actor, log)
    log.refresh_from_db(); campaign.refresh_from_db(); delivery.refresh_from_db()
    assert send.call_count == 1 and log.attempts == 5
    assert log.status == campaign.status == delivery.status == "sent"
    assert "Current retry title" in message.call_args.kwargs["body"]
    assert AuditLog.objects.filter(action="event.broadcast.delivery_requeued", makerspace=space).exists()


@pytest.mark.parametrize("retry", [retry_delivery, retry_email_log])
@pytest.mark.parametrize("invalidate", ["sender", "recipient", "module", "cancel"])
def test_manual_retry_keeps_live_authority_eligibility_and_cancellation_checks(
    monkeypatch, django_capture_on_commit_callbacks, retry, invalidate,
):
    space, actor, user, event, registration = fixture(monkeypatch)
    sender = account("retry-sender")
    grant = create_manual_grant(makerspace=space, event=event, user=sender,
                                          granted_by=actor, permissions=["manage_registrations"])
    campaign, delivery, log = queued(event, sender, statuses=["registered"])
    send = smtp(monkeypatch)
    # Cancellation is possible while deliveries are still retrying, before exhaustion.
    if invalidate == "cancel":
        send.side_effect = OSError("offline")
        _deliver(log)
        change(campaign, sender, "cancel")
        send.reset_mock(); send.side_effect = None
    else:
        exhaust(log, send)
        if invalidate == "sender":
            grant.revoked_at = timezone.now(); grant.save(update_fields=["revoked_at"])
        elif invalidate == "recipient":
            EventRegistration.objects.filter(pk=registration.pk).update(status="cancelled")
        else:
            space.enabled_modules.remove("events"); space.save(update_fields=["enabled_modules"])
    enqueue = lambda pk: _deliver(EmailLog.objects.get(pk=pk))
    monkeypatch.setattr("apps.integrations.services._enqueue", enqueue)
    monkeypatch.setattr("apps.integrations.dispatch._enqueue", enqueue)
    if invalidate == "cancel":
        with pytest.raises((ValidationError, EmailRetryError)), django_capture_on_commit_callbacks(execute=True):
            retry(actor, log)
        campaign.refresh_from_db(); log.refresh_from_db()
        assert campaign.status == "cancelled" and log.status == "failed"
    else:
        with django_capture_on_commit_callbacks(execute=True):
            retry(actor, log)
        log.refresh_from_db(); delivery.refresh_from_db()
        assert log.status == delivery.status == "skipped"
    assert not send.called


@pytest.mark.parametrize("retry", [retry_delivery, retry_email_log])
def test_manual_retry_rolls_back_domain_state_if_outbox_save_fails(monkeypatch, retry):
    space, actor, user, event, registration = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    exhaust(log, smtp(monkeypatch))
    campaign.refresh_from_db()
    completed_at = campaign.completed_at
    original_save = EmailLog.save

    def fail_pending(self, *args, **kwargs):
        if self.pk == log.pk and self.status == "pending":
            raise RuntimeError("outbox update failed")
        return original_save(self, *args, **kwargs)

    monkeypatch.setattr(EmailLog, "save", fail_pending)
    with pytest.raises(RuntimeError, match="outbox update failed"):
        retry(actor, log)
    log.refresh_from_db(); campaign.refresh_from_db(); delivery.refresh_from_db()
    assert log.status == campaign.status == delivery.status == "failed"
    assert campaign.completed_at == completed_at
    assert RETRY_START not in log.source_metadata
    assert not AuditLog.objects.filter(action="event.broadcast.delivery_requeued", makerspace=space).exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("retry", [retry_delivery, retry_email_log])
@pytest.mark.parametrize("join_guard", [allow_join_result, denied_join_result])
def test_manual_retry_transient_failure_survives_real_celery_retry(
    monkeypatch, django_capture_on_commit_callbacks, retry, join_guard,
):
    from apps.integrations.tasks import deliver_email_task

    space, actor, user, event, registration = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    send = smtp(monkeypatch)
    exhaust(log, send)
    send.side_effect = [OSError("temporary SMTP outage"), 1]
    monkeypatch.setattr("apps.integrations.tasks.record_worker_heartbeat", lambda: None)
    def enqueue(pk):
        # Eager Celery follows Retry.sig only when Retry is captured by its tracer.
        # Propagate terminal errors after the real retry chain has completed.
        result = deliver_email_task.apply(args=(pk,), throw=False)
        # apply() returned a completed EagerResult: no worker subtask is being
        # joined, regardless of Celery's process-wide join guard from other tests.
        result.get(propagate=True, disable_sync_subtasks=False)

    monkeypatch.setattr("apps.integrations.services._enqueue", enqueue)
    monkeypatch.setattr("apps.integrations.dispatch._enqueue", enqueue)
    with join_guard(), django_capture_on_commit_callbacks(execute=True):
        retry(actor, log)
    log.refresh_from_db(); campaign.refresh_from_db(); delivery.refresh_from_db()
    assert send.call_count == 2
    assert log.attempts == 6 and log.source_metadata[RETRY_START] == 4
    assert log.status == campaign.status == delivery.status == "sent"


@pytest.mark.parametrize("retry", [retry_delivery, retry_email_log])
@pytest.mark.parametrize("initial_attempts", [1, 4])
def test_renewed_budget_recovery_exhaustion_and_another_manual_retry(
    monkeypatch, django_capture_on_commit_callbacks, retry, initial_attempts,
):
    from apps.integrations import delivery_sources

    space, actor, user, event, registration = fixture(monkeypatch)
    campaign, delivery, log = queued(event, actor, statuses=["registered"])
    send = smtp(monkeypatch)
    send.side_effect = OSError("SMTP offline")
    for _ in range(initial_attempts):
        _deliver(log)
    enqueue = Mock()
    monkeypatch.setattr("apps.integrations.services._enqueue", enqueue)
    monkeypatch.setattr("apps.integrations.dispatch._enqueue", enqueue)
    with django_capture_on_commit_callbacks(execute=True):
        retry(actor, log)
    log.refresh_from_db()
    assert log.attempts == log.source_metadata[RETRY_START] == initial_attempts
    # Three failures remain pending even if lifetime attempts have exceeded four.
    for _ in range(3):
        _deliver(log)
    log.refresh_from_db(); campaign.refresh_from_db(); delivery.refresh_from_db()
    assert campaign.status == "sending" and campaign.completed_at is None
    assert delivery.status == "pending" and log.status == "failed"
    recovered = Mock()
    monkeypatch.setattr("apps.integrations.dispatch_outbox._enqueue", recovered)
    resume_broadcasts()
    recovered.assert_called_once_with(log.pk)
    # A crash after the final failure commits must reconcile as exhausted,
    # rather than enqueue a fresh task with an unbounded retry budget.
    finished = delivery_sources.finished
    monkeypatch.setattr(delivery_sources, "finished", Mock(side_effect=RuntimeError("callback crash")))
    with pytest.raises(RuntimeError, match="callback crash"):
        _deliver(log)
    monkeypatch.setattr(delivery_sources, "finished", finished)
    recovered.reset_mock()
    resume_broadcasts()
    recovered.assert_not_called()
    log.refresh_from_db(); campaign.refresh_from_db(); delivery.refresh_from_db()
    assert log.attempts == initial_attempts + 4
    assert log.status == campaign.status == delivery.status == "failed"
    with django_capture_on_commit_callbacks(execute=True):
        retry(actor, log)
    log.refresh_from_db()
    assert log.source_metadata[RETRY_START] == initial_attempts + 4
    send.side_effect = None
    _deliver(log)
    log.refresh_from_db(); campaign.refresh_from_db(); delivery.refresh_from_db()
    assert log.attempts == initial_attempts + 5
    assert log.status == campaign.status == delivery.status == "sent"
