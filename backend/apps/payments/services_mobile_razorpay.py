"""Lookup-first native Orders, called under the existing credential/Payment locks."""

import logging

from apps.audit import services as audit
from apps.payments.models import Payment
from apps.payments.money import AmountNotCapturable, to_provider_minor_units
from apps.payments.providers import PaymentsUnavailable, get_provider
from apps.payments.providers.razorpay import RazorpayRequestError
from apps.payments.subjects import resolve_subject_labels, subject_label

logger = logging.getLogger(__name__)


def create_mobile_order(payment, source, *, actor):
    provider = get_provider(source.vendor)
    receipt = f"sw-pay-{payment.pk}"
    if len(receipt) > 40:
        raise PaymentsUnavailable("The payment receipt exceeds Razorpay's limit.")
    try:
        amount = to_provider_minor_units(payment.amount, payment.currency)
    except AmountNotCapturable as exc:
        raise PaymentsUnavailable("The charge amount is finer than Razorpay can capture.") from exc
    currency = payment.currency.upper()
    notes = {"payment_id": str(payment.pk), "makerspace_id": str(payment.makerspace_id)}

    def validate(order):
        if not (
            isinstance(order, dict)
            and isinstance(order.get("id"), str) and order["id"]
            and order.get("receipt") == receipt
            and isinstance(order.get("notes"), dict)
            and order["notes"].get("payment_id") == notes["payment_id"]
            and order["notes"].get("makerspace_id") == notes["makerspace_id"]
            and type(order.get("amount")) is int and order["amount"] == amount
            and order.get("currency") == currency
            and order.get("status") in {"created", "attempted"}
            and (not payment.external_order_id or order["id"] == payment.external_order_id)
        ):
            logger.warning("razorpay_mobile_order_mismatch", extra={"payment_id": payment.pk})
            raise PaymentsUnavailable("Razorpay returned an incompatible order.")
        return order

    def lookup():
        orders = provider.fetch_orders_by_receipt(source, receipt)
        if not orders:
            return None
        # Receipt filtering is substring-based; an exact hit may accompany partial
        # hits. Partial-only results and duplicate exact hits fail closed.
        exact = [order for order in orders if isinstance(order, dict) and order.get("receipt") == receipt]
        if len(exact) != 1:
            logger.warning("razorpay_mobile_order_ambiguous", extra={"payment_id": payment.pk})
            raise PaymentsUnavailable("Razorpay returned ambiguous orders.")
        return validate(exact[0])

    if payment.external_order_id:
        order = validate(provider.fetch_order(source, payment.external_order_id))
    else:
        order = lookup()
        if order is None:
            try:
                order = validate(provider.create_order(
                    source, amount_minor=amount, currency=currency, receipt=receipt, notes=notes,
                ))
            except RazorpayRequestError as exc:
                if not exc.is_duplicate_receipt:
                    raise
                order = lookup()
                if order is None:
                    logger.warning("razorpay_mobile_order_recovery_missing", extra={"payment_id": payment.pk})
                    raise PaymentsUnavailable("Razorpay order recovery failed.") from None

    if not payment.external_order_id or payment.online_rail is None:
        payment.external_order_id = order["id"]
        payment.online_rail = Payment.OnlineRail.NATIVE_PAYMENT_INTENT
        payment.save(update_fields=["external_order_id", "online_rail", "updated_at"])
        audit.record(
            actor, "payment.mobile_order_created", makerspace=payment.makerspace,
            target=payment, meta={"provider": "razorpay", "order_id": order["id"]},
        )
    return {
        "vendor": "razorpay", "payment_id": payment.pk,
        "key_id": source.publishable_key, "order_id": order["id"],
        "amount_minor": amount, "currency": currency, "name": payment.makerspace.name,
        "description": subject_label(payment, resolve_subject_labels([payment])),
    }
