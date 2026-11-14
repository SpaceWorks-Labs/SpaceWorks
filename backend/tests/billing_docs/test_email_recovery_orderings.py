"""Bounded producer schedules; test_document_email_state proves the state x event table."""
from datetime import timedelta
from itertools import product
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.integrations.mail_providers.delivery import send as smtp_send
from apps.integrations.models import EmailLog, NotificationPreference as Matrix
from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.notification_delivery import fallback_if_exhausted
from apps.integrations.notification_providers import ProviderResult
from apps.integrations.notification_tasks import deliver_envelope, sweep_notification_outbox
from apps.notifications.models import MemberNotificationPreference
from apps.notifications.models_preferences import NotificationPreference
from apps.payments.documents import issue_bill
from apps.payments.models import Payment, PaymentDocument
from apps.payments.notifications_p2 import notify_document
from tests.billing_docs.test_email_recovery import set_switch
from tests.billing_docs.test_r2_delivery import provider

from tests.billing_docs.email_recovery_helpers import intent_state

pytestmark = pytest.mark.django_db
DISABLED = "Email is disabled for this makerspace."
PDF = b"%PDF-1.7\nordering-table-private-payer-document"

# 2 * 3 * 3 * 2 * 2 * 4 * 2 = 576 schedules, each with at most four chat attempts.
ORDERINGS = list(product(
    [False, True], ["none", "flip", "roundtrip"], ["before", "after", "delayed"],
    [False, True], [False, True], ["none", "before", "after", "twice"], [False, True],
))


def business_snapshot(space):
    """Every ledger/document column and every non-transport tenant audit row."""
    return (
        list(Payment.objects.filter(makerspace=space).order_by("pk").values()),
        list(PaymentDocument.objects.filter(makerspace=space).order_by("pk").values()),
        list(AuditLog.objects.filter(makerspace=space).exclude(
            action__startswith="notification.").order_by("pk").values()),
    )


@pytest.mark.parametrize("email_on,toggles,worker,sweep,retry,reemit,optout", ORDERINGS,
    ids=["-".join(map(str, row)) for row in ORDERINGS])
def test_document_email_history_ordering_table(
        lane, payment, settings, monkeypatch, django_capture_on_commit_callbacks, mailoutbox,
        email_on, toggles, worker, sweep, retry, reemit, optout):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    monkeypatch.setattr("apps.integrations.email.makerspace_mail_connection", lambda space: (None, "billing@example.test"))
    monkeypatch.setattr("apps.integrations.timing_dispatch.defer_log", lambda *args, **kwargs: False)
    smtp = Mock(wraps=smtp_send)
    monkeypatch.setattr("apps.integrations.mail_providers.delivery.send", smtp)
    rendered = []

    def pdf(row):
        rendered.append(row.pk)
        return PDF

    monkeypatch.setattr("apps.payments.document_pdf.render_document_pdf", pdf)
    fake = provider(monkeypatch, [ProviderResult(False, retryable=True, error_code="unavailable")] * 4)
    Matrix.objects.update_or_create(makerspace=lane.space, feature="payments", channel="email",
                                    defaults={"enabled": True})
    NotificationPreference.objects.filter(makerspace=lane.space, user=payment.member, category="payments").update(
        channels=["email", "telegram"] if retry else ["email"], email_fallback=True)
    if optout:
        consent = MemberNotificationPreference.objects.create(makerspace=lane.space, user=payment.member,
            feature="payments", channel="email", enabled=False)
    set_switch(lane.space, "email", email_on)
    # Unlike a pre-existing fixture intent, this is its very first producer emit.
    with django_capture_on_commit_callbacks(execute=True):
        document = issue_bill(payment, actor=lane.manager)
    envelope = NotificationEnvelope.objects.get(source_kind="payments.document", source_id=str(document.pk))
    assert lane.enqueued.count(envelope.pk) == 1
    assert envelope.processed_at is None and envelope.deliveries.count() == 0
    assert intent_state(envelope).state != "recovery_approved"
    history = list(EmailLog.objects.filter(source_id=envelope.pk, event=envelope.event).order_by("pk").values())
    skip_count = int(optout or not email_on)
    assert len(history) == skip_count
    if skip_count:
        row = history[0]
        assert (row["status"], row["error"], row["attempts"]) == (
            "skipped", "email_member_opted_out" if optout else DISABLED, 0)
        assert (row["source_kind"], row["source_id"], row["recipient_id"]) == (
            "notification.direct", envelope.pk, payment.member_id)
        assert row["source_metadata"]["p2_direct"] == envelope.dedup_key
    assert smtp.call_count == 0 and mailoutbox == [] and rendered == []
    original = business_snapshot(lane.space)
    if optout:
        # The historical refusal must still win when current consent now allows mail.
        consent.enabled = True
        consent.save(update_fields=["enabled"])

    def unchanged():
        assert list(EmailLog.objects.filter(pk__in=[row["id"] for row in history]).order_by("pk").values()) == history
        assert business_snapshot(lane.space) == original

    def emit():
        document.makerspace.refresh_from_db()
        with django_capture_on_commit_callbacks(execute=True):
            notify_document(document)
        unchanged()

    def work():
        deliver_envelope(envelope.pk)
        unchanged()

    def sweep_work(expected):
        # Exercise actual sweep selection, then synchronously execute only this intent.
        with patch("apps.integrations.notification_tasks.deliver_envelope.delay") as enqueue:
            sweep_notification_outbox()
        selected = [call.args[0] for call in enqueue.call_args_list].count(envelope.pk)
        assert selected == expected
        if selected:
            work()

    if worker == "before":
        if reemit in {"before", "twice"}:
            emit()
        work()
    for enabled in {"none": [], "flip": [not email_on], "roundtrip": [not email_on, email_on]}[toggles]:
        set_switch(lane.space, "email", enabled)
        unchanged()
    final_on = not email_on if toggles == "flip" else email_on
    if worker != "before":
        if reemit in {"before", "twice"}:
            emit()
        if worker == "delayed" and sweep:
            sweep_work(1)
        work()  # The originally queued task may now be stale.
    if sweep and worker != "delayed":
        sweep_work(0)  # Finished/no runnable leg, or Telegram's retry is still in the future.
    if retry:
        telegram = envelope.deliveries.get(channel="telegram")
        assert (telegram.state, telegram.last_error, telegram.attempt_count, telegram.retryable) == (
            "retrying", "unavailable", 1, True)
        for attempt in range(2, 5):
            NotificationDelivery.objects.filter(pk=telegram.pk).update(
                next_attempt_at=timezone.now() - timedelta(seconds=1))
            if sweep:
                sweep_work(1)
            else:
                work()
            telegram.refresh_from_db()
            assert (telegram.state, telegram.last_error, telegram.attempt_count, telegram.retryable) == (
                "failed" if attempt == 4 else "retrying", "unavailable", attempt, attempt < 4)
            assert telegram.claim_until is None
            assert (telegram.next_attempt_at is not None) is (attempt < 4)
        assert len(fake.documents) == 4 and fake.texts == []
    else:
        assert envelope.deliveries.exclude(channel="email").count() == 0
        assert fake.documents == [] and fake.texts == []

    # R6: absent successful early explicit recovery, all automatic entries stay inert.
    early_recovery = not optout and not email_on and final_on and worker != "before" and reemit in {"before", "twice"}
    initial_send = not optout and email_on and (worker == "before" or final_on)
    assert smtp.call_count == int(initial_send or early_recovery)
    assert envelope.deliveries.filter(channel="email").count() == int(initial_send or early_recovery)
    if reemit in {"after", "twice"}:
        emit()
    # Drain both original and recovery queue entries, including duplicate old tasks.
    for pk in [pk for pk in lane.enqueued if pk == envelope.pk]:
        deliver_envelope(pk)
    recovery = not optout and not email_on and final_on and (
        reemit in {"after", "twice"} or reemit == "before" and worker != "before")
    expected = int(initial_send or recovery)
    assert smtp.call_count == expected and len(mailoutbox) == expected
    assert envelope.deliveries.filter(channel="email").count() == expected
    assert lane.enqueued.count(envelope.pk) == 1 + int(recovery)
    envelope.refresh_from_db()
    assert intent_state(envelope).generation == int(recovery)
    assert intent_state(envelope).state == ("sent" if expected else "skipped_permanent" if optout else "skipped_disabled")
    logs = EmailLog.objects.filter(makerspace=lane.space, source_id=envelope.pk, event=envelope.event)
    # An explicit emit after disabling observes and records the refusal even if
    # initial fan-out was enabled. A worker alone reserves no compatibility log.
    late_skip = int(not optout and email_on and not final_on and worker != "before" and reemit != "none")
    assert logs.count() == skip_count + late_skip + expected
    assert logs.filter(status="skipped").count() == skip_count + late_skip
    if late_skip:
        skipped = logs.get(status="skipped")
        assert (skipped.error, skipped.attempts, skipped.source_kind, skipped.recipient_id) == (
            DISABLED, 0, "notification.direct", payment.member_id)
        assert skipped.source_metadata["p2_direct"] == envelope.dedup_key
    assert logs.filter(status="sent").count() == expected
    if expected:
        log = logs.get(status="sent")
        leg = envelope.deliveries.get(channel="email")
        assert (leg.state, leg.last_error, leg.attempt_count, leg.retryable) == ("sent", "", 1, False)
        assert (log.status, log.error, log.attempts) == ("sent", "", 1)
        assert (log.source_kind, log.recipient_id, log.source_metadata["delivery_id"]) == (
            "notification.envelope", payment.member_id, leg.pk)
        assert mailoutbox[0].to == [payment.member.email]
        assert mailoutbox[0].attachments == [(f"{document.number}.pdf", PDF, "application/pdf")]
    assert rendered == [document.pk] * (expected + (4 if retry else 0))
    unchanged()
    saved_legs = list(envelope.deliveries.order_by("pk").values())
    saved_logs = list(logs.order_by("pk").values())
    fallback_if_exhausted(envelope)
    work()
    if sweep:
        sweep_work(0)
    assert list(envelope.deliveries.order_by("pk").values()) == saved_legs
    assert list(logs.order_by("pk").values()) == saved_logs
    assert smtp.call_count == expected and len(mailoutbox) == expected
    assert rendered == [document.pk] * (expected + (4 if retry else 0))
    unchanged()
