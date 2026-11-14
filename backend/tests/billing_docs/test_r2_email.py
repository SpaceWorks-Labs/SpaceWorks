"""Exercise both document email owners through the real SMTP assembly boundary."""
import json
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.integrations.models import EmailLog
from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.notification_tasks import deliver_envelope
from apps.notifications.models import MemberNotificationPreference
from apps.notifications.models_preferences import NotificationPreference
from apps.payments.notifications_p2 import notify_document
from tests.billing_docs.email_recovery_helpers import document_ledger_snapshot, retry_mail

pytestmark = pytest.mark.django_db


def issue_mail(document, path, callbacks, mail_fixture):
    envelope = mail_fixture.route(path)
    # The tenant email matrix selects the delivery owner. The payer must still
    # consent to email: route("direct") inherited a Telegram-only personal choice.
    NotificationPreference.objects.filter(makerspace=document.makerspace, user=document.payment.member,
                                          category="payments").update(channels=["email"])
    # document_mail configures a separate tenant instance after this FK was loaded.
    document.makerspace.refresh_from_db()
    with callbacks(execute=True):
        notify_document(document)
    if path == "envelope":
        deliver_envelope(envelope.pk)
    return envelope


def assert_mail_owner(document, path, envelope, *, skipped_direct=0):
    logs = EmailLog.objects.filter(makerspace=document.makerspace, event="document_issued")
    assert logs.count() == 1 + skipped_direct
    assert logs.filter(status="sent").count() == 1
    log = logs.get(status="sent")
    assert log.recipient_id == document.payment.member_id
    assert log.source_id == envelope.pk
    deliveries = NotificationDelivery.objects.filter(envelope=envelope, channel="email")
    direct = logs.filter(source_kind="notification.direct", source_id=envelope.pk)
    if path == "envelope":
        assert deliveries.count() == 1
        delivery = deliveries.get()
        assert delivery.state == "sent"
        assert log.source_kind == "notification.envelope"
        assert log.source_metadata["delivery_id"] == delivery.pk
        assert direct.count() == skipped_direct
        assert direct.filter(source_metadata__p2_direct=envelope.dedup_key).count() == skipped_direct
    else:
        assert deliveries.count() == 0
        assert direct.count() == 1 + skipped_direct
        assert log.source_kind == "notification.direct"
        assert log.source_metadata["p2_direct"] == envelope.dedup_key
    assert direct.filter(status="skipped", error="Email is disabled for this makerspace.").count() == skipped_direct
    return log


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
    assert assert_mail_owner(document, path, envelope).pk == log.pk
    # Re-emission and an outbox sweep cannot duplicate the compatibility mail.
    with django_capture_on_commit_callbacks(execute=True):
        notify_document(document)
    deliver_envelope(envelope.pk)
    assert len(mailoutbox) == 1
    assert assert_mail_owner(document, path, envelope).pk == log.pk
    assert document_mail.rendered == [document.pk]
    persisted = json.dumps(list(NotificationEnvelope.objects.values("context", "message_body", "routing_snapshot")))
    persisted += json.dumps(list(EmailLog.objects.values("source_metadata")))
    persisted += json.dumps(list(AuditLog.objects.values("meta")), default=str)
    assert "private-payer-document" not in persisted and "%PDF" not in persisted


@pytest.mark.parametrize("path", ["direct", "envelope"])
def test_payer_optout_blocks_initial_document_mail(document, document_mail, path, lane,
        django_capture_on_commit_callbacks, mailoutbox):
    MemberNotificationPreference.objects.create(makerspace=lane.space, user=document.payment.member,
                                                feature="payments", channel="email", enabled=False)
    envelope = issue_mail(document, path, django_capture_on_commit_callbacks, document_mail)
    assert mailoutbox == [] and document_mail.rendered == []
    logs = EmailLog.objects.filter(event="document_issued")
    assert logs.count() == 1
    log = logs.get()
    assert (log.status, log.error) == ("skipped", "email_member_opted_out")
    assert (log.source_kind, log.source_id, log.recipient_id) == (
        "notification.direct", envelope.pk, document.payment.member_id)
    assert log.source_metadata["p2_direct"] == envelope.dedup_key
    assert envelope.deliveries.filter(channel="email").count() == 0


@pytest.mark.parametrize("path", ["direct", "envelope"])
def test_payer_optout_blocks_document_retry(document, document_mail, path, lane,
        django_capture_on_commit_callbacks, mailoutbox):
    with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("SMTP unavailable")):
        envelope = issue_mail(document, path, django_capture_on_commit_callbacks, document_mail)
    assert len(document_mail.rendered) == 1
    logs = EmailLog.objects.filter(event="document_issued", source_id=str(envelope.pk),
                                   recipient_id=document.payment.member_id)
    assert logs.count() == 1
    history = logs.values().get()
    assert (history["status"], history["error"]) == ("failed", "email_delivery_failed:OSError")
    MemberNotificationPreference.objects.create(makerspace=lane.space, user=document.payment.member,
                                                feature="payments", channel="email", enabled=False)
    retry_mail(path, envelope)
    assert mailoutbox == [] and len(document_mail.rendered) == 1
    assert logs.count() == 1
    if path == "direct":
        assert (logs.get().status, logs.get().error) == ("skipped", "email_member_opted_out")
    else:
        delivery = envelope.deliveries.get(channel="email")
        assert (delivery.state, delivery.last_error) == ("skipped", "live_eligibility_changed")
        assert logs.get().source_metadata["delivery_id"] == delivery.pk
        assert logs.values().get() == history


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
    history = EmailLog.objects.values().get(event="document_issued", source_id=str(envelope.pk),
                                            recipient_id=document.payment.member_id)
    assert (history["status"], history["error"]) == ("failed", "email_delivery_failed:OSError")
    owner = document.payment.member
    owner.email = "unproven-payer@example.test"
    owner.save(update_fields=["email"])
    assert owner.email_verified_at is None
    retry_mail("envelope", envelope)
    assert mailoutbox == [] and document_mail.rendered == [document.pk]
    deliveries = envelope.deliveries.filter(channel="email")
    assert deliveries.count() == 1
    delivery = deliveries.get()
    assert (delivery.state, delivery.last_error) == ("skipped", "live_eligibility_changed")
    logs = EmailLog.objects.filter(source_kind="notification.envelope", source_id=str(envelope.pk),
        recipient_id=owner.pk, source_metadata__delivery_id=delivery.pk, event="document_issued")
    assert logs.count() == 1
    assert logs.values().get() == history


@pytest.mark.parametrize("path", ["direct", "envelope"])
def test_oversize_document_fails_delivery_instead_of_sending_link_only(document, document_mail, path, monkeypatch,
        django_capture_on_commit_callbacks, mailoutbox):
    monkeypatch.setattr("apps.payments.document_pdf.render_document_pdf", lambda row: b"x" * (5 * 1024 * 1024 + 1))
    envelope = issue_mail(document, path, django_capture_on_commit_callbacks, document_mail)
    assert mailoutbox == []
    logs = EmailLog.objects.filter(makerspace=document.makerspace, event="document_issued",
        source_id=str(envelope.pk), recipient_id=document.payment.member_id)
    assert logs.count() == 1
    log = logs.get()
    assert (log.status, log.error) == ("failed", "document_size_exceeded")
    if path == "envelope":
        assert log.source_metadata["delivery_id"] == envelope.deliveries.get(channel="email").pk
    else:
        assert log.source_metadata["document"] == {"document_id": document.pk, "kind": document.kind}


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


@pytest.mark.parametrize("path", ["direct", "envelope"])
def test_email_module_off_keeps_document_and_blocks_its_attachment(document, document_mail, lane, path,
        django_capture_on_commit_callbacks, mailoutbox):
    original = document_ledger_snapshot(document)
    modules = list(lane.space.enabled_modules)
    lane.space.enabled_modules = [key for key in lane.space.enabled_modules if key != "email"]
    lane.space.save(update_fields=["enabled_modules"])
    envelope = issue_mail(document, path, django_capture_on_commit_callbacks, document_mail)
    assert mailoutbox == []
    assert document_mail.rendered == []
    assert document.payment.documents.filter(pk=document.pk).count() == 1
    assert not EmailLog.objects.filter(event="document_issued", status="sent").exists()
    assert document_ledger_snapshot(document) == original
    assert envelope.deliveries.filter(channel="email").count() == 0
    suppressed = EmailLog.objects.get(event="document_issued")
    assert suppressed.status == "skipped"
    assert suppressed.error == "Email is disabled for this makerspace."
    assert suppressed.source_kind == "notification.direct"
    assert suppressed.source_id == envelope.pk
    assert suppressed.source_metadata["p2_direct"] == envelope.dedup_key
    # A second emission while disabled must neither render nor add another intent.
    assert issue_mail(document, path, django_capture_on_commit_callbacks, document_mail).pk == envelope.pk
    assert mailoutbox == [] and document_mail.rendered == []
    assert EmailLog.objects.filter(event="document_issued").count() == 1
    assert document_ledger_snapshot(document) == original

    lane.space.enabled_modules = modules
    lane.space.save(update_fields=["enabled_modules"])
    restored = issue_mail(document, path, django_capture_on_commit_callbacks, document_mail)
    assert restored.pk == envelope.pk
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == [document.payment.member.email]
    assert mailoutbox[0].attachments == [(f"{document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-1", "application/pdf")]
    assert document_mail.rendered == [document.pk]
    sent = assert_mail_owner(document, path, envelope, skipped_direct=1)
    assert document_ledger_snapshot(document) == original
    assert issue_mail(document, path, django_capture_on_commit_callbacks, document_mail).pk == envelope.pk
    deliver_envelope(envelope.pk)
    assert len(mailoutbox) == 1 and document_mail.rendered == [document.pk]
    assert assert_mail_owner(document, path, envelope, skipped_direct=1).pk == sent.pk
    suppressed.refresh_from_db()
    assert (suppressed.status, suppressed.error) == ("skipped", "Email is disabled for this makerspace.")
    assert document_ledger_snapshot(document) == original


@pytest.mark.parametrize("path", ["direct", "envelope"])
def test_document_capability_back_on_restores_mail_with_ledger_kept(document, document_mail, lane, path,
        django_capture_on_commit_callbacks, mailoutbox):
    from apps.payments.document_delivery import DocumentDeliveryError, render_attachment
    from apps.payments.notifications_p2 import document_eligible

    original = document_ledger_snapshot(document)
    features = lane.space.enabled_features
    lane.space.enabled_features = [key for key in features if key != "billing.documents"]
    lane.space.save(update_fields=["enabled_features"])
    envelope = issue_mail(document, path, django_capture_on_commit_callbacks, document_mail)
    assert mailoutbox == []
    assert document_mail.rendered == []
    assert not EmailLog.objects.filter(event="document_issued").exists()
    assert document.payment.documents.filter(pk=document.pk).count() == 1
    assert document_ledger_snapshot(document) == original
    assert document_eligible(envelope) is False
    assert envelope.deliveries.filter(channel="email").count() == 0
    with pytest.raises(DocumentDeliveryError) as refused:
        render_attachment({"document_id": document.pk, "kind": document.kind},
                          makerspace_id=lane.space.pk, recipient_id=document.payment.member_id)
    assert str(refused.value) == "document_not_authorized"
    assert issue_mail(document, path, django_capture_on_commit_callbacks, document_mail).pk == envelope.pk
    assert mailoutbox == [] and document_mail.rendered == []
    assert EmailLog.objects.filter(event="document_issued").count() == 0
    assert document_ledger_snapshot(document) == original

    lane.space.enabled_features = sorted(set(features) | {"billing.documents"})
    lane.space.save(update_fields=["enabled_features"])
    assert issue_mail(document, path, django_capture_on_commit_callbacks, document_mail).pk == envelope.pk
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == [document.payment.member.email]
    assert document_mail.rendered == [document.pk]
    assert EmailLog.objects.filter(event="document_issued", status="sent").count() == 1
    assert mailoutbox[0].attachments == [(f"{document.number}.pdf", b"%PDF-1.7\nprivate-payer-document-1", "application/pdf")]
    assert document_eligible(envelope) is True
    sent = assert_mail_owner(document, path, envelope)
    assert document_ledger_snapshot(document) == original
    assert issue_mail(document, path, django_capture_on_commit_callbacks, document_mail).pk == envelope.pk
    deliver_envelope(envelope.pk)
    assert len(mailoutbox) == 1 and document_mail.rendered == [document.pk]
    assert assert_mail_owner(document, path, envelope).pk == sent.pk
    assert document_ledger_snapshot(document) == original


@pytest.mark.parametrize("channels", [[], ["telegram"]])
def test_direct_document_mail_respects_personal_channel_selection(document, document_mail, channels,
        django_capture_on_commit_callbacks, mailoutbox):
    document_mail.route("direct")
    NotificationPreference.objects.filter(makerspace=document.makerspace, user=document.payment.member,
                                          category="payments").update(channels=channels, email_fallback=False)
    document.makerspace.refresh_from_db()
    with django_capture_on_commit_callbacks(execute=True):
        notify_document(document)
    assert mailoutbox == []
    assert document_mail.rendered == []
    log = EmailLog.objects.get(event="document_issued")
    assert log.status == "skipped"
    assert log.error == "email_member_opted_out"
    assert log.recipient_id == document.payment.member_id
