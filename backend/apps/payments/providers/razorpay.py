"""Razorpay Payment Links for browsers and Orders for native Checkout.

**Self-host / own-account only, by owner decision.** Razorpay has no equivalent of
Stripe Connect in this design, so there is no way to route a platform fee or to charge
on behalf of a tenant from a platform account. Managed hosting therefore keeps Stripe
Connect as its only rail, and `resolve_payment_source` never returns a Razorpay source
for a Connect-backed makerspace. Razorpay Route would be its own piece of work.

stdlib ``urllib`` rather than the vendor SDK, matching ``integrations/sms/twilio.py``:
three endpoints and an HMAC do not justify a dependency, and it keeps the seam honest
about how little a provider actually has to do.
"""

import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.request
from base64 import b64encode
from urllib.parse import quote, urlencode

from apps.payments.method_labels import razorpay_label
from apps.payments.providers.base import (
    RAZORPAY,
    CheckoutRequest,
    CheckoutResult,
    PaymentsUnavailable,
    ProviderOutcomeUnknown,
    RefundRequest,
    RefundResult,
    WebhookEvent,
    WebhookVerificationError,
)

logger = logging.getLogger(__name__)

API_ROOT = "https://api.razorpay.com/v1"
TIMEOUT_SECONDS = 15

# Only these mean "the money is captured". `payment.authorized` deliberately does NOT:
# an authorised-but-uncaptured payment is not settled, and treating it as paid would
# mark a charge complete for money that can still fail to arrive.
PAID_EVENTS = frozenset({"payment_link.paid", "order.paid", "payment.captured"})
# Razorpay refund statuses, normalised to the three the Refund row knows. `created`
# and `pending` both mean "accepted, money not yet back"; only `processed` is final.
REFUND_STATUSES = {
    "processed": "succeeded",
    "pending": "pending",
    "created": "pending",
    "failed": "failed",
}


class RazorpayRequestError(PaymentsUnavailable):
    """Sanitized public message; provider diagnostics are retained only for recovery."""

    def __init__(self, status, code="", description=""):
        super().__init__("Razorpay rejected the request.")
        self.status, self.code, self.description = status, code, description

    @property
    def is_duplicate_receipt(self):
        description = self.description.lower()
        return (
            self.status == 400 and self.code == "BAD_REQUEST_ERROR"
            and "receipt" in description
            and any(word in description for word in ("unique", "duplicate", "already"))
        )


class RazorpayUnreadableResponse(ProviderOutcomeUnknown):
    """An unusable 2xx answer. `outcome_unknown` keeps a refund PENDING and reserved."""

    status = 200

    def __init__(self):
        super().__init__("Razorpay sent an unreadable response.")


class RazorpayProvider:
    key = RAZORPAY

    # ---- HTTP ------------------------------------------------------------------

    def _request(self, source, method, path, body=None, *, idempotency_key=None):
        if not (source.secret_key and source.publishable_key):
            raise PaymentsUnavailable("Razorpay credentials are not configured.")
        # publishable_key carries the key_id, secret_key the key_secret. Reusing the
        # existing PaymentSource fields keeps one resolution path for both providers
        # rather than a parallel Razorpay-shaped source object.
        token = b64encode(
            f"{source.publishable_key}:{source.secret_key}".encode()
        ).decode()
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"{API_ROOT}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Basic {token}",
                "Content-Type": "application/json",
                # Payments audit 0.12.0 C-9: a retried refund POST must not move the money twice.
                # Razorpay refund idempotency header (docs: api/refunds/normal-refunds-idempotent).
                **({"X-Refund-Idempotency": idempotency_key} if idempotency_key else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            # The body can echo back the description and notes, which carry a member's
            # name. Log the status only -- an integration log is not the place for it.
            logger.warning(
                "razorpay_http_error", extra={"status": exc.code, "path": path}
            )
            try:
                error = json.loads(exc.read().decode()).get("error", {})
                code, description = error.get("code", ""), error.get("description", "")
            except (ValueError, AttributeError, OSError):
                code, description = "", ""
            raise RazorpayRequestError(
                exc.code, str(code), str(description)
            ) from None
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            logger.warning("razorpay_unreachable", extra={"path": path})
            raise PaymentsUnavailable("Razorpay could not be reached.") from exc
        try:
            result = json.loads(raw.decode())
            if not isinstance(result, dict):
                raise ValueError("Expected an object.")
            return result
        except ValueError:
            # Razorpay answered 2xx, so it may well have acted (PAY-REVIEW 0.12.0): a refund whose
            # answer we cannot read is an UNKNOWN outcome, never a refusal that frees its balance.
            logger.warning("razorpay_unreadable_response", extra={"path": path})
            raise RazorpayUnreadableResponse() from None

    # ---- Provider protocol -----------------------------------------------------

    def create_order(self, source, *, amount_minor, currency, receipt, notes):
        return self._request(source, "POST", "/orders", {
            "amount": amount_minor, "currency": currency.upper(), "receipt": receipt,
            "notes": {key: str(value) for key, value in notes.items()},
            # Ask for automatic capture (PAY-REVIEW 0.12.0): an authorised-but-uncaptured payment
            # never settles here and Razorpay auto-refunds it. The Dashboard capture setting is
            # still documented as required, in case an account overrides the per-order flag.
            "payment_capture": 1,
        })

    def fetch_order(self, source, order_id):
        return self._request(source, "GET", f"/orders/{quote(order_id, safe='')}")

    def fetch_orders_by_receipt(self, source, receipt):
        orders, skip = [], 0
        while True:
            query = urlencode({"receipt": receipt, "count": 100, "skip": skip})
            result = self._request(source, "GET", f"/orders?{query}")
            items = result.get("items") if isinstance(result, dict) else None
            if not isinstance(items, list):
                raise PaymentsUnavailable("Razorpay returned an invalid order list.")
            orders.extend(items)
            if len(items) < 100:
                return orders
            skip += len(items)

    def create_checkout(self, source, request: CheckoutRequest) -> CheckoutResult:
        # Payments audit 0.12.0: Razorpay refuses a reused `reference_id`, so the link raised
        # after an expired/cancelled one carries the idempotency key's generation. The first
        # link keeps the bare payment id, exactly as before.
        generation = (request.idempotency_key or "").rpartition("-")[2]
        reference = request.reference if generation in ("", "0") else f"{request.reference}-{generation}"[:40]
        payload = {
            "amount": request.amount_minor,
            # Razorpay wants the ISO code uppercase; the rest of this codebase stores
            # currency lowercase, so the conversion belongs here rather than leaking a
            # provider's spelling into the Payment row.
            "currency": request.currency.upper(),
            "description": request.description[:2048],
            "reference_id": reference,
            "callback_url": request.success_url,
            "callback_method": "get",
            # Razorpay calls it `notes`; it is the `metadata` echo the webhook needs to
            # find the Payment row without trusting anything the payer could edit.
            "notes": {key: str(value) for key, value in (request.metadata or {}).items()},
            # We already email members ourselves through the notification matrix, and a
            # second unmanaged channel would bypass every recipient rule and module gate.
            "notify": {"sms": False, "email": False},
            "reminder_enable": False,
        }
        result = self._request(source, "POST", "/payment_links", payload)
        order_id, checkout_url = result.get("id"), result.get("short_url")
        if not order_id or not checkout_url:
            raise PaymentsUnavailable("Razorpay did not return a payment link.")
        return CheckoutResult(order_id=order_id, checkout_url=checkout_url)

    def expire_checkout(self, source, order_id: str) -> bool:
        """Cancel a link; True only when Razorpay confirms it can no longer take money."""
        if not order_id:
            return True
        try:
            self._request(source, "POST", f"/payment_links/{order_id}/cancel")
            return True
        except PaymentsUnavailable:
            # Best effort by contract: the reconciliation that called this must still
            # succeed. A link that outlives its payment is caught by the webhook, which
            # corrects a waiver or raises an explicit refund-required audit condition.
            logger.info("razorpay_link_cancel_failed", extra={"order_id": order_id})
        # PAY-REVIEW 0.12.0: a refused cancel is often a link that is already closed. Only an
        # authoritative read says so; the gateway poll forgets a link's id only on True, because a
        # forgotten link that is still payable takes money no webhook can match to its charge.
        try:
            link = self._request(source, "GET", f"/payment_links/{order_id}")
        except PaymentsUnavailable:
            return False
        return isinstance(link, dict) and link.get("status") in {"cancelled", "expired"}

    def create_refund(self, source, request: RefundRequest) -> RefundResult:
        if not request.payment_id:
            raise PaymentsUnavailable("The payment has no Razorpay payment id to refund.")
        result = self._request(
            source,
            "POST",
            f"/payments/{request.payment_id}/refund",
            {
                "amount": request.amount_minor,
                "receipt": request.reference[:40],
                "notes": {key: str(value) for key, value in (request.metadata or {}).items()},
            },
            # The caller keys it on the Refund row (`payment-refund-<pk>`), stable across retries.
            idempotency_key=request.idempotency_key or None,
        )
        refund_id = result.get("id")
        if not isinstance(refund_id, str) or not refund_id.strip():
            raise RazorpayUnreadableResponse()
        return RefundResult(
            refund_id=refund_id,
            status=REFUND_STATUSES.get(str(result.get("status") or ""), "pending"),
        )

    def verify_webhook(self, source, *, payload: bytes, headers) -> WebhookEvent:
        signature = headers.get("X-Razorpay-Signature") or headers.get(
            "HTTP_X_RAZORPAY_SIGNATURE", ""
        )
        secret = source.webhook_secret
        if not secret:
            raise WebhookVerificationError("No Razorpay webhook secret is configured.")
        if not signature:
            raise WebhookVerificationError("Missing Razorpay signature header.")
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        # compare_digest, not ==: a short-circuiting comparison leaks the correct prefix
        # through timing, which is enough to forge a signature given enough attempts.
        # Compared as bytes: on str arguments compare_digest raises TypeError for any
        # non-ASCII header character, turning a forged signature into a 500 (and a retry).
        if not hmac.compare_digest(expected.encode(), signature.encode("utf-8", "replace")):
            raise WebhookVerificationError("Razorpay signature mismatch.")
        try:
            body = json.loads(payload.decode() or "{}")
        except ValueError as exc:
            raise WebhookVerificationError("Razorpay sent an unparseable body.") from exc

        event_type = body.get("event") or ""
        entities = body.get("payload") or {}
        link = (entities.get("payment_link") or {}).get("entity") or {}
        payment = (entities.get("payment") or {}).get("entity") or {}
        order = (entities.get("order") or {}).get("entity") or {}
        refund = (entities.get("refund") or {}).get("entity") or {}
        dispute = (entities.get("dispute") or {}).get("entity") or {}

        # Razorpay does not send a top-level event id, so the delivery id header is the
        # idempotency anchor. Falling back to the entity id keeps the record unique per
        # charge when a proxy strips the header, which is worse than the header but far
        # better than treating every delivery as new.
        event_id = (
            headers.get("X-Razorpay-Event-Id")
            or headers.get("HTTP_X_RAZORPAY_EVENT_ID")
            or f"{event_type}:{refund.get('id') or link.get('id') or payment.get('id') or order.get('id') or ''}"
        )
        return WebhookEvent(
            event_id=event_id,
            is_paid=event_type in PAID_EVENTS,
            is_failed=event_type == "payment.failed",
            amount_minor=int(payment.get("amount") or order.get("amount") or link.get("amount") or 0),
            currency=payment.get("currency") or order.get("currency") or link.get("currency") or "",
            order_id=link.get("id") or order.get("id") or payment.get("order_id") or "",
            payment_id=payment.get("id") or refund.get("payment_id") or dispute.get("payment_id") or "",
            metadata=link.get("notes") or payment.get("notes") or order.get("notes") or {},
            refund_id=refund.get("id") or "",
            refund_status=REFUND_STATUSES.get(refund.get("status") or "", ""),
            refund_amount_minor=int(refund.get("amount") or 0),
            method_label=razorpay_label(payment),
            dispute_id=dispute.get("id") or "",
            dispute_status=str(dispute.get("status") or event_type.rpartition(".")[2] or "")[:32],
            dispute_reason=str(dispute.get("reason_code") or dispute.get("reason_description") or "")[:64],
            dispute_amount_minor=int(dispute.get("amount") or 0),
            event_type=event_type, body_sha256=hashlib.sha256(payload).hexdigest(),
        )
