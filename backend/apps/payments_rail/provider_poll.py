"""Read-only provider lookups for the gateway poll (lane L5, X18).

Every function here only READS a provider: what happened to a checkout we opened, or to
a refund staff already approved. None creates, approves or cancels anything. Failures
return None so one unreachable provider never stops the sweep.
"""

import logging
from dataclasses import dataclass

from apps.payments.method_labels import razorpay_label, stripe_label

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PolledCapture:
    paid: bool
    capture_id: str = ""
    minor: int = 0
    currency: str = ""
    method_label: str = ""


def _get(value, key):
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


def poll_checkout(payment, source):
    try:
        if payment.provider == payment.Provider.RAZORPAY:
            return _razorpay_checkout(payment, source)
        return _stripe_checkout(payment, source)
    except Exception:  # noqa: BLE001 - provider I/O is best effort by contract
        logger.info("gateway_poll_checkout_failed", extra={"payment_id": payment.pk})
        return None


def _stripe_checkout(payment, source):
    from apps.payments import stripe_client

    if payment.stripe_checkout_session_id:
        options = ({"stripe_account": source.connected_account_id}
                   if source.provider == "connect" and source.connected_account_id else None)
        session = stripe_client.build_client(source).v1.checkout.sessions.retrieve(
            payment.stripe_checkout_session_id, **({"options": options} if options else {}))
        if _get(session, "payment_status") != "paid":
            # A completed session whose debit is still processing already has its intent;
            # the poll's abandonment keeps it so a late success still matches (PAY-REVIEW).
            intent = _get(session, "payment_intent")
            return PolledCapture(False, intent if isinstance(intent, str) else "")
        return PolledCapture(True, _get(session, "payment_intent") or "", int(_get(session, "amount_total") or 0),
                             str(_get(session, "currency") or ""))
    if payment.stripe_payment_intent_id:
        intent = stripe_client.retrieve_payment_intent(source, payment.stripe_payment_intent_id)
        if _get(intent, "status") != "succeeded":
            return PolledCapture(False)
        return PolledCapture(True, payment.stripe_payment_intent_id, int(_get(intent, "amount_received") or 0),
                             str(_get(intent, "currency") or ""), stripe_label(intent))
    return None


def _razorpay_checkout(payment, source):
    from apps.payments.providers import get_provider

    provider = get_provider("razorpay")
    order_id = payment.external_order_id or ""
    if order_id.startswith("order_"):
        items = (provider._request(source, "GET", f"/orders/{order_id}/payments") or {}).get("items") or []
    else:
        link = provider._request(source, "GET", f"/payment_links/{order_id}") or {}
        items = [{"id": row.get("payment_id"), "status": row.get("status"), "amount": row.get("amount")}
                 for row in link.get("payments") or []]
    for item in items:
        if item.get("status") == "captured" and item.get("id"):
            return PolledCapture(True, item["id"], int(item.get("amount") or 0), str(item.get("currency") or ""),
                                 razorpay_label(item))
    return PolledCapture(False)


def find_refund(refund, source):
    """Locate the provider refund our row asked for when the create call's outcome was unknown.

    Returns (external_id, 'succeeded'|'failed'|'pending') or None when the provider has no
    such refund yet or could not say. Matches on the `refund_id` metadata/notes we always send.
    """
    try:
        payment = refund.payment
        wanted = str(refund.pk)
        if refund.provider == "razorpay":
            from apps.payments.providers import get_provider
            rows = (get_provider("razorpay")._request(
                source, "GET", f"/payments/{payment.external_payment_id}/refunds") or {}).get("items") or []
            for row in rows:
                if str((row.get("notes") or {}).get("refund_id", "")) == wanted and row.get("id"):
                    return row["id"], {"processed": "succeeded", "failed": "failed"}.get(row.get("status") or "", "pending")
            return None
        from apps.payments import stripe_client
        options = ({"stripe_account": source.connected_account_id}
                   if source.provider == "connect" and source.connected_account_id else None)
        listing = stripe_client.build_client(source).v1.refunds.list(
            params={"payment_intent": payment.stripe_payment_intent_id, "limit": 100},
            **({"options": options} if options else {}))
        for row in _get(listing, "data") or []:
            if str((_get(row, "metadata") or {}).get("refund_id", "")) == wanted and _get(row, "id"):
                return _get(row, "id"), {"succeeded": "succeeded", "failed": "failed", "canceled": "failed"}.get(
                    _get(row, "status") or "", "pending")
        return None
    except Exception:  # noqa: BLE001 - provider I/O is best effort by contract
        logger.info("gateway_poll_refund_lookup_failed", extra={"refund_id": refund.pk})
        return None


def poll_refund(refund, source):
    """'succeeded' | 'failed' | 'pending', or None when the provider could not say."""
    try:
        if refund.provider == "razorpay":
            from apps.payments.providers import get_provider
            row = get_provider("razorpay")._request(source, "GET", f"/refunds/{refund.external_refund_id}") or {}
            return {"processed": "succeeded", "failed": "failed"}.get(row.get("status") or "", "pending")
        from apps.payments import stripe_client
        options = ({"stripe_account": source.connected_account_id}
                   if source.provider == "connect" and source.connected_account_id else None)
        row = stripe_client.build_client(source).v1.refunds.retrieve(
            refund.external_refund_id, **({"options": options} if options else {}))
        return {"succeeded": "succeeded", "failed": "failed", "canceled": "failed"}.get(
            _get(row, "status") or "", "pending")
    except Exception:  # noqa: BLE001 - provider I/O is best effort by contract
        logger.info("gateway_poll_refund_failed", extra={"refund_id": refund.pk})
        return None
