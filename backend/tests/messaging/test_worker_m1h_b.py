from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.integrations.messaging.transport import SendResult
from apps.integrations.messaging.worker import claim, complete, deliver
from apps.integrations.models import MessagingDelivery, MessagingSuppression
from tests.messaging.helpers_m1h_b import setup_pipeline

pytestmark = pytest.mark.django_db


@pytest.fixture
def pipeline(space, member):
    return setup_pipeline(space, member)


def test_lease_fences_stale_worker_completion(pipeline):
    row = pipeline.enqueue()
    old = claim(row.pk)
    MessagingDelivery.objects.filter(pk=row.pk).update(lease_until=timezone.now() - timedelta(seconds=1))
    current = claim(row.pk)
    assert current != old
    assert not complete(row.pk, old, pipeline.sms, SendResult(message_id="SMstale"))
    assert complete(row.pk, current, pipeline.sms, SendResult(message_id="SMcurrent"))
    row.refresh_from_db()
    assert row.provider_message_id == "SMcurrent" and row.progress_rank == 1


def test_retry_and_crash_do_not_reserve_quota_again(pipeline):
    row = pipeline.enqueue()
    reserved = row.quota_reserved_at
    with patch("apps.makerspaces.limits.reserve_notification_quota", side_effect=AssertionError("reserved twice")), patch(
        "apps.integrations.messaging.worker.send_message", return_value=SendResult(error_code="20429", retryable=True)):
        deliver(row.pk)
    row.refresh_from_db()
    assert row.status == "pending" and row.attempts == 1 and row.next_attempt_at > timezone.now()
    assert row.quota_reserved_at == reserved


@pytest.mark.parametrize("code,reason", [("21610", "provider_opt_out"), ("21211", "permanent_failure"), ("21614", "permanent_failure")])
def test_permanent_phone_errors_suppress(pipeline, code, reason):
    row = pipeline.enqueue()
    with patch("apps.integrations.messaging.worker.send_message", return_value=SendResult(error_code=code, permanent=True)):
        deliver(row.pk)
    row.refresh_from_db()
    assert row.status == "failed" and row.error_code == code
    assert MessagingSuppression.objects.get(sender_key=pipeline.sms.sender_key).reason == reason
    assert pipeline.enqueue(key="next").status == "suppressed"


def test_template_errors_are_failed_template_rejected(pipeline):
    row = pipeline.enqueue(channel="whatsapp")
    with patch("apps.integrations.messaging.worker.send_message", return_value=SendResult(error_code="132001", permanent=True)):
        deliver(row.pk)
    row.refresh_from_db()
    assert (row.status, row.error_code) == ("failed", "template_rejected")


def test_acceptance_never_lowers_callback_progress(pipeline):
    from apps.integrations.messaging.webhook_processing import accept_event
    row = pipeline.enqueue(channel="whatsapp")
    def send(*args, **kwargs):
        accept_event(provider="meta", channel="whatsapp", sender_key=pipeline.wa.sender_key,
            dedupe_id="wamid.early:read", kind="status", payload={"message_id": "wamid.early", "status": "read",
                "delivery_id": str(row.pk), "phone_hash": "", "alias_hash": "known-alias"})
        return SendResult(message_id="wamid.early")
    with patch("apps.integrations.messaging.worker.send_message", side_effect=send):
        deliver(row.pk)
    row.refresh_from_db()
    assert row.status == "read" and row.progress_rank == 4
    assert row.read_at is None  # Callback did not provide a provider timestamp.


def test_exhausted_expired_claim_and_stale_recovery(pipeline):
    from apps.integrations.messaging.sweep import run_sweep
    exhausted = pipeline.enqueue(key="exhausted")
    stale = pipeline.enqueue(key="stale")
    MessagingDelivery.objects.filter(pk=exhausted.pk).update(status="sending", attempts=4,
        lease_token=uuid4(), lease_until=timezone.now() - timedelta(seconds=1))
    MessagingDelivery.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(days=8),
        next_attempt_at=timezone.now() + timedelta(days=365))
    with patch("apps.integrations.messaging.sweep.schedule_delivery"):
        run_sweep()
    exhausted.refresh_from_db(); stale.refresh_from_db()
    assert (exhausted.status, exhausted.error_code) == ("failed", "attempts_exhausted")
    assert (stale.status, stale.error_code) == ("failed", "stale")
