"""Money owed back on orders (release 2 L6, #59/#60/#94). Nothing here moves money.

Every amount becomes an append-only `EventOrderDue` linked to a staff-approved
`RefundCase` on the order's one `Payment` (`payments.services_refund_partial`). Only a
staff approval turns a case into a refund row on the ledger.

* The space cancels the event: every paid order of it is owed its full remaining balance,
  booking fee included (decision 60). Pending orders are voided and their holds released.
* One seat is cancelled (by the attendee or staff): that seat's share of the ticket line,
  under the event's refund policy (its own override, else the space's), less the policy
  fee. The booking fee is not refunded for a single seat. Its place is freed.
* Series passes keep their own rule (`passes.occurrence_cancelled`); skipping one
  occurrence of a pass owes nothing.
"""

import logging
from decimal import ROUND_DOWN, Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit.services import record
from apps.payments.money import quantize_money

from .models import EventOrder, EventOrderDue, EventOrderSeat

logger = logging.getLogger(__name__)


def open_order_due(order, *, amount, kind, actor, reason_code, seat=None, event=None, snapshot=None):
    from apps.payments.services_refund_partial import add_due_share
    from .orders_settlement import order_payment
    payment = order_payment(order)
    if payment is None or amount <= 0:
        return None
    case = add_due_share(payment, amount=amount, reason_code=reason_code, actor=actor,
                         snapshot={"order_id": order.pk, "seat_id": getattr(seat, "pk", None), **(snapshot or {})})
    if case is None:
        return None
    due = EventOrderDue.objects.create(makerspace=order.makerspace, order=order, kind=kind, seat=seat,
                                       event=event or order.event, amount=min(Decimal(amount), case.due_amount),
                                       refund_case=case, created_by=actor)
    record(actor, "event.order_due_opened", makerspace=order.makerspace, target=order,
           meta={"order_id": order.pk, "due_id": due.pk, "case_id": case.pk, "kind": kind, "amount": str(due.amount)})
    return due


def seat_share(seat):
    """What one admission of a ticket line cost, after its discounts (fee excluded)."""
    line = seat.line
    seats = max(line.quantity * max(line.seats_per_unit, 1), 1)
    return quantize_money(line.line_total / seats, line.order.currency, ROUND_DOWN)


def policy_share(order, share, *, cancelled_at):
    """`share` under the event's refund policy band, less the policy fee."""
    from apps.payments.refund_policy import area_policy
    from .orders_settlement import order_payment
    payment = order_payment(order)
    policy = area_policy(payment, "events") if payment is not None else None
    if policy is None or order.event is None:
        return Decimal("0"), {"rule": "no_policy"}
    minutes = int((order.event.starts_at - cancelled_at).total_seconds() // 60)
    if minutes >= policy.full_before_minutes:
        band, gross = "full", share
    elif minutes >= policy.partial_before_minutes:
        band, gross = "partial", share * Decimal(policy.partial_percent) / 100
    else:
        band, gross = "none", Decimal("0")
    due = quantize_money(max(gross - Decimal(policy.cancellation_fee), Decimal("0")), order.currency, ROUND_DOWN)
    return due, {"rule": "policy", "band": band, "minutes_before_start": minutes, "share": str(share)}


def seat_cancelled(registration, *, actor):
    seat = EventOrderSeat.objects.select_for_update(of=("self",)).select_related("order", "line").filter(
        registration=registration).first()
    if seat is None or seat.status == EventOrderSeat.Status.VOID:
        return None
    seat.status, seat.voided_at = EventOrderSeat.Status.VOID, timezone.now()
    seat.save(update_fields=["status", "voided_at"])
    order = seat.order
    record(actor, "event.order_seat_cancelled", makerspace=order.makerspace, target=order,
           meta={"order_id": order.pk, "seat_id": seat.pk, "registration_id": registration.pk})
    if order.status != EventOrder.Status.PAID or seat.line.kind != "ticket":
        return None
    due, facts = policy_share(order, seat_share(seat), cancelled_at=registration.cancelled_at or timezone.now())
    return open_order_due(order, amount=due, kind=EventOrderDue.Kind.SEAT_CANCELLED, actor=actor,
                          reason_code="registration_cancelled", seat=seat, snapshot=facts)


def event_cancelled(event, *, actor):
    from apps.payments.reconciliation import cancel_pending
    from apps.payments.refund_policy import refundable_balance
    from .orders_settlement import order_payment, release_hold
    for order in EventOrder.objects.select_for_update().filter(event=event).order_by("pk"):
        if order.status == EventOrder.Status.PENDING:
            order.status, order.closed_at = EventOrder.Status.CANCELLED, timezone.now()
            order.save(update_fields=["status", "closed_at"])
            release_hold(getattr(order, "hold", None), "cancelled")
            cancel_pending(makerspace=order.makerspace, subject_type="event_order", subject_id=order.pk, actor=actor)
            record(actor, "event.order_cancelled", makerspace=order.makerspace, target=order,
                   meta={"order_id": order.pk, "reason": "event_cancelled"})
        elif order.status == EventOrder.Status.PAID:
            payment = order_payment(order)
            if payment is not None and payment.status in ("paid_online", "paid_offline"):
                open_order_due(order, amount=refundable_balance(payment), kind=EventOrderDue.Kind.EVENT_CANCELLED,
                               actor=actor, reason_code="event_cancelled")
    pass_occurrence_cancelled(event, actor=actor)


def pass_occurrence_cancelled(event, *, actor):
    """Each pass holder of a cancelled occurrence is owed the pass type's partial amount."""
    from .notices_r2_l6 import order_notice
    seats = (EventOrderSeat.objects.select_for_update(of=("self",)).select_related("order", "line__pass_type")
             .filter(event=event, order__kind=EventOrder.Kind.PASS, order__status=EventOrder.Status.PAID)
             .exclude(status=EventOrderSeat.Status.VOID).order_by("pk"))
    for seat in seats:
        seat.status, seat.voided_at = EventOrderSeat.Status.VOID, timezone.now()
        seat.save(update_fields=["status", "voided_at"])
        amount = Decimal(seat.line.pass_type.occurrence_refund_amount or 0)
        due = open_order_due(seat.order, amount=amount, kind=EventOrderDue.Kind.OCCURRENCE_CANCELLED, actor=actor,
                             reason_code="pass_occurrence_cancelled", seat=seat, event=event) if amount > 0 else None
        record(actor, "event.pass_occurrence_cancelled", makerspace=seat.makerspace, target=seat.order,
               meta={"order_id": seat.order_id, "event_id": event.pk, "due_id": getattr(due, "pk", None)})
        order_notice(seat.order, "pass_occurrence_cancelled", event=event, due=due)


def after_event_charges(event, actor, *, registration_ids=None):
    """Post-commit companion of `services_lifecycle._cancel_open_charges_after_commit` (L6 hook)."""
    from .services_write_boundary import event_write

    @event_write
    def run(event, *, actor):
        if registration_ids is None:
            event_cancelled(event, actor=actor)
            return
        from .models import EventRegistration
        for registration in EventRegistration.objects.filter(pk__in=registration_ids, order_seat__isnull=False):
            seat_cancelled(registration, actor=actor)

    def safely():
        try:
            run(event, actor=actor)
        except Exception:
            logger.error("event_order_refund_hook_failed", extra={"event_id": event.pk})

    transaction.on_commit(safely)
