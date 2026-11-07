"""Online payment of a hosting invoice through the PLATFORM's own Stripe or Razorpay
account (#187A), behind ``MANAGED_BILLING_ONLINE_ENABLED`` (off) and its own keys.

The Space Manager opens a checkout (the payer acts); nothing is ever charged without
them. The provider's signed callback settles the invoice exactly once (the receipt's
``(method, reference)`` is unique for online methods). A callback for an amount or
currency other than the invoice's is refused, never partially applied.
"""

import hashlib
import hmac
import json
import logging

import requests
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.space_controls.errors import SpaceControlConflict

from .availability import public_base_url, require_online_billing
from .models import HostingInvoice, HostingInvoiceReceipt, PlatformHostingBillingSettings

logger = logging.getLogger(__name__)
TIMEOUT = 15


class ProviderUnavailable(SpaceControlConflict):
    def __init__(self, detail="Online payment is not configured for hosting invoices."):
        super().__init__("online_billing_unavailable", detail)


def start_checkout(makerspace_id, invoice_id, *, actor=None):
    require_online_billing()
    settings_row = PlatformHostingBillingSettings.load()
    with transaction.atomic():
        invoice = HostingInvoice.objects.select_for_update().get(pk=invoice_id, makerspace_id=makerspace_id)
        if invoice.status != HostingInvoice.Status.OPEN:
            raise SpaceControlConflict("invoice_not_open", "This invoice is not open.")
    # The plan and its invoices live on the "Usage & limits" tab (TenantUsagePanel).
    back = f"{public_base_url()}/m/{invoice.makerspace.slug}/admin/usage?invoice={invoice.pk}"
    if settings_row.provider == "stripe" and settings_row.stripe_secret_key:
        session_id, url = _stripe_session(settings_row, invoice, back)
    elif settings_row.provider == "razorpay" and settings_row.razorpay_key_id and settings_row.razorpay_key_secret:
        session_id, url = _razorpay_link(settings_row, invoice, back)
    else:
        raise ProviderUnavailable()
    HostingInvoice.objects.filter(pk=invoice.pk).update(provider=settings_row.provider, provider_session_id=session_id)
    audit.record(actor, "managed_hosting.invoice_checkout_started", makerspace=invoice.makerspace, target=invoice,
                 meta={"provider": settings_row.provider})
    return url


def _stripe_session(settings_row, invoice, back):
    import stripe

    try:
        session = stripe.checkout.Session.create(
            api_key=settings_row.secret("stripe_secret_key"), mode="payment",
            line_items=[{"quantity": 1, "price_data": {
                "currency": invoice.currency.lower(), "unit_amount": invoice.amount_minor,
                "product_data": {"name": f"Space Works hosting {invoice.number}"}}}],
            success_url=back + "&paid=1", cancel_url=back,
            client_reference_id=str(invoice.pk), metadata={"hosting_invoice_id": str(invoice.pk)},
        )
    except Exception as exc:  # provider text may carry account details: log the type only
        logger.warning("hosting_checkout_failed", extra={"provider": "stripe", "error_class": type(exc).__name__})
        raise ProviderUnavailable("The payment provider refused the checkout. Try again later.") from exc
    return session["id"], session["url"]


def _razorpay_link(settings_row, invoice, back):
    try:
        response = requests.post(
            "https://api.razorpay.com/v1/payment_links", timeout=TIMEOUT,
            auth=(settings_row.razorpay_key_id, settings_row.secret("razorpay_key_secret")),
            json={"amount": invoice.amount_minor, "currency": invoice.currency, "reference_id": invoice.number,
                  "description": f"Space Works hosting {invoice.number}", "callback_url": back,
                  "callback_method": "get", "notes": {"hosting_invoice_id": str(invoice.pk)}})
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        logger.warning("hosting_checkout_failed", extra={"provider": "razorpay", "error_class": type(exc).__name__})
        raise ProviderUnavailable("The payment provider refused the checkout. Try again later.") from exc
    return body["id"], body["short_url"]


def verify_stripe(payload, signature):
    import stripe

    settings_row = PlatformHostingBillingSettings.load()
    secret = settings_row.secret("stripe_webhook_secret")
    if not secret:
        raise ValueError("No Stripe webhook secret.")
    event = stripe.Webhook.construct_event(payload, signature, secret)
    if event["type"] != "checkout.session.completed":
        return None
    session = event["data"]["object"]
    if session.get("payment_status") != "paid":
        return None
    return {"invoice_id": (session.get("metadata") or {}).get("hosting_invoice_id"),
            "amount_minor": session.get("amount_total"), "currency": (session.get("currency") or "").upper(),
            "reference": session.get("payment_intent") or session["id"], "method": HostingInvoiceReceipt.Method.ONLINE_STRIPE}


def verify_razorpay(payload, signature):
    secret = PlatformHostingBillingSettings.load().secret("razorpay_webhook_secret")
    if not secret or not signature:
        raise ValueError("Missing Razorpay secret or signature.")
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected.encode(), signature.encode("utf-8", "replace")):
        raise ValueError("Razorpay signature mismatch.")
    body = json.loads(payload.decode() or "{}")
    if body.get("event") != "payment_link.paid":
        return None
    link = ((body.get("payload") or {}).get("payment_link") or {}).get("entity") or {}
    payment = ((body.get("payload") or {}).get("payment") or {}).get("entity") or {}
    return {"invoice_id": (link.get("notes") or {}).get("hosting_invoice_id"),
            "amount_minor": payment.get("amount"), "currency": (payment.get("currency") or "").upper(),
            "reference": payment.get("id") or link.get("id"), "method": HostingInvoiceReceipt.Method.ONLINE_RAZORPAY}


def settle(event):
    """Apply one verified paid event; returns True when this call settled the invoice."""
    from .billing import _settle

    if not event or not str(event.get("invoice_id") or "").isdigit():
        return False
    with transaction.atomic():
        invoice = HostingInvoice.objects.select_for_update().filter(pk=int(event["invoice_id"])).first()
        if invoice is None or invoice.status != HostingInvoice.Status.OPEN:
            return False
        if event["amount_minor"] != invoice.amount_minor or event["currency"] != invoice.currency:
            logger.warning("hosting_payment_mismatch", extra={"hosting_invoice_id": invoice.pk})
            return False
        try:
            with transaction.atomic():
                _settle(invoice, method=event["method"], reference=str(event["reference"]),
                        received_on=timezone.localdate(), amount_minor=invoice.amount_minor, note="", actor=None)
        except IntegrityError:
            return False
    return True
