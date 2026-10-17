"""Fail-safe payer-only mail; download grants remain short-lived and user-bound."""

import logging
from urllib.parse import urlencode

from django.core import signing
from django.urls import reverse

logger = logging.getLogger(__name__)
DOWNLOAD_TTL = 300
SALT = "payments.document.download.v1"
DOCUMENT_KINDS = {"receipt", "credit_note", "bill"}
MAX_PDF_BYTES = 5 * 1024 * 1024


class DocumentDeliveryError(ValueError):
    """A fixed diagnostic, safe to persist in delivery health."""


def attachment_references(envelope):
    """Derive references from the live source, never from arbitrary message JSON."""
    if envelope.source_kind != "payments.document":
        return ()
    from apps.operations.notifications_p2 import scoped
    from apps.payments.models import PaymentDocument
    from .notifications_p2 import document_eligible
    if not document_eligible(envelope):
        raise DocumentDeliveryError("document_not_authorized")
    document = scoped(PaymentDocument, envelope.makerspace_id).get(pk=envelope.source_id)
    return ({"document_id": document.pk, "kind": document.kind},) if document.kind in DOCUMENT_KINDS else ()


def authorized_document(reference, *, makerspace_id, recipient_id):
    from apps.operations.notifications_p2 import scoped
    from apps.payments.models import PaymentDocument
    from apps.makerspaces.platform import feature_enabled
    from apps.makerspaces.servability import is_servable
    from apps.notifications.inbox import eligible_owner
    from .member_access import member_may_see_own_charges
    if (not isinstance(reference, dict) or set(reference) != {"document_id", "kind"}
            or type(reference["document_id"]) is not int or reference["document_id"] < 1
            or not isinstance(reference["kind"], str)
            or not 1 <= len(reference["kind"]) <= 16
            or not recipient_id or not makerspace_id):
        raise DocumentDeliveryError("document_not_authorized")
    document = scoped(PaymentDocument, makerspace_id).select_related("payment__member", "makerspace").filter(
        pk=reference["document_id"], kind=reference["kind"], payment__member_id=recipient_id,
        payment__makerspace_id=makerspace_id,
    ).first()
    if (document is None or not is_servable(document.makerspace)
            or not feature_enabled(document.makerspace, "billing.documents")
            or not eligible_owner(document.makerspace, recipient_id)
            or not member_may_see_own_charges(document.payment.member, makerspace_id)):
        raise DocumentDeliveryError("document_not_authorized")
    return document


def render_attachment(reference, *, makerspace_id, recipient_id):
    from django.utils.text import get_valid_filename
    from .document_pdf import render_document_pdf
    document = authorized_document(reference, makerspace_id=makerspace_id, recipient_id=recipient_id)
    if document.kind not in DOCUMENT_KINDS:
        raise DocumentDeliveryError("document_not_authorized")
    try:
        pdf = render_document_pdf(document)
    except Exception:
        raise DocumentDeliveryError("document_render_failed") from None
    if not isinstance(pdf, bytes):
        raise DocumentDeliveryError("document_render_failed")
    if len(pdf) > MAX_PDF_BYTES:
        raise DocumentDeliveryError("document_size_exceeded")
    if not pdf.startswith(b"%PDF-"):
        raise DocumentDeliveryError("document_render_failed")
    return get_valid_filename(document.number) + ".pdf", pdf, "application/pdf"


def prepare_document_email(log):
    """Compatibility mail without an envelope still reloads the payer on retry."""
    from apps.integrations.delivery_content import render
    from .notifications_p2 import document_body
    reference = log.source_metadata.get("document", {})
    if str(reference.get("document_id")) != str(log.source_id) or log.event != "document_issued":
        return False
    try:
        document = authorized_document(reference, makerspace_id=log.makerspace_id, recipient_id=log.recipient_id)
    except DocumentDeliveryError:
        return False
    address = document.payment.member.email
    if not address:
        return False
    value = document_body(document)
    render(log, to_email=address, subject=value["subject"], text_body=value["text"],
           html_body=value.get("html", ""),
           attachments=(reference,) if document.kind in DOCUMENT_KINDS else ())
    return True


def download_path(document, user, *, makerspace_id, audience):
    token = signing.dumps({"document": document.pk, "user": user.pk,
                           "space": makerspace_id, "audience": audience}, salt=SALT)
    return reverse("payment-document-download", args=[document.pk]) + "?" + urlencode({"token": token})


def email_document(document_id):
    """No arbitrary recipient is accepted; contact is read from the payment owner."""
    from apps.payments.models import PaymentDocument
    from apps.payments.notifications_p2 import notify_document
    from apps.operations.notifications_p2 import scoped

    try:
        seed = PaymentDocument.objects.only("makerspace_id").get(pk=document_id)
        document = scoped(PaymentDocument, seed.makerspace_id).select_related(
            "payment__member", "makerspace",
        ).get(pk=document_id)
        return notify_document(document)
    except Exception:
        logger.warning("payment_document_notification_failed", extra={"document_id": document_id})
