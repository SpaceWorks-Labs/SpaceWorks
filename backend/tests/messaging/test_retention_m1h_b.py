from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.integrations.messaging.sweep import run_sweep
from apps.integrations.messaging.webhook_processing import accept_event
from apps.integrations.models import MessagingDelivery, MessagingWebhookEvent
from tests.messaging.helpers_m1h_b import setup_pipeline

pytestmark = pytest.mark.django_db


def test_retention_uses_derived_status_90_or_365_days(space, member):
    p = setup_pipeline(space, member)
    rows = {}
    for state in ("accepted", "sent", "delivered", "read", "skipped", "suppressed", "failed"):
        row = p.enqueue(key=state)
        MessagingDelivery.objects.filter(pk=row.pk).update(status=state, created_at=timezone.now() - timedelta(days=91))
        rows[state] = row.pk
    with patch("apps.integrations.messaging.sweep.schedule_delivery"):
        run_sweep()
    assert list(MessagingDelivery.objects.filter(pk__in=rows.values()).values_list("status", flat=True)) == ["failed"]
    MessagingDelivery.objects.filter(pk=rows["failed"]).update(created_at=timezone.now() - timedelta(days=366))
    run_sweep()
    assert not MessagingDelivery.objects.filter(pk=rows["failed"]).exists()


def test_accepted_then_failed_keeps_failed_retention(space, member):
    p = setup_pipeline(space, member)
    row = p.enqueue()
    MessagingDelivery.objects.filter(pk=row.pk).update(provider_message_id="SMretention", progress_rank=1,
        status="accepted", created_at=timezone.now() - timedelta(days=100))
    accept_event(provider="twilio", channel="sms", sender_key=p.sms.sender_key, dedupe_id="SMretention:failed",
        kind="status", payload={"message_id": "SMretention", "status": "failed"})
    run_sweep()
    row.refresh_from_db()
    assert row.status == "failed" and row.progress_rank == 1


def test_webhook_retry_abandon_and_deletion_are_bounded(space, member):
    p = setup_pipeline(space, member)
    event = accept_event(provider="twilio", channel="sms", sender_key=p.sms.sender_key,
        dedupe_id="early:sent", kind="status", payload={"message_id": "SMmissing", "status": "sent"})
    MessagingWebhookEvent.objects.filter(pk=event.pk).update(received_at=timezone.now() - timedelta(days=31),
        next_attempt_at=timezone.now() - timedelta(seconds=1))
    run_sweep()
    event.refresh_from_db()
    assert event.state == "abandoned"
    MessagingWebhookEvent.objects.filter(pk=event.pk).update(processed_at=timezone.now() - timedelta(days=31))
    run_sweep()
    assert not MessagingWebhookEvent.objects.filter(pk=event.pk).exists()


def test_processed_webhook_retention_uses_processing_time(space, member):
    p = setup_pipeline(space, member)
    event = accept_event(provider="twilio", channel="sms", sender_key=p.sms.sender_key, dedupe_id="inbound:help",
                         kind="inbound", payload={"stop": False})
    MessagingWebhookEvent.objects.filter(pk=event.pk).update(received_at=timezone.now() - timedelta(days=60))
    run_sweep()
    assert MessagingWebhookEvent.objects.filter(pk=event.pk).exists()
    MessagingWebhookEvent.objects.filter(pk=event.pk).update(processed_at=timezone.now() - timedelta(days=31))
    run_sweep()
    assert not MessagingWebhookEvent.objects.filter(pk=event.pk).exists()
