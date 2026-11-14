"""R7 real producers: no-envelope owner changes and reasonless completed history."""
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.hardware_requests.models import HardwareRequest
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.mail_providers.delivery import send as smtp_send
from apps.integrations.models import DailyEmailCounter, EmailLog, NotificationRecipient
from apps.integrations.models_contract import NotificationEnvelope, NotificationDelivery
from apps.integrations.models_document_email import DocumentEmailIntent
from apps.integrations.notification_delivery import ensure_deliveries, fallback_if_exhausted
from apps.integrations.notification_tasks import deliver_envelope, sweep_notification_outbox
from apps.notifications.models import MemberNotificationPreference
from apps.notifications.models_preferences import NotificationPreference
from apps.payments.documents import issue_bill
from apps.payments.models import Payment, PaymentDocument
from apps.payments.notifications_p2 import notify_document
from tests.billing_docs.test_email_recovery import set_switch
from tests.billing_docs.test_email_recovery_concurrency import contend_at_envelope_lock
from tests.billing_docs.test_email_recovery_orderings import DISABLED, business_snapshot

pytestmark = pytest.mark.django_db(transaction=True)


def no_envelope_bill(lane, document, callbacks):
    NotificationRecipient.objects.create(makerspace=lane.space, feature="payments", event="document_issued",
                                          kind="user", user=lane.manager)
    NotificationPreference.objects.filter(makerspace=lane.space, user=document.payment.member,
                                          category="payments").update(channels=["email"])
    loan = HardwareRequest.objects.create(makerspace=lane.space, requester=document.payment.member,
        requester_username=document.payment.member.username, status="accepted")
    debt = Payment.objects.create(makerspace=lane.space, member=document.payment.member,
        subject_type="loan_deposit", subject_id=loan.pk, amount="25.00", currency="usd",
        provider="unclaimed", created_by=lane.manager)
    with callbacks(execute=True):
        bill = issue_bill(debt, actor=lane.manager)
    assert NotificationEnvelope.objects.filter(source_kind="payments.document", source_id=str(bill.pk)).count() == 0
    return bill


def emit(document, callbacks):
    document.makerspace.refresh_from_db()
    with callbacks(execute=True):
        notify_document(document)


def assert_one_payer_pdf(document, mail, outbox):
    assert len(outbox) == 1 and outbox[0].to == [document.payment.member.email]
    assert outbox[0].attachments == [(f"{document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-1", "application/pdf")]
    assert mail.rendered == [document.pk]


@pytest.mark.parametrize("owner", ["direct", "envelope"])
def test_proven_initial_fanout_can_be_delayed_and_sent_exactly_once(
        document, document_mail, lane, owner, settings, django_capture_on_commit_callbacks, mailoutbox):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    document_mail.route(owner)
    NotificationPreference.objects.filter(makerspace=lane.space, user=document.payment.member,
                                          category="payments").update(channels=["email"])
    loan = HardwareRequest.objects.create(makerspace=lane.space, requester=document.payment.member,
        requester_username=document.payment.member.username, status="accepted")
    debt = Payment.objects.create(makerspace=lane.space, member=document.payment.member,
        subject_type="loan_deposit", subject_id=loan.pk, amount="25.00", currency="usd",
        provider="unclaimed", created_by=lane.manager)
    with patch("apps.integrations.transient_mail.queue_email", return_value=True) as queued_mail:
        with django_capture_on_commit_callbacks(execute=True):
            bill = issue_bill(debt, actor=lane.manager)
    intent = DocumentEmailIntent.objects.get(document=bill)
    envelope = NotificationEnvelope.objects.get(source_kind="payments.document", source_id=str(bill.pk))
    assert intent.generation == 0
    assert mailoutbox == [] and document_mail.rendered == []
    original = business_snapshot(lane.space)
    if owner == "direct":
        assert queued_mail.call_count == 1
        pending = EmailLog.objects.get(source_kind="notification.direct", source_id=envelope.pk)
        assert (intent.state, intent.owner_kind, intent.owner_id) == ("sent", "direct", pending.pk)
        assert (pending.status, pending.error, pending.attempts) == ("pending", "", 0)
        _deliver(pending)
    else:
        queued_mail.assert_not_called()
        assert (intent.state, intent.owner_kind, intent.owner_id) == ("initial_pending", "", None)
        assert EmailLog.objects.filter(source_id=envelope.pk, event="document_issued").count() == 0
        deliver_envelope(envelope.pk)
    intent.refresh_from_db()
    assert (intent.state, intent.generation, intent.owner_kind) == ("sent", 0, owner)
    for _ in range(2):
        emit(bill, django_capture_on_commit_callbacks)
        deliver_envelope(envelope.pk)
    assert_one_payer_pdf(bill, document_mail, mailoutbox)
    sent = EmailLog.objects.get(event="document_issued", source_id=envelope.pk)
    assert (sent.status, sent.error, sent.attempts, sent.recipient_id) == ("sent", "", 1, bill.payment.member_id)
    assert business_snapshot(lane.space) == original


def test_no_envelope_two_connection_recovery_has_one_quota_attempt_enqueue_and_pdf(
        document, document_mail, lane, settings, monkeypatch, django_capture_on_commit_callbacks, mailoutbox):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    lane.space.email_provider = "resend"
    lane.space.resource_limit_overrides = {**lane.space.resource_limit_overrides, "email": 1}
    lane.space.save(update_fields=["email_provider", "resource_limit_overrides"])
    set_switch(lane.space, "email", False)
    bill = no_envelope_bill(lane, document, django_capture_on_commit_callbacks)
    intent = DocumentEmailIntent.objects.get(document=bill)
    skipped = EmailLog.objects.values().get(source_kind="payments.document", source_id=bill.pk)
    assert (skipped["status"], skipped["error"], skipped["attempts"]) == ("skipped", DISABLED, 0)
    assert (skipped["recipient_id"], skipped["source_metadata"]["p2_direct"]) == (bill.payment.member_id, intent.intent_key)
    assert skipped["source_metadata"]["document"] == {"document_id": bill.pk, "kind": "bill"}
    assert DailyEmailCounter.objects.filter(makerspace=lane.space).count() == 0
    original, queued = business_snapshot(lane.space), list(lane.enqueued)
    set_switch(lane.space, "email", True)
    smtp = Mock(wraps=smtp_send)
    monkeypatch.setattr("apps.integrations.mail_providers.delivery.send", smtp)

    def produce():
        current = PaymentDocument.objects.select_related("makerspace", "payment__member").get(pk=bill.pk)
        notify_document(current)

    # Keep the real producer and queue seam; count its one send enqueue after reservation.
    with patch("apps.integrations.transient_mail.queue_email", return_value=True) as enqueue:
        contend_at_envelope_lock(produce)
    pending = EmailLog.objects.get(source_kind="payments.document", source_id=bill.pk, status="pending")
    assert enqueue.call_count == 1
    assert enqueue.call_args.args[0].pk == pending.pk
    assert (pending.error, pending.attempts, pending.recipient_id) == ("", 0, bill.payment.member_id)
    assert pending.source_metadata["p2_direct"] == intent.intent_key
    assert pending.source_metadata["document"] == {"document_id": bill.pk, "kind": "bill"}
    intent.refresh_from_db()
    assert (intent.state, intent.generation, intent.owner_kind, intent.owner_id) == ("sent", 1, "direct", pending.pk)
    assert DailyEmailCounter.objects.get(makerspace=lane.space).count == 1
    assert lane.enqueued == queued
    assert mailoutbox == [] and document_mail.rendered == [] and smtp.call_count == 0
    _deliver(pending)
    saved = EmailLog.objects.values().get(pk=pending.pk)
    assert (saved["status"], saved["error"], saved["attempts"]) == ("sent", "", 1)
    for _ in range(2):
        emit(bill, django_capture_on_commit_callbacks)
        _deliver(EmailLog.objects.get(pk=pending.pk))
    assert_one_payer_pdf(bill, document_mail, mailoutbox)
    assert smtp.call_count == 1 and DailyEmailCounter.objects.get(makerspace=lane.space).count == 1
    assert EmailLog.objects.filter(source_kind="payments.document", source_id=bill.pk).count() == 2
    assert EmailLog.objects.values().get(pk=pending.pk) == saved
    assert EmailLog.objects.values().get(pk=skipped["id"]) == skipped
    assert business_snapshot(lane.space) == original and lane.enqueued == queued


@pytest.mark.parametrize("legacy", [False, True])
def test_permanent_no_envelope_skip_blocks_new_envelope_owner(
        document, document_mail, lane, settings, monkeypatch, legacy, django_capture_on_commit_callbacks, mailoutbox):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    smtp = Mock(wraps=smtp_send)
    monkeypatch.setattr("apps.integrations.mail_providers.delivery.send", smtp)
    consent = MemberNotificationPreference.objects.create(makerspace=lane.space, user=document.payment.member,
        feature="payments", channel="email", enabled=False)
    bill = no_envelope_bill(lane, document, django_capture_on_commit_callbacks)
    intent = DocumentEmailIntent.objects.get(document=bill)
    key = intent.intent_key
    history = EmailLog.objects.values().get(source_kind="payments.document", source_id=bill.pk)
    assert (history["status"], history["error"], history["attempts"]) == ("skipped", "email_member_opted_out", 0)
    if legacy:
        intent.delete()
    consent.enabled = True
    consent.save(update_fields=["enabled"])
    NotificationRecipient.objects.create(makerspace=lane.space, feature="payments", event="document_issued", kind="requester")
    document_mail.route("envelope")
    original, queued = business_snapshot(lane.space), list(lane.enqueued)
    emit(bill, django_capture_on_commit_callbacks)
    envelope = NotificationEnvelope.objects.get(dedup_key=key)
    assert (envelope.recipient_id, envelope.source_id) == (bill.payment.member_id, str(bill.pk))
    assert lane.enqueued == queued + [envelope.pk]
    for _ in range(2):
        deliver_envelope(envelope.pk)
        ensure_deliveries(envelope)
        fallback_if_exhausted(envelope)
        emit(bill, django_capture_on_commit_callbacks)
    intent = DocumentEmailIntent.objects.get(document=bill)
    assert (intent.state, intent.generation, intent.reason) == ("skipped_permanent", 0, "email_member_opted_out")
    assert envelope.deliveries.filter(channel="email").count() == 0
    assert EmailLog.objects.filter(event="document_issued").count() == 1
    assert EmailLog.objects.values().get(pk=history["id"]) == history
    assert lane.enqueued == queued + [envelope.pk]
    assert mailoutbox == [] and document_mail.rendered == []
    assert smtp.call_count == 0
    assert business_snapshot(lane.space) == original


@pytest.mark.parametrize("other_channel", [False, True])
def test_reasonless_completed_legacy_is_inert_through_direct_worker_and_public_fallback(
        document, document_mail, lane, monkeypatch, other_channel, django_capture_on_commit_callbacks, mailoutbox):
    smtp = Mock(wraps=smtp_send)
    monkeypatch.setattr("apps.integrations.mail_providers.delivery.send", smtp)
    envelope = document_mail.route("direct")
    NotificationPreference.objects.filter(makerspace=lane.space, user=document.payment.member,
                                          category="payments").update(channels=["email"])
    envelope.processed_at = timezone.now()
    envelope.save(update_fields=["processed_at"])
    DocumentEmailIntent.objects.filter(document=document).delete()
    if other_channel:
        NotificationDelivery.objects.create(makerspace=lane.space, envelope=envelope, channel="telegram",
            target_key="legacy-channel", provider="telegram", state="retrying")
    before = NotificationEnvelope.objects.values().get(pk=envelope.pk)
    history = list(EmailLog.objects.filter(event="document_issued").values())
    original, queued = business_snapshot(lane.space), list(lane.enqueued)
    with patch("apps.integrations.notification_delivery.send") as send, patch(
            "apps.integrations.dispatch_outbox._enqueue") as enqueue, patch(
            "apps.integrations.notification_tasks.deliver_envelope.delay") as sweep:
        for _ in range(2):
            emit(document, django_capture_on_commit_callbacks)
            ensure_deliveries(envelope)
            fallback_if_exhausted(envelope)
            deliver_envelope(envelope.pk)
            sweep_notification_outbox()
        enqueue.assert_not_called()
        # Existing chat retries keep their sweep schedule; no email/recovery job is added.
        assert [call.args[0] for call in sweep.call_args_list].count(envelope.pk) == (2 if other_channel else 0)
        assert [call.args[0] for call in send.call_args_list] == (
            [envelope.deliveries.get(channel="telegram").pk] * 2 if other_channel else [])
    intent = DocumentEmailIntent.objects.get(document=document)
    assert (intent.state, intent.generation, intent.owner_kind, intent.owner_id) == ("unknown_legacy", 0, "", None)
    assert envelope.deliveries.filter(channel="email").count() == 0
    assert NotificationEnvelope.objects.values().get(pk=envelope.pk) == before
    assert list(EmailLog.objects.filter(event="document_issued").values()) == history == []
    assert lane.enqueued == queued and mailoutbox == [] and document_mail.rendered == []
    assert smtp.call_count == 0
    assert business_snapshot(lane.space) == original
