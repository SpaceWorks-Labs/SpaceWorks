"""Fail-safe payer-only mail; download grants remain short-lived and user-bound."""

import logging
from urllib.parse import urlencode

from django.core import signing
from django.urls import reverse

logger = logging.getLogger(__name__)
DOWNLOAD_TTL = 300
SALT = "payments.document.download.v1"


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
