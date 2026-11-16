"""Refund a paid-online charge through the provider seam.

Three steps, and the split is deliberate:

1. Under the Payment row lock: validate and write a PENDING `Refund` row. Pending rows
   count against the refundable balance, so two staff refunding at once cannot both pass.
2. Outside any row lock: call the provider. A webhook for the same payment must not queue
   behind vendor I/O, and a lock held across a network call is how deadlocks start.
3. Settle the row from the synchronous answer. Async providers leave it PENDING and the
   webhook (`services_refund_webhooks`) finishes the job idempotently.

The Payment row itself is never touched: it is terminal and the database forbids it.
"""

from django.utils.translation import gettext
import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.payments.exceptions_refunds import RefundNotAllowed, RefundProviderFailure
from apps.payments.models import Payment, Refund
from apps.payments.money import AmountNotCapturable, quantize_money, to_provider_minor_units
from apps.payments.providers import PaymentsUnavailable, RefundRequest, get_provider
from apps.payments.resolution import source_for_payment

logger = logging.getLogger(__name__)


def refund_payment(payment, *, amount, reason, actor):
    refund = _open_refund(payment, amount=amount, reason=reason, actor=actor)
    refund, failed = dispatch_refund(refund, actor=actor)
    if failed:
        raise RefundProviderFailure(refund)
    return refund


def dispatch_refund(refund, *, actor):
    """Steps 2 and 3: provider I/O outside every lock, then settle. Returns (refund, failed)."""
    result, failed = _send_to_provider(refund)
    if failed is None:
        # Audit 0.12.0 C-1: a timeout, dropped connection or provider 5xx says nothing about
        # whether the money went back. Marking the row FAILED freed its share of the balance,
        # so a retry raised a SECOND provider refund (new idempotency key) for the same money.
        # It stays PENDING and reserved; the provider's webhook binds and settles it.
        refund = Refund.objects.select_related("payment__makerspace").get(pk=refund.pk)
        audit.record(actor, "payment.refund_requested", makerspace=refund.payment.makerspace,
                     target=refund.payment, meta={"payment_id": refund.payment_id, "refund_id": refund.pk,
                                                  "amount": str(refund.amount), "outcome_unknown": True})
        return refund, False
    if failed:
        settle_refund(refund, external_refund_id=None, status=Refund.Status.FAILED, actor=actor)
    else:
        settle_refund(refund, external_refund_id=result.refund_id, status=result.status, actor=actor)
    refund.refresh_from_db()
    return refund, failed


def _open_refund(payment, *, amount, reason, actor):
    try:
        raw, amount = Decimal(amount), quantize_money(amount, payment.currency)
    except (InvalidOperation, TypeError, ValueError):
        raise RefundNotAllowed(gettext("Refund amount is invalid."), "refund_amount_invalid")
    if raw != amount:
        # Finer than the charge precision (a yen's decimals, a KWD fils): refuse, never round a refund.
        raise RefundNotAllowed(gettext("Refund amount is invalid for this currency."), "refund_amount_invalid")
    if amount <= 0:
        raise RefundNotAllowed(gettext("Refund amount must be positive."), "refund_amount_invalid")
    with transaction.atomic():
        locked = Payment.objects.select_for_update(of=("self",)).select_related("makerspace").get(pk=payment.pk)
        return open_refund_locked(locked, amount=amount, reason=reason, actor=actor)


def open_refund_locked(locked, *, amount, reason, actor):
    """Step 1 for a caller that already holds the Payment row lock.

    `amount` is a validated two-place Decimal. Shared by the direct staff refund and a
    refund-case approval, so both apply the same status and balance rules.
    """
    if locked.status != Payment.Status.PAID_ONLINE:
        # Offline charges are refunded through the core manual receipt service;
        # a provider cannot send back money it did not collect.
        raise RefundNotAllowed(
            gettext("Only payments settled online can be refunded through the provider."),
            "refund_not_online",
        )
    from apps.payments.refund_policy import precision_ok
    if not precision_ok(amount, locked.currency):
        # Audit 0.12.0 C-2: JPY 0.50 passed the two-place check and was sent as 1 yen.
        raise RefundNotAllowed(gettext("Refund amount is invalid for this currency."), "refund_amount_invalid")
    if Refund.counted_total(locked) + amount > locked.amount:
        raise RefundNotAllowed(
            gettext("Refund exceeds the refundable balance."), "refund_exceeds_balance"
        )
    refund = Refund.objects.create(
        payment=locked,
        amount=amount,
        currency=locked.currency,
        provider=locked.provider,
        reason=(reason or "")[:255],
        created_by=actor,
    )
    from apps.payments.services_refund_cases import void_exhausted_cases
    void_exhausted_cases(locked, actor=actor)
    return refund


def _minor(refund):
    try:
        return to_provider_minor_units(refund.amount, refund.currency)
    except AmountNotCapturable as exc:
        raise PaymentsUnavailable("The refund amount is finer than the provider can move.") from exc


def _send_to_provider(refund):
    payment = refund.payment
    try:
        source = source_for_payment(payment)
        if source is None:
            raise PaymentsUnavailable("The payment's provider credentials are no longer configured.")
        provider_payment_id = (
            payment.stripe_payment_intent_id
            if payment.provider == Payment.Provider.STRIPE
            else payment.external_payment_id
        )
        result = get_provider(payment.provider).create_refund(
            source,
            RefundRequest(
                payment_id=provider_payment_id or "",
                # Integer minor units; a float here reconciles as a real money difference.
                amount_minor=_minor(refund),
                currency=refund.currency,
                reference=str(refund.pk),
                idempotency_key=f"payment-refund-{refund.pk}",
                metadata={"refund_id": refund.pk, "payment_id": payment.pk},
                # Connect uses direct charges: the platform fee was taken from this
                # charge, so it is returned pro rata. There is no transfer to reverse.
                refund_application_fee=(
                    payment.stripe_provider == Payment.StripeProvider.CONNECT
                    and (payment.stripe_application_fee_amount or 0) > 0
                ),
            ),
        )
        return result, False
    except PaymentsUnavailable as exc:
        if outcome_unknown(exc):
            logger.warning("payment_refund_outcome_unknown", extra={"refund_id": refund.pk})
            return None, None
        logger.warning("payment_refund_provider_failed", extra={"refund_id": refund.pk})
        return None, True
    except Exception as exc:
        if outcome_unknown(exc):
            logger.warning("payment_refund_outcome_unknown", extra={"refund_id": refund.pk})
            return None, None
        logger.exception("payment_refund_provider_error", extra={"refund_id": refund.pk})
        return None, True


def outcome_unknown(exc):
    """True when the provider may have acted: a network failure, timeout, 5xx or unreadable 2xx anywhere in the chain.

    A 4xx is a definitive refusal, and a local precondition (no credentials, no captured id)
    never reached the provider, so both stay FAILED and the balance is free to retry.
    """
    seen, current = set(), exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if getattr(current, "outcome_unknown", False) is True:
            return True
        status = getattr(current, "http_status", None)
        if status is None:
            status = getattr(current, "status", None)
        if isinstance(status, int) and not isinstance(status, bool):
            # A 2xx carried by an exception is an answer we could not read (Stripe's SDK raises
            # APIError on an unparseable 200): the provider accepted, so the outcome is unknown.
            if 200 <= status < 300:
                return True
            if 400 <= status < 500:
                return False
            if status >= 500:
                return True
        if isinstance(current, (TimeoutError, ConnectionError, OSError)) or type(current).__name__ in (
                "APIConnectionError", "Timeout", "ReadTimeout", "ConnectTimeout"):
            return True
        current = current.__cause__ or current.__context__
    return False


def settle_refund(refund, *, external_refund_id, status, actor):
    """Move a PENDING refund to its final state exactly once; later calls are no-ops.

    Shared by the synchronous path and the webhook path so both write the same audit
    entries with the same meta, whichever one gets there first.
    """
    from apps.payments.services_refund_cases import approved_cases_for_refund, mark_approval_failed
    with transaction.atomic():
        Payment.objects.select_for_update().get(pk=refund.payment_id)
        # Lock order Payment -> RefundCase -> Refund, as everywhere a case is touched.
        cases = approved_cases_for_refund(refund.pk)
        locked = Refund.objects.select_for_update(of=("self",)).select_related("payment__makerspace").get(pk=refund.pk)
        fields = []
        if external_refund_id and not locked.external_refund_id:
            locked.external_refund_id = external_refund_id
            fields.append("external_refund_id")
        if locked.status != Refund.Status.PENDING:
            if fields:
                locked.save(update_fields=fields)
            return locked
        if status == Refund.Status.PENDING:
            if fields:
                locked.save(update_fields=fields)
            audit.record(
                actor, "payment.refund_requested",
                makerspace=locked.payment.makerspace, target=locked.payment,
                meta={"payment_id": locked.payment_id, "refund_id": locked.pk, "amount": str(locked.amount)},
            )
            return locked
        locked.status = status
        locked.settled_at = timezone.now()
        locked.save(update_fields=[*fields, "status", "settled_at"])
        action = "payment.refunded" if status == Refund.Status.SUCCEEDED else "payment.refund_failed"
        audit.record(
            actor, action,
            makerspace=locked.payment.makerspace, target=locked.payment,
            meta={"payment_id": locked.payment_id, "refund_id": locked.pk, "amount": str(locked.amount)},
        )
        if status == Refund.Status.SUCCEEDED:
            from apps.payments.documents import issue_credit_note
            issue_credit_note(locked, actor=actor)
            from apps.payments.notifications import notify_payment
            notify_payment(locked.payment, "refund_issued", refund=locked)
        else:
            # Synchronous refusal or a later webhook: the approved case goes back to
            # staff for a retry or a decline (R2), whichever path reports the failure.
            mark_approval_failed(cases, locked, actor=actor)
        return locked
