"""Document reservation deduplication precedes the finite daily quota charge."""
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.hardware_requests.models import HardwareRequest
from apps.integrations.dispatch import dispatch_email
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.models import DailyEmailCounter, EmailLog
from apps.payments.models import Payment, PaymentDocument
from tests.billing_docs.test_email_recovery import set_switch
from tests.billing_docs.test_email_recovery_concurrency import contend_at_envelope_lock
from tests.billing_docs.test_r2_email import assert_mail_owner, document_ledger_snapshot, issue_mail

pytestmark = pytest.mark.django_db(transaction=True)


def prepare_recovery(document, document_mail, lane, settings, callbacks):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    lane.space.email_provider = "resend"
    lane.space.resource_limit_overrides = {**lane.space.resource_limit_overrides, "email": 1}
    lane.space.save(update_fields=["email_provider", "resource_limit_overrides"])
    set_switch(lane.space, "email", False)
    envelope = issue_mail(document, "direct", callbacks, document_mail)
    history = EmailLog.objects.values().get(event="document_issued")
    assert (history["status"], history["error"]) == ("skipped", "Email is disabled for this makerspace.")
    assert DailyEmailCounter.objects.filter(makerspace=lane.space).count() == 0
    set_switch(lane.space, "email", True)
    return envelope, history, document_ledger_snapshot(document)


def reserve(document_id, envelope):
    current = PaymentDocument.objects.select_related("makerspace", "payment__member").get(pk=document_id)
    return dispatch_email(makerspace=current.makerspace, to_email=current.payment.member.email,
        subject="Document", text_body="Document issued", stream="payments", event="document_issued",
        audience="requester", recipient_id=current.payment.member_id, source_kind="notification.direct",
        source_id=envelope.pk, source_metadata={"p2_direct": envelope.dedup_key, "address_owner": True,
            "document": {"document_id": current.pk, "kind": current.kind}}, sync=False)


@pytest.mark.parametrize("overlap", [False, True])
def test_one_unit_quota_duplicate_document_reservations_share_attempt_and_enqueue(
        document, document_mail, lane, settings, overlap, django_capture_on_commit_callbacks, mailoutbox):
    envelope, history, original = prepare_recovery(
        document, document_mail, lane, settings, django_capture_on_commit_callbacks)
    attempts = []

    def produce():
        attempts.append(reserve(document.pk, envelope).pk)

    with patch("apps.integrations.dispatch_outbox._enqueue") as enqueue:
        if overlap:
            contend_at_envelope_lock(produce)
        else:
            with django_capture_on_commit_callbacks(execute=True):
                produce()
                produce()
    pending = EmailLog.objects.get(event="document_issued", status="pending")
    assert attempts == [pending.pk, pending.pk]
    enqueue.assert_called_once_with(pending.pk)
    assert (pending.error, pending.attempts) == ("", 0)
    counter = DailyEmailCounter.objects.get(makerspace=lane.space, day=timezone.now().date())
    assert counter.count == 1
    assert DailyEmailCounter.objects.filter(makerspace=lane.space).count() == 1
    assert EmailLog.objects.filter(event="document_issued").count() == 2
    assert EmailLog.objects.filter(event="document_issued", status="failed").count() == 0
    assert mailoutbox == [] and document_mail.rendered == []
    _deliver(pending)
    _deliver(EmailLog.objects.get(pk=pending.pk))
    assert len(mailoutbox) == 1 and mailoutbox[0].to == [document.payment.member.email]
    assert mailoutbox[0].attachments == [
        (f"{document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-1", "application/pdf")]
    assert document_mail.rendered == [document.pk]
    assert assert_mail_owner(document, "direct", envelope, skipped_direct=1).pk == pending.pk
    counter.refresh_from_db()
    assert counter.count == 1
    assert EmailLog.objects.values().get(pk=history["id"]) == history
    assert document_ledger_snapshot(document) == original


def test_one_unit_quota_refuses_a_genuinely_new_document_intent(
        document, document_mail, lane, settings, django_capture_on_commit_callbacks, mailoutbox):
    from apps.payments.documents import issue_bill
    from apps.payments.notifications_p2 import notify_document
    envelope, history, _ = prepare_recovery(
        document, document_mail, lane, settings, django_capture_on_commit_callbacks)
    with patch("apps.integrations.dispatch_outbox._enqueue") as enqueue:
        with django_capture_on_commit_callbacks(execute=True):
            first = reserve(document.pk, envelope)
    enqueue.assert_called_once_with(first.pk)
    _deliver(first)
    assert len(mailoutbox) == 1
    assert assert_mail_owner(document, "direct", envelope, skipped_direct=1).pk == first.pk
    first_history = EmailLog.objects.values().get(pk=first.pk)
    loan = HardwareRequest.objects.create(makerspace=lane.space, requester=document.payment.member,
        requester_username=document.payment.member.username, status="accepted")
    payment = Payment.objects.create(makerspace=lane.space, member=document.payment.member,
        subject_type="loan_deposit", subject_id=loan.pk,
        amount="7.00", currency="usd", provider="unclaimed", created_by=lane.manager)
    with patch("apps.integrations.dispatch._deliver") as transport, \
            patch("apps.integrations.dispatch_outbox._enqueue") as refused_enqueue:
        with django_capture_on_commit_callbacks(execute=True):
            second_document = issue_bill(payment, actor=lane.manager)
    transport.assert_not_called()
    refused_enqueue.assert_not_called()
    logs = EmailLog.objects.filter(event="document_issued", source_metadata__document__document_id=second_document.pk)
    assert logs.count() == 1
    refused = logs.get()
    assert (refused.status, refused.error, refused.attempts) == (
        "failed", "Daily email limit reached for this space.", 0)
    assert (refused.source_kind, refused.recipient_id) == ("notification.direct", payment.member_id)
    assert refused.source_id != envelope.pk
    assert refused.source_metadata["p2_direct"] != envelope.dedup_key
    assert refused.source_metadata["document"] == {"document_id": second_document.pk, "kind": "bill"}
    refused_history = logs.values().get()
    original = document_ledger_snapshot(second_document)
    with django_capture_on_commit_callbacks(execute=True):
        notify_document(second_document)
    assert logs.count() == 1 and logs.values().get() == refused_history
    assert EmailLog.objects.filter(event="document_issued").count() == 3
    assert DailyEmailCounter.objects.get(makerspace=lane.space, day=timezone.now().date()).count == 1
    assert len(mailoutbox) == 1 and document_mail.rendered == [document.pk]
    assert EmailLog.objects.values().get(pk=first.pk) == first_history
    assert EmailLog.objects.values().get(pk=history["id"]) == history
    assert document_ledger_snapshot(second_document) == original
