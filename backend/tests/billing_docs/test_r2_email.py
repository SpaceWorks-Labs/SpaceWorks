"""Exercise both document email owners through the real SMTP assembly boundary."""
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.models import EmailLog
from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.notification_delivery import send
from apps.integrations.notification_tasks import deliver_envelope
from apps.notifications.models import MemberNotificationPreference
from apps.payments.notifications_p2 import notify_document

pytestmark = pytest.mark.django_db


def issue_mail(document, path, callbacks, mail_fixture):
    envelope = mail_fixture.route(path)
    with callbacks(execute=True):
        notify_document(document)
    if path == "envelope":
        deliver_envelope(envelope.pk)
    return envelope


def retry_mail(path, envelope):
    if path == "direct":
        return _deliver(EmailLog.objects.filter(event="document_issued").latest("pk"))
    delivery = envelope.deliveries.get(channel="email")
    NotificationDelivery.objects.filter(pk=delivery.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
    send(delivery.pk)
    return EmailLog.objects.filter(event="document_issued").latest("pk")


@pytest.mark.parametrize("document", ["receipt", "credit_note", "bill"], indirect=True)
@pytest.mark.parametrize("path", ["direct", "envelope"])
def test_each_document_kind_is_attached_once_to_payer_mail(document, document_mail, path,
        django_capture_on_commit_callbacks, mailoutbox):
    envelope = issue_mail(document, path, django_capture_on_commit_callbacks, document_mail)
    assert len(mailoutbox) == 1
    message = mailoutbox[0]
    assert message.to == [document.payment.member.email]
    assert message.attachments == [(f"{document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-1", "application/pdf")]
    log = EmailLog.objects.get(event="document_issued")
    assert log.status == "sent" and log.recipient_id == document.payment.member_id
    # Re-emission and an outbox sweep cannot duplicate the compatibility mail.
    with django_capture_on_commit_callbacks(execute=True):
        notify_document(document)
    deliver_envelope(envelope.pk)
    assert len(mailoutbox) == 1
    persisted = json.dumps(list(NotificationEnvelope.objects.values("context", "message_body", "routing_snapshot")))
    persisted += json.dumps(list(EmailLog.objects.values("source_metadata")))
    persisted += json.dumps(list(AuditLog.objects.values("meta")), default=str)
    assert "private-payer-document" not in persisted and "%PDF" not in persisted


@pytest.mark.parametrize("path", ["direct", "envelope"])
def test_payer_optout_blocks_initial_document_mail(document, document_mail, path, lane,
        django_capture_on_commit_callbacks, mailoutbox):
    MemberNotificationPreference.objects.create(makerspace=lane.space, user=document.payment.member,
                                                feature="payments", channel="email", enabled=False)
    issue_mail(document, path, django_capture_on_commit_callbacks, document_mail)
    assert mailoutbox == [] and document_mail.rendered == []
    assert not EmailLog.objects.filter(event="document_issued", status="sent").exists()


@pytest.mark.parametrize("path", ["direct", "envelope"])
def test_payer_optout_blocks_document_retry(document, document_mail, path, lane,
        django_capture_on_commit_callbacks, mailoutbox):
    with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("SMTP unavailable")):
        envelope = issue_mail(document, path, django_capture_on_commit_callbacks, document_mail)
    assert len(document_mail.rendered) == 1
    MemberNotificationPreference.objects.create(makerspace=lane.space, user=document.payment.member,
                                                feature="payments", channel="email", enabled=False)
    retry_mail(path, envelope)
    assert mailoutbox == [] and len(document_mail.rendered) == 1


@pytest.mark.parametrize("path", ["direct", "envelope"])
def test_retry_rerenders_and_uses_current_payer_mailbox(document, document_mail, path,
        django_capture_on_commit_callbacks, mailoutbox):
    with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("SMTP unavailable")):
        envelope = issue_mail(document, path, django_capture_on_commit_callbacks, document_mail)
    owner = document.payment.member
    owner.email = "current-payer@example.test"
    owner.save(update_fields=["email"])
    owner.email_verified_at = timezone.now()
    owner.save(update_fields=["email_verified_at"])
    retry_mail(path, envelope)
    assert document_mail.rendered == [document.pk, document.pk]
    assert len(mailoutbox) == 1 and mailoutbox[0].to == [owner.email]
    assert mailoutbox[0].attachments[0].content.endswith(b"-2")


def test_changed_unverified_mailbox_blocks_envelope_retry(document, document_mail,
        django_capture_on_commit_callbacks, mailoutbox):
    with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("SMTP unavailable")):
        envelope = issue_mail(document, "envelope", django_capture_on_commit_callbacks, document_mail)
    owner = document.payment.member
    owner.email = "unproven-payer@example.test"
    owner.save(update_fields=["email"])
    assert owner.email_verified_at is None
    retry_mail("envelope", envelope)
    assert mailoutbox == [] and document_mail.rendered == [document.pk]
    assert envelope.deliveries.get(channel="email").state == "skipped"


@pytest.mark.parametrize("path", ["direct", "envelope"])
def test_oversize_document_fails_delivery_instead_of_sending_link_only(document, document_mail, path, monkeypatch,
        django_capture_on_commit_callbacks, mailoutbox):
    monkeypatch.setattr("apps.payments.document_pdf.render_document_pdf", lambda row: b"x" * (5 * 1024 * 1024 + 1))
    issue_mail(document, path, django_capture_on_commit_callbacks, document_mail)
    assert mailoutbox == []
    assert EmailLog.objects.filter(event="document_issued", status="failed").exists()


def test_attachment_reference_rejects_foreign_tenant_and_wrong_payer(document, lane):
    from apps.payments.document_delivery import DocumentDeliveryError, render_attachment
    from tests.return_helpers import make_space
    reference = {"document_id": document.pk, "kind": document.kind}
    with pytest.raises(DocumentDeliveryError, match="document_not_authorized"):
        render_attachment(reference, makerspace_id=make_space("r2-foreign-doc").pk,
                          recipient_id=document.payment.member_id)
    with pytest.raises(DocumentDeliveryError, match="document_not_authorized"):
        render_attachment(reference, makerspace_id=lane.space.pk, recipient_id=lane.manager.pk)


def test_account_less_payment_never_generates_document_mail(lane,
        django_capture_on_commit_callbacks, mailoutbox):
    from apps.hardware_requests.models import HardwareRequest
    from apps.payments.models import Payment, PaymentDocument
    from apps.payments.reconciliation import mark_offline
    from tests.return_helpers import settlement_details
    request = HardwareRequest.objects.create(makerspace=lane.space, requester=lane.owner,
        requester_username=lane.owner.username, status="accepted")
    payment = Payment.objects.create(makerspace=lane.space, member=None, subject_type="loan_deposit",
        subject_id=request.pk, amount="25.00", currency="usd", provider="unclaimed", created_by=lane.manager)
    with django_capture_on_commit_callbacks(execute=True):
        mark_offline(payment, lane.manager, settlement=settlement_details())
        document = PaymentDocument.objects.get(payment=payment, kind="receipt", reverses__isnull=True)
        notify_document(document)
    assert mailoutbox == [] and not EmailLog.objects.filter(event="document_issued").exists()
