"""Parity C24: one CSV row per ticket order of an event (behind `events.orders` and `reports.event_exports`).

Amounts are the order's own frozen quote and its payment's real movements, written by `payments.money.money_text`
in the order's currency (nothing is summed across currencies). Test-mode money never joins live money: a Stripe
payment raised with a test key is shown in `test_paid`, not in `paid` or `refunded` (`payments.test_mode`).

Promo codes are never shown (stored as digests); the column says what the code gave.
Authority is the same as the staff order list: the event's registration grant. The export contains the buyer's
name and email, like the registration export, so it is a staff download only and counts against
`report_exports_monthly`.
"""

from django.db.models import Q

from apps.events.models import EventOrder, EventOrderLine
from apps.payments.models import Payment, Refund
from apps.payments.money import money_text
from apps.payments.test_mode import payment_is_test
from .report_types import ReportResult

ORDER_FIELDS = ("order_id", "placed_at", "status", "kind", "buyer_name", "buyer_email", "event_date", "tickets",
                "items", "currency", "subtotal", "discount", "promo", "booking_fees", "extras", "total",
                "paid", "payment_method", "paid_at", "refunded", "refund_pending", "chargeback", "test_paid")
BATCH = 500
SETTLED = (Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE)


def _buyer_name(user):
    return user.display_name or user.get_full_name() or user.username


def _promo(code):
    """The code itself is stored only as a digest, so the report names what it gave."""
    return f"{code.percent_off}% off" if code.percent_off else f"{money_text(code.amount_off)} off"


def _method(payment):
    if payment.status == Payment.Status.PAID_OFFLINE:
        return "In person"
    return " · ".join(part for part in (payment.provider.title(), payment.method_label) if part)


def _row(order, payment):
    live = payment if payment is not None and payment.status in SETTLED and not payment_is_test(payment) else None
    test = payment if payment is not None and payment.status in SETTLED and payment_is_test(payment) else None
    lines = list(order.lines.all())
    refunds = list(payment.refunds.all()) if live is not None else []
    dispute = next(iter(payment.disputes.all()), None) if payment is not None else None
    return {
        "order_id": order.pk, "placed_at": order.created_at, "status": order.status, "kind": order.kind,
        "buyer_name": _buyer_name(order.buyer), "buyer_email": order.buyer.email,
        "event_date": order.event.starts_at if order.event_id else None,
        "tickets": sum(1 for seat in order.seats.all() if seat.status != "void"),
        "items": "; ".join(f"{line.label} × {line.quantity}" for line in lines if line.kind != EventOrderLine.Kind.TYPE_CHANGE),
        "currency": order.currency, "subtotal": money_text(order.subtotal), "discount": money_text(order.discount_total),
        "promo": _promo(order.promo_code) if order.promo_code_id else "",
        "booking_fees": money_text(order.fee_total),
        "extras": money_text(sum((line.line_total for line in lines if line.kind == EventOrderLine.Kind.ADDON), 0)),
        "total": money_text(order.total),
        "paid": money_text(live.amount) if live is not None else "",
        "payment_method": _method(live) if live is not None else "",
        "paid_at": order.paid_at,
        "refunded": money_text(sum((r.amount for r in refunds if r.status == Refund.Status.SUCCEEDED), 0)) if live else "",
        "refund_pending": money_text(sum((r.amount for r in refunds if r.status == Refund.Status.PENDING), 0)) if live else "",
        "chargeback": dispute.status if dispute is not None else "",
        "test_paid": money_text(test.amount) if test is not None else "",
    }


def build_event_orders(makerspace_id, *, subject_kind, subject_id, limit=None, date_range=None):
    orders = (EventOrder.objects.filter(makerspace_id=makerspace_id).filter(
        Q(event_id=subject_id) | Q(kind=EventOrder.Kind.PASS, seats__event_id=subject_id)).distinct())
    if date_range:
        start, end = date_range
        if start:
            orders = orders.filter(created_at__gte=start)
        if end:
            orders = orders.filter(created_at__lt=end)
    orders = orders.order_by("pk")
    if limit is not None:
        orders = orders[:limit]
    ids = list(orders.values_list("pk", flat=True))
    records = []
    for index in range(0, len(ids), BATCH):
        chunk = ids[index:index + BATCH]
        payments = {payment.subject_id: payment for payment in Payment.objects.filter(
            makerspace_id=makerspace_id, subject_type=Payment.SubjectType.EVENT_ORDER, subject_id__in=chunk
        ).prefetch_related("refunds", "disputes")}
        batch = (EventOrder.objects.filter(pk__in=chunk).select_related("buyer", "event", "promo_code")
                 .prefetch_related("lines", "seats").order_by("pk"))
        records.extend(_row(order, payments.get(order.pk)) for order in batch)
    return ReportResult(ORDER_FIELDS, records)
