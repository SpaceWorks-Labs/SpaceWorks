"""An older worker completion cannot acknowledge a newer document recovery."""
from datetime import timedelta
from threading import Event, Thread
from unittest.mock import Mock, patch

import pytest
from django.db import close_old_connections, connection, connections, transaction
from django.utils import timezone

from apps.integrations.mail_providers.delivery import send as smtp_send
from apps.integrations.models import EmailLog
from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.notification_outbox import mark_processed
from apps.integrations.notification_providers import ProviderResult
from apps.integrations.notification_tasks import deliver_envelope, runnable_deliveries
from apps.notifications.models_preferences import NotificationPreference
from apps.payments.notifications_p2 import notify_document
from tests.billing_docs.test_email_recovery import set_switch
from tests.billing_docs.test_email_recovery_history import remove_marker
from tests.billing_docs.test_email_recovery_refusals import DISABLED, assert_direct_skip, emit_document
from tests.billing_docs.test_r2_delivery import provider
from tests.billing_docs.test_r2_email import assert_mail_owner, document_ledger_snapshot

from tests.billing_docs.email_recovery_helpers import intent_state

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("pre_marker", [False, True])
def test_old_telegram_completion_preserves_new_explicit_missing_email_recovery(
        document, document_mail, lane, settings, monkeypatch, pre_marker,
        django_capture_on_commit_callbacks, mailoutbox):
    assert connection.vendor == "postgresql"
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    smtp = Mock(wraps=smtp_send)
    monkeypatch.setattr("apps.integrations.mail_providers.delivery.send", smtp)
    envelope = document_mail.route("envelope")
    NotificationPreference.objects.filter(makerspace=lane.space, user=document.payment.member,
        category="payments").update(channels=["email", "telegram"], email_fallback=True)
    fake = provider(monkeypatch, [ProviderResult(False, retryable=True, error_code="unavailable"),
                                 ProviderResult(True, "retry-document-id")])
    original = document_ledger_snapshot(document)
    set_switch(lane.space, "email", False)
    emit_document(document, django_capture_on_commit_callbacks)
    deliver_envelope(envelope.pk)
    envelope.refresh_from_db()
    assert envelope.processed_at is not None
    telegram = envelope.deliveries.get(channel="telegram")
    assert (telegram.state, telegram.last_error, telegram.attempt_count, telegram.retryable) == (
        "retrying", "unavailable", 1, True)
    assert telegram.next_attempt_at > timezone.now() and telegram.claim_until is None
    history = EmailLog.objects.values().get(event="document_issued")
    assert_direct_skip(history, envelope, DISABLED)
    if pre_marker:
        remove_marker(envelope)
        assert "_disabled_dispatch" not in envelope.routing_snapshot
    else:
        assert intent_state(envelope).reason == DISABLED
        assert intent_state(envelope).state == "skipped_disabled"
    assert envelope.deliveries.count() == 1
    assert envelope.deliveries.filter(channel="email").count() == 0
    assert len(fake.documents) == 1 and fake.texts == []
    assert document_mail.rendered == [document.pk] and mailoutbox == []
    smtp.assert_not_called()
    queued = lane.enqueued.count(envelope.pk)
    set_switch(lane.space, "email", True)
    assert lane.enqueued.count(envelope.pk) == queued
    NotificationDelivery.objects.filter(pk=telegram.pk).update(
        next_attempt_at=timezone.now() - timedelta(seconds=1))

    paused, release, completed = Event(), Event(), Event()
    errors, worker_pids = [], []
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        producer_pid = cursor.fetchone()[0]

    def pause_completion(current):
        assert current.pk == envelope.pk
        assert not connections["default"].in_atomic_block
        paused.set()
        assert release.wait(10), "Recovery producer did not release the old worker"
        mark_processed(current)
        completed.set()

    def retry_worker():
        close_old_connections()
        db = connections["default"]
        try:
            with db.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
                cursor.execute("SET statement_timeout = '8s'")
                cursor.execute("SELECT pg_backend_pid()")
                worker_pids.append(cursor.fetchone()[0])
            deliver_envelope(envelope.pk)
        except BaseException as exc:
            errors.append(exc)
        finally:
            db.close()

    worker = Thread(target=retry_worker, daemon=True)
    with patch("apps.integrations.notification_outbox.mark_processed", side_effect=pause_completion) as finish:
        try:
            worker.start()
            assert paused.wait(5), "Old worker did not reach completion after its Telegram send"
            assert len(worker_pids) == 1 and worker_pids[0] != producer_pid
            telegram.refresh_from_db()
            assert (telegram.state, telegram.last_error, telegram.attempt_count, telegram.retryable) == (
                "accepted", "", 2, False)
            assert telegram.provider_id == "retry-document-id"
            assert telegram.next_attempt_at is None and telegram.claim_until is None
            telegram_history = NotificationDelivery.objects.values().get(pk=telegram.pk)
            assert len(fake.documents) == 2 and fake.texts == []
            assert document_mail.rendered == [document.pk] * 2
            assert envelope.deliveries.filter(channel="email").count() == 0
            assert not runnable_deliveries(envelope.deliveries.all()).exists()
            smtp.assert_not_called()
            assert mailoutbox == []

            # A different connection commits approval while the old pass is paused.
            document.makerspace.refresh_from_db()
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '5s'")
                    cursor.execute("SET LOCAL statement_timeout = '8s'")
                notify_document(document)
            assert lane.enqueued.count(envelope.pk) == queued + 1
            approved = NotificationEnvelope.objects.values().get(pk=envelope.pk)
            assert approved["processed_at"] is None
            assert intent_state(envelope).state == "recovery_approved"
            assert intent_state(envelope).generation == 1
            assert envelope.deliveries.filter(channel="email").count() == 0
            assert EmailLog.objects.filter(event="document_issued").count() == 1
            assert EmailLog.objects.values().get(pk=history["id"]) == history
            smtp.assert_not_called()
        finally:
            release.set()
            worker.join(timeout=12)
        assert not worker.is_alive(), "Old worker exceeded its bounded timeout"
        assert errors == [] and completed.is_set()
        assert finish.call_count == 1

    # No runnable leg remains: the recovery wake-up itself must survive completion.
    assert NotificationEnvelope.objects.values().get(pk=envelope.pk) == approved
    assert not runnable_deliveries(envelope.deliveries.all()).exists()
    assert NotificationDelivery.objects.values().get(pk=telegram.pk) == telegram_history
    assert EmailLog.objects.values().get(pk=history["id"]) == history
    assert document_ledger_snapshot(document) == original
    assert smtp.call_count == 0 and mailoutbox == []
    deliver_envelope(lane.enqueued[-1])
    envelope.refresh_from_db()
    assert envelope.processed_at is not None
    assert envelope.routing_snapshot == approved["routing_snapshot"]
    assert lane.enqueued.count(envelope.pk) == queued + 1
    assert envelope.deliveries.count() == 2
    assert envelope.deliveries.filter(channel="email").count() == 1
    email = envelope.deliveries.get(channel="email")
    assert (email.state, email.last_error, email.attempt_count, email.retryable) == ("sent", "", 1, False)
    assert email.next_attempt_at is None and email.claim_until is None
    sent = assert_mail_owner(document, "envelope", envelope, skipped_direct=1)
    assert (sent.status, sent.error, sent.attempts) == ("sent", "", 1)
    assert smtp.call_count == 1
    assert len(mailoutbox) == 1 and mailoutbox[0].to == [document.payment.member.email]
    assert mailoutbox[0].attachments == [
        (f"{document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-3", "application/pdf")]
    assert document_mail.rendered == [document.pk] * 3
    assert len(fake.documents) == 2 and fake.texts == []
    assert NotificationDelivery.objects.values().get(pk=telegram.pk) == telegram_history
    assert EmailLog.objects.values().get(pk=history["id"]) == history
    assert document_ledger_snapshot(document) == original

    final_envelope = NotificationEnvelope.objects.values().get(pk=envelope.pk)
    final_deliveries = list(envelope.deliveries.order_by("pk").values())
    final_logs = list(EmailLog.objects.filter(event="document_issued").order_by("pk").values())
    for _ in range(2):
        emit_document(document, django_capture_on_commit_callbacks)
        deliver_envelope(envelope.pk)
    assert lane.enqueued.count(envelope.pk) == queued + 1
    assert NotificationEnvelope.objects.values().get(pk=envelope.pk) == final_envelope
    assert list(envelope.deliveries.order_by("pk").values()) == final_deliveries
    assert list(EmailLog.objects.filter(event="document_issued").order_by("pk").values()) == final_logs
    assert smtp.call_count == 1 and len(mailoutbox) == 1
    assert document_mail.rendered == [document.pk] * 3
    assert len(fake.documents) == 2 and fake.texts == []
    assert document_ledger_snapshot(document) == original
