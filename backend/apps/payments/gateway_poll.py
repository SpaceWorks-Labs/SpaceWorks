"""Gateway poll (lane L5, X18): catch what a missed webhook would have told us.

Every 5 minutes, both schedulers:
* open online attempts -- a pending charge with a live hosted page or native intent --
  are asked of the provider. A capture settles exactly as its webhook would
  (`online_settlement.settle_capture`, so flags and held receipts behave the same). An
  attempt still unpaid a week after it opened is closed and forgotten; the DEBT stays
  pending, it simply no longer has a stale link.
* PENDING provider refunds -- ones a staff member already approved -- are asked for
  their status for 30 days and flagged once when still pending after a day.

Polling never creates, approves or cancels a refund and never cancels a charge. It does
nothing when the payment rail is tombstoned.
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit import services as audit
from apps.audit.models import AuditLog
from apps.payments.models import Payment, Refund

logger = logging.getLogger(__name__)
ABANDON_AFTER = timedelta(days=7)
REFUND_POLL_FOR = timedelta(days=30)
REFUND_FLAG_AFTER = timedelta(days=1)
BATCH = 200


def run_gateway_poll(now=None, *, makerspace_id=None):
    from apps.accounts import rbac
    from apps.makerspaces.models import Makerspace
    from apps.separability.registry import runtime_active
    from apps.tenant_migration.gate_runtime import fanout_tenant_write

    counts = {"checkouts": 0, "refunds": 0, "skipped": 0, "failed": 0}
    if not runtime_active("payments_rail"):
        return {**counts, "rail": "tombstoned"}
    now = now or timezone.now()
    spaces = rbac.scope_for_scheduled_work(Makerspace.objects.all(), field="pk").order_by("pk")
    if makerspace_id is not None:
        spaces = spaces.filter(pk=makerspace_id)
    for space in spaces.iterator():
        try:
            with fanout_tenant_write(space.pk, operation="gateway_poll", counts=counts) as allowed:
                if not allowed:
                    continue
                counts["checkouts"] += sum(1 for row in _open_attempts(space) if _poll_attempt(row, now))
                counts["refunds"] += sum(1 for row in _pending_refunds(space, now) if _poll_refund(row, now))
        except Exception as exc:  # noqa: BLE001 - one tenant never stops the sweep
            counts["failed"] += 1
            logger.error("gateway_poll_tenant_failed", extra={"makerspace_id": space.pk,
                                                              "failure_type": type(exc).__name__})
    return counts


def _open_attempts(space):
    live = (Q(stripe_checkout_session_id__isnull=False) | Q(external_order_id__isnull=False)
            | Q(stripe_payment_intent_id__isnull=False))
    return (Payment.objects.filter(makerspace=space, status=Payment.Status.PENDING,
                                   stripe_checkout_session_expired_at__isnull=True)
            .exclude(provider=Payment.Provider.UNCLAIMED).filter(live).select_related("makerspace")
            .order_by("pk")[:BATCH])


def _opened_at(payment):
    stamp = AuditLog.objects.filter(makerspace_id=payment.makerspace_id, action="payment.checkout_created",
                                    target_type="payments.payment", target_id=str(payment.pk)).order_by(
        "-created_at").values_list("created_at", flat=True).first()
    return stamp or payment.created_at


def _poll_attempt(payment, now):
    from apps.payments.resolution import source_for_payment
    from apps.payments_rail.provider_poll import poll_checkout

    source = source_for_payment(payment)
    if source is None:
        return False
    result = poll_checkout(payment, source)
    if result is not None and result.paid:
        return _settle(payment.pk, result)
    if result is not None and now - _opened_at(payment) > ABANDON_AFTER:
        return _abandon(payment.pk)
    return False


def _settle(payment_id, result):
    from apps.payments.online_settlement import settle_capture
    from apps.payments.services_refund_webhooks import _record_once

    with transaction.atomic():
        payment = Payment.objects.select_for_update(of=("self",)).select_related("makerspace").get(pk=payment_id)
        if payment.status != Payment.Status.PENDING:
            return False
        if not _record_once(payment.makerspace, f"poll:{payment.pk}:{result.capture_id}", payment.provider):
            return False
        settle_capture(payment, provider=payment.provider, capture_id=result.capture_id,
                       event_id=f"poll:{payment.pk}", polled=True,
                       minor=result.minor, currency=result.currency, method_label=result.method_label)
    return True


def _abandon(payment_id):
    from apps.payments.checkout_expiry import forget_closed_checkout
    from apps.payments.reconciliation_rail import _expire_checkout_best_effort

    with transaction.atomic():
        payment = Payment.objects.select_for_update(of=("self",)).select_related("makerspace").get(pk=payment_id)
        if payment.status != Payment.Status.PENDING or payment.stripe_checkout_session_expired_at:
            return False
        _expire_checkout_best_effort(payment)
        fields = forget_closed_checkout(payment)
        payment.save(update_fields=[*fields, "updated_at"])
        audit.record(None, "payment.checkout_abandoned", makerspace=payment.makerspace, target=payment,
                     meta={"provider": payment.provider})
    return True


def _pending_refunds(space, now):
    return (Refund.objects.filter(payment__makerspace=space, status=Refund.Status.PENDING, provider__in=("stripe", "razorpay"),
                                  external_refund_id__isnull=False, created_at__gte=now - REFUND_POLL_FOR)
            .select_related("payment__makerspace").order_by("pk")[:BATCH])


def _poll_refund(refund, now):
    from apps.payments.resolution import source_for_payment
    from apps.payments.services_refunds import settle_refund
    from apps.payments_rail.provider_poll import poll_refund

    source = source_for_payment(refund.payment)
    status = poll_refund(refund, source) if source is not None else None
    if status in (Refund.Status.SUCCEEDED, Refund.Status.FAILED):
        settle_refund(refund, external_refund_id=refund.external_refund_id, status=status, actor=None)
        return True
    if now - refund.created_at > REFUND_FLAG_AFTER and not AuditLog.objects.filter(
            makerspace_id=refund.payment.makerspace_id, action="payment.refund_pending_flagged",
            target_type="payments.payment", target_id=str(refund.payment_id), meta__refund_id=refund.pk).exists():
        audit.record(None, "payment.refund_pending_flagged", makerspace=refund.payment.makerspace,
                     target=refund.payment, meta={"refund_id": refund.pk, "provider": refund.provider})
    return False
