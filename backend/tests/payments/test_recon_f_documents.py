"""Native captures use the core bill/receipt/credit-note and payer-only pipeline."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from apps.audit.models import AuditLog
from apps.integrations.models_contract import NotificationEnvelope
from apps.operations.notifications_p2 import revision
from apps.payments.document_delivery import (
    DocumentDeliveryError, attachment_references, authorized_document, render_attachment,
)
from apps.payments.documents import issue_bill
from apps.payments.models import MakerspaceBillingSettings, PaymentDocument, Refund
from apps.payments.notification_projections import payment_subject
from apps.payments.notifications_p2 import rendered
from apps.payments.providers.base import WebhookEvent
from apps.payments.services_refunds import settle_refund
from apps.payments.services_webhooks import apply_razorpay_webhook_event, apply_webhook_event
from tests.payments.recon_f_helpers import pending_charge
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db


def native_charge(provider):
    handles = ({"stripe_payment_intent_id": "pi_recon_documents"} if provider == "stripe"
               else {"external_order_id": "order_recon_documents"})
    return pending_charge(f"{provider}-recon-documents", provider=provider,
                          online_rail="native_payment_intent", **handles)


def capture(payment, event_id):
    if payment.provider == "stripe":
        return apply_webhook_event(payment.makerspace, {
            "id": event_id, "type": "payment_intent.succeeded",
            "data": {"object": {"id": payment.stripe_payment_intent_id}},
        })
    return apply_razorpay_webhook_event(payment.makerspace, WebhookEvent(
        event_id=event_id, is_paid=True, order_id=payment.external_order_id,
        payment_id="pay_recon_documents", amount_minor=1000, currency="USD",
    ))


@pytest.mark.parametrize("provider", ["stripe", "razorpay"])
@pytest.mark.parametrize("waived", [False, True])
def test_native_capture_and_callback_replay_issue_one_receipt(provider, waived):
    space, staff, payment = native_charge(provider)
    bill = issue_bill(payment, actor=staff)
    if waived:
        from apps.payments.reconciliation import waive
        # External cancellation is best-effort; no configured provider is needed here.
        waive(payment, staff)
    capture(payment, "evt_capture_first")
    capture(payment, "evt_capture_first")
    capture(payment, "evt_capture_second_shape")
    payment.refresh_from_db()
    receipt = PaymentDocument.objects.get(payment=payment, kind="receipt")
    assert payment.status == "paid_online"
    assert receipt.amount == payment.amount and receipt.settlement_method == provider
    assert PaymentDocument.objects.filter(payment=payment).count() == 2
    assert bill.number == "BILL-000001" and receipt.number == "000001"
    assert MakerspaceBillingSettings.objects.get(makerspace=space).next_document_number == 2
    assert AuditLog.objects.filter(makerspace=space, action="payment.document_issued").count() == 2
    assert not AuditLog.objects.filter(makerspace=space, action="payment.double_paid_refund_required").exists()
    if provider == "razorpay":
        assert payment.external_payment_id == "pay_recon_documents"
    envelopes = NotificationEnvelope.objects.filter(
        makerspace=space, source_kind="payments.document", source_id=str(receipt.pk),
    )
    assert envelopes.count() == 1
    assert envelopes.get().recipient_id == payment.member_id
    assert envelopes.get().audience == "requester"


@pytest.mark.parametrize("provider", ["stripe", "razorpay"])
def test_native_refund_callback_and_sync_completion_share_one_credit_note(provider):
    space, staff, payment = native_charge(provider)
    capture(payment, "evt_paid")
    payment.refresh_from_db()
    refund = Refund.objects.create(payment=payment, provider=provider, amount="3.00",
                                   currency=payment.currency, created_by=staff)
    if provider == "stripe":
        event = {"id": "evt_refund", "type": "refund.updated", "data": {"object": {
            "id": "re_recon", "payment_intent": payment.stripe_payment_intent_id,
            "amount": 300, "status": "succeeded",
        }}}
        apply_webhook_event(space, event)
        apply_webhook_event(space, event)
        apply_webhook_event(space, {**event, "id": "evt_refund_again"})
    else:
        event = WebhookEvent(event_id="evt_refund", is_paid=False,
            payment_id=payment.external_payment_id, refund_id="re_recon",
            refund_status="succeeded", refund_amount_minor=300)
        apply_razorpay_webhook_event(space, event)
        apply_razorpay_webhook_event(space, event)
        apply_razorpay_webhook_event(space, replace(event, event_id="evt_refund_again"))
    # The synchronous provider response can arrive after its webhook.
    settle_refund(refund, external_refund_id="re_recon", status="succeeded", actor=staff)
    refund.refresh_from_db()
    assert refund.status == "succeeded"
    credit = PaymentDocument.objects.get(refund=refund)
    assert credit.kind == "credit_note" and credit.amount == refund.amount
    assert PaymentDocument.objects.filter(payment=payment).count() == 2
    assert AuditLog.objects.filter(makerspace=space, action="payment.refunded").count() == 1


def test_refund_projection_redacts_all_money_from_staff_templates(monkeypatch):
    _, _, payment = native_charge("stripe")
    refund = SimpleNamespace(amount="3.00")
    assert vars(payment_subject(payment, audience="requester", refund=refund))["amount"] == "3.00"
    seen = []
    def template(space, stream, audience, event, context, **kwargs):
        seen.append((audience, vars(context["subject"])))
        return context
    monkeypatch.setattr("apps.payments.notifications_p2.template", template)
    rendered(payment, "refund_issued", "staff", refund)
    rendered(payment, "refund_issued", "requester", refund)
    staff_subject, payer_subject = seen[0][1], seen[1][1]
    assert staff_subject["id"] == payment.pk and staff_subject["status"] == "pending"
    assert set(staff_subject) - {"_frozen"} == {"id", "status"}
    assert payer_subject["amount"] == "3.00" and payer_subject["currency"] == "usd"


def test_attachments_require_current_payer_and_source_authority():
    space, staff, payment = native_charge("stripe")
    capture(payment, "evt_private_document")
    document = PaymentDocument.objects.get(payment=payment, kind="receipt")
    envelope = SimpleNamespace(source_kind="payments.document", source_id=str(document.pk),
        makerspace_id=space.pk, recipient_id=payment.member_id, audience="requester",
        event="document_issued", revision=revision(document.pk, document.issued_at))
    reference = {"document_id": document.pk, "kind": "receipt"}
    assert attachment_references(envelope) == (reference,)
    assert authorized_document(reference, makerspace_id=space.pk, recipient_id=payment.member_id).pk == document.pk
    for changes in ({"audience": "staff"}, {"recipient_id": staff.pk},
                    {"revision": "obsolete"}, {"makerspace_id": make_space("document-foreign").pk}):
        forged = SimpleNamespace(**{**vars(envelope), **changes})
        with pytest.raises(DocumentDeliveryError, match="document_not_authorized"):
            attachment_references(forged)
    assert attachment_references(SimpleNamespace(source_kind="payments.ledger")) == ()
    stranger = make_user("document-stranger")
    for recipient_id in (stranger.pk, staff.pk):
        with pytest.raises(DocumentDeliveryError, match="document_not_authorized"):
            authorized_document(reference, makerspace_id=space.pk, recipient_id=recipient_id)
    payer = payment.member
    payer.access_status = "restricted"
    payer.save(update_fields=["access_status"])
    with pytest.raises(DocumentDeliveryError, match="document_not_authorized"):
        render_attachment(reference, makerspace_id=space.pk, recipient_id=payer.pk)
