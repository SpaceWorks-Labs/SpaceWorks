"""History truth table at both reservations, independent of processed_at."""
from itertools import product
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.mail_providers.delivery import send as smtp_send
from apps.integrations.models import EmailLog
from apps.integrations.models_document_email import DocumentEmailIntent
from apps.integrations.notification_delivery import ensure_deliveries, send
from apps.notifications.models_preferences import NotificationPreference
from apps.payments.notifications_p2 import notify_document
from tests.billing_docs.test_email_recovery_orderings import DISABLED, business_snapshot
from tests.billing_docs.test_email_recovery_quota import reserve

pytestmark = pytest.mark.django_db
HISTORIES = {
    "reasonless": [],
    "disabled": [("skipped", DISABLED)],
    "source_disabled": [("skipped", "notification_source_disabled")],
    "permanent": [("skipped", "email_member_opted_out")],
    "in_flight": [("pending", "")],
    "sent": [("sent", "")],
    "failed": [("failed", "timeout")],
    "ambiguous": [("skipped", "")],
    "disabled_permanent": [("skipped", DISABLED), ("skipped", "email_member_opted_out")],
    "disabled_in_flight": [("skipped", DISABLED), ("pending", "")],
    "disabled_sent": [("skipped", DISABLED), ("sent", "")],
    "disabled_failed": [("skipped", DISABLED), ("failed", "timeout")],
}
CASES = list(product(HISTORIES, [False, True], ["worker", "explicit", "direct"]))


def record_history(envelope, facts):
    # Pre-530 histories have no state record, including reasonless pending rows.
    DocumentEmailIntent.objects.filter(document_id=envelope.source_id).delete()
    for status, error in facts:
        EmailLog.objects.create(makerspace_id=envelope.makerspace_id, recipient_id=envelope.recipient_id,
            source_kind="notification.direct", source_id=envelope.pk, event=envelope.event,
            stream=envelope.stream, status=status, error=error, attempts=int(status == "sent"),
            email_retryable=False if status == "failed" else True,
            source_metadata={"p2_direct": envelope.dedup_key})
    return list(EmailLog.objects.filter(source_id=envelope.pk, event=envelope.event).order_by("pk").values())


@pytest.mark.parametrize("history,processed,entry", CASES, ids=["-".join(map(str, row)) for row in CASES])
def test_email_history_controls_every_reservation_not_completion_time(
        document, document_mail, lane, settings, monkeypatch, history, processed, entry,
        django_capture_on_commit_callbacks, mailoutbox):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    envelope = document_mail.route("direct" if entry == "direct" else "envelope")
    NotificationPreference.objects.filter(makerspace=lane.space, user=document.payment.member,
        category="payments").update(channels=["email"], email_fallback=False)
    envelope.processed_at = timezone.now() if processed else None
    envelope.save(update_fields=["processed_at"])
    retained = record_history(envelope, HISTORIES[history])
    original = business_snapshot(lane.space)
    queued = lane.enqueued.count(envelope.pk)
    smtp = Mock(wraps=smtp_send)
    monkeypatch.setattr("apps.integrations.mail_providers.delivery.send", smtp)
    recoverable = history in {"disabled", "source_disabled"}
    allowed = recoverable and entry != "worker"
    if entry == "direct":
        with patch("apps.integrations.dispatch_outbox._enqueue") as enqueue:
            with django_capture_on_commit_callbacks(execute=True):
                log = reserve(document.pk, envelope)
        if allowed:
            assert (log.status, log.error, log.attempts) == ("pending", "", 0)
            enqueue.assert_called_once_with(log.pk)
            _deliver(log)
        else:
            enqueue.assert_not_called()
            expected_log = next((row for row in retained if row["status"] != "skipped"
                or row["error"] not in {"", DISABLED, "notification_source_disabled"}), None)
            assert (log.pk if log else None) == (expected_log["id"] if expected_log else None)
        assert envelope.deliveries.filter(channel="email").count() == 0
    else:
        if entry == "explicit":
            document.makerspace.refresh_from_db()
            with django_capture_on_commit_callbacks(execute=True):
                notify_document(document)
        # The public reservation helper must honor history even when passed a
        # completed envelope, or a pending envelope with a retained direct skip.
        ensure_deliveries(envelope)
        assert envelope.deliveries.filter(channel="email").count() == int(allowed)
        if allowed:
            leg = envelope.deliveries.get(channel="email")
            assert (leg.state, leg.last_error, leg.attempt_count) == ("retrying", "", 0)
            send(leg.pk)
            leg.refresh_from_db()
            assert (leg.state, leg.last_error, leg.attempt_count, leg.retryable) == ("sent", "", 1, False)
    assert lane.enqueued.count(envelope.pk) == queued + int(recoverable and entry == "explicit")
    envelope.refresh_from_db()
    intent = DocumentEmailIntent.objects.get(document_id=envelope.source_id)
    assert intent.generation == int(recoverable and allowed)
    assert intent.state == ("sent" if allowed or "in_flight" in history or "sent" in history or "failed" in history else
        "skipped_permanent" if "permanent" in history else "skipped_disabled" if recoverable else "unknown_legacy")
    if "failed" in history:
        owner = next(row for row in retained if row["status"] == "failed")
        assert (intent.owner_kind, intent.owner_id, intent.email_log_id) == ("direct", owner["id"], owner["id"])
    logs = EmailLog.objects.filter(source_id=envelope.pk, event=envelope.event)
    assert logs.count() == len(retained) + int(allowed)
    assert list(logs.filter(pk__in=[row["id"] for row in retained]).order_by("pk").values()) == retained
    assert logs.filter(status="skipped").count() == sum(row["status"] == "skipped" for row in retained)
    assert smtp.call_count == int(allowed) and len(mailoutbox) == int(allowed)
    assert document_mail.rendered == [document.pk] * int(allowed)
    if allowed:
        sent = logs.exclude(pk__in=[row["id"] for row in retained]).get()
        assert (sent.status, sent.error, sent.attempts, sent.recipient_id) == ("sent", "", 1, document.payment.member_id)
        assert sent.source_kind == ("notification.direct" if entry == "direct" else "notification.envelope")
        assert mailoutbox[0].to == [document.payment.member.email]
        assert mailoutbox[0].attachments == [
            (f"{document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-1", "application/pdf")]
    assert business_snapshot(lane.space) == original


@pytest.mark.parametrize("switch", ["email", "billing.documents"])
def test_delayed_initial_direct_callback_cannot_recover_a_later_disabled_outcome(
        document, document_mail, lane, settings, monkeypatch, switch, django_capture_on_commit_callbacks, mailoutbox):
    from apps.integrations.notification_tasks import deliver_envelope
    from tests.billing_docs.test_email_recovery import set_switch

    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    smtp = Mock(wraps=smtp_send)
    monkeypatch.setattr("apps.integrations.mail_providers.delivery.send", smtp)
    envelope = document_mail.route("direct")
    NotificationPreference.objects.filter(makerspace=lane.space, user=document.payment.member,
        category="payments").update(channels=["email"], email_fallback=False)
    # Register while there is NO email history, then delay the compatibility callback.
    document.makerspace.refresh_from_db()
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        notify_document(document)
    assert len(callbacks) == 1
    assert EmailLog.objects.filter(source_id=envelope.pk, event=envelope.event).count() == 0
    original = business_snapshot(lane.space)
    set_switch(lane.space, switch, False)
    deliver_envelope(envelope.pk)
    envelope.refresh_from_db()
    reason = DISABLED if switch == "email" else "notification_source_disabled"
    intent = DocumentEmailIntent.objects.get(document=document)
    baseline = intent.generation
    assert (intent.state, intent.reason) == ("skipped_disabled", reason)
    set_switch(lane.space, switch, True)
    saved_envelope = type(envelope).objects.values().get(pk=envelope.pk)
    queued = list(lane.enqueued)
    callbacks[0]()
    smtp.assert_not_called()
    assert type(envelope).objects.values().get(pk=envelope.pk) == saved_envelope
    assert lane.enqueued == queued
    assert mailoutbox == [] and document_mail.rendered == []
    assert envelope.deliveries.count() == 0
    assert EmailLog.objects.filter(source_id=envelope.pk, event=envelope.event).count() == 0
    assert business_snapshot(lane.space) == original
    # A subsequent explicit producer call owns a new generation and may recover.
    document.makerspace.refresh_from_db()
    with django_capture_on_commit_callbacks(execute=True):
        notify_document(document)
    envelope.refresh_from_db()
    intent.refresh_from_db()
    assert (intent.state, intent.generation) == ("sent", baseline + 1)
    log = EmailLog.objects.get(source_id=envelope.pk, event=envelope.event)
    assert (log.status, log.error, log.attempts, log.source_kind) == ("sent", "", 1, "notification.direct")
    assert log.source_metadata["document_generation"] == baseline + 1
    assert log.recipient_id == document.payment.member_id
    assert envelope.deliveries.count() == 0
    assert smtp.call_count == 1 and len(mailoutbox) == 1 and document_mail.rendered == [document.pk]
    assert mailoutbox[0].to == [document.payment.member.email]
    assert mailoutbox[0].attachments == [
        (f"{document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-1", "application/pdf")]
    saved = EmailLog.objects.values().get(pk=log.pk)
    for _ in range(2):
        callbacks[0]()
        with django_capture_on_commit_callbacks(execute=True):
            notify_document(document)
        deliver_envelope(envelope.pk)
    assert smtp.call_count == 1 and len(mailoutbox) == 1 and document_mail.rendered == [document.pk]
    assert EmailLog.objects.values().get(pk=log.pk) == saved
    assert EmailLog.objects.filter(source_id=envelope.pk, event=envelope.event).count() == 1
    assert lane.enqueued == queued
    assert business_snapshot(lane.space) == original


@pytest.mark.parametrize("processed,approved,epoch", list(product([False, True], [False, True], [0, 1])))
def test_legacy_metadata_cannot_authorize_automatic_disabled_recovery(
        document, document_mail, lane, processed, approved, epoch, mailoutbox):
    envelope = document_mail.route("envelope")
    envelope.processed_at = timezone.now() if processed else None
    envelope.routing_snapshot = {**envelope.routing_snapshot,
        "_disabled_dispatch_reemitted": approved, "_disabled_dispatch_epoch": epoch}
    envelope.save(update_fields=["processed_at", "routing_snapshot"])
    retained = record_history(envelope, HISTORIES["disabled"])
    original = business_snapshot(lane.space)
    ensure_deliveries(envelope)
    allowed = False  # Legacy metadata never substitutes for persisted approval (530).
    assert envelope.deliveries.filter(channel="email").count() == int(allowed)
    assert list(EmailLog.objects.filter(source_id=envelope.pk, event=envelope.event).order_by("pk").values()) == retained
    assert mailoutbox == [] and document_mail.rendered == []
    assert business_snapshot(lane.space) == original
