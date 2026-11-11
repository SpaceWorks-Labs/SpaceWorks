from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.integrations.messaging import worker
from apps.integrations.messaging.transport import SendResult
from apps.integrations.models import MessagingDelivery, MessagingRecipientCorrelation
from tests.messaging.helpers_m1h_b import setup_pipeline

pytestmark = pytest.mark.django_db


@pytest.fixture
def pipeline(space, member):
    return setup_pipeline(space, member)


def test_pending_snapshot_cannot_resubmit_another_workers_crashed_probe(pipeline):
    row = pipeline.enqueue(channel="whatsapp")
    resolve = worker.resolve_sender
    paused = False

    def resume_after_crash(*args, **kwargs):
        nonlocal paused
        if not paused:
            # A already read pending. B claims, submits and crashes before completion.
            paused = True
            with pytest.raises(RuntimeError, match="crashed after submission"):
                worker.deliver(row.pk)
            MessagingDelivery.objects.filter(pk=row.pk).update(lease_until=timezone.now() - timedelta(seconds=1))
        return resolve(*args, **kwargs)

    with patch.object(worker, "resolve_sender", side_effect=resume_after_crash), patch.object(
        worker, "send_message", side_effect=RuntimeError("crashed after submission")) as send:
        worker.deliver(row.pk)
    assert send.call_count == 1
    row.refresh_from_db()
    assert (row.status, row.error_code, row.attempts) == ("failed", "ambiguous_timeout", 2)
    assert MessagingRecipientCorrelation.objects.get().probe_delivery_id == row.pk


@pytest.mark.parametrize("result,max_attempts", [
    (SendResult(error_code="190", permanent=True), 4),
    (SendResult(error_code="132001", permanent=True), 4),
    (SendResult(error_code="130429", retryable=True), 1),
])
def test_definitively_rejected_probe_releases_phone_for_later_delivery(pipeline, result, max_attempts):
    first = pipeline.enqueue(channel="whatsapp")
    MessagingDelivery.objects.filter(pk=first.pk).update(max_attempts=max_attempts)
    with patch.object(worker, "send_message", return_value=result):
        worker.deliver(first.pk)
    first.refresh_from_db()
    assert first.status == "failed"
    assert not MessagingRecipientCorrelation.objects.exists()
    second = pipeline.enqueue(channel="whatsapp", key="after-credential-repair")
    with patch.object(worker, "send_message", return_value=SendResult(message_id="wamid.repaired")) as send:
        worker.deliver(second.pk)
    send.assert_called_once()
    assert MessagingRecipientCorrelation.objects.get().probe_delivery_id == second.pk


def test_local_template_failure_never_reserves_a_probe(pipeline):
    row = pipeline.enqueue(channel="whatsapp")
    MessagingDelivery.objects.filter(pk=row.pk).update(context={"unreviewed": "forbidden"})
    with patch.object(worker, "send_message") as send:
        worker.deliver(row.pk)
    send.assert_not_called()
    row.refresh_from_db()
    assert row.error_code == "template_rejected"
    assert not MessagingRecipientCorrelation.objects.exists()


def test_early_acceptance_prevents_rejection_from_releasing_probe(pipeline):
    from apps.integrations.messaging.webhook_processing import accept_event
    row = pipeline.enqueue(channel="whatsapp")

    def send(*args, **kwargs):
        accept_event(provider="meta", channel="whatsapp", sender_key=pipeline.wa.sender_key,
            dedupe_id="early:failed", kind="status", payload={"message_id": "wamid.early",
                "delivery_id": str(row.pk), "status": "failed"})
        return SendResult(error_code="190", permanent=True)

    with patch.object(worker, "send_message", side_effect=send):
        worker.deliver(row.pk)
    assert MessagingRecipientCorrelation.objects.get().probe_delivery_id == row.pk
