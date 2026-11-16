"""Per-currency charge totals and settlement facts for the linked event finance view (decision 216 item 8).

Read-only. Every total is grouped by currency and never summed across currencies. A charge
is one `Payment`; its settlement fact is the ledger's own: `paid_online` (a provider capture)
or `paid_offline` with its effective `ManualSettlement` receipt (the chain head nothing amends).
Refunds count only money that actually went back (succeeded, not superseded).
"""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Q, Sum

ZERO = Decimal("0.00")
STATUS_COLUMNS = {"pending": "owed", "paid_online": "paid_online", "paid_offline": "paid_offline", "waived": "waived"}


def _blank(currency):
    return {"currency": currency, "charges": 0, "owed": ZERO, "paid_online": ZERO, "paid_offline": ZERO,
            "offline_receipts": 0, "offline_by_method": {}, "waived": ZERO, "refunded": ZERO}


def charge_totals(payments):
    """`[{currency, charges, owed, paid_online, paid_offline, offline_receipts, offline_by_method, waived,
    refunded}]` for a `Payment` queryset, one entry per currency, sorted."""
    from apps.payments.models import ManualSettlement, Refund

    groups = {}

    def group(currency):
        currency = (currency or "").lower()
        return groups.setdefault(currency, _blank(currency))

    for row in payments.order_by().values("currency", "status").annotate(n=Count("pk"), total=Sum("amount")):
        entry = group(row["currency"])
        entry["charges"] += row["n"]
        column = STATUS_COLUMNS.get(row["status"])
        if column:
            entry[column] += row["total"] or ZERO
    receipts = ManualSettlement.objects.filter(payment__in=payments.values("pk"), amended_by__isnull=True,
                                               payment__status="paid_offline")
    by_method = defaultdict(lambda: ZERO)
    for row in receipts.order_by().values("currency", "method").annotate(n=Count("pk"), total=Sum("amount")):
        entry = group(row["currency"])
        entry["offline_receipts"] += row["n"]
        by_method[(entry["currency"], row["method"])] += row["total"] or ZERO
    for (currency, method), total in by_method.items():
        groups[currency]["offline_by_method"][method] = total
    refunds = Refund.objects.filter(payment__in=payments.values("pk"), status=Refund.Status.SUCCEEDED,
                                    amended_by__isnull=True)
    for row in refunds.order_by().values("payment__currency").annotate(total=Sum("amount")):
        group(row["payment__currency"])["refunded"] += row["total"] or ZERO
    return [groups[key] for key in sorted(groups)]


def event_charge_payments(space, event):
    """The event's own charges (registrations, orders, deposits, entry and team fees) -- never the venue."""
    from apps.events.models import EventOrder, EventRegistration, HackathonSubmission, HackathonTeam
    from apps.payments.models import Payment

    registrations = EventRegistration.objects.filter(event=event).values("pk")
    owned = (Q(subject_type="event_registration", subject_id__in=registrations)
             | Q(subject_type="event_deposit", subject_id__in=registrations)
             | Q(subject_type="event_order", subject_id__in=EventOrder.objects.filter(event=event).values("pk"))
             | Q(subject_type="submission_fee",
                 subject_id__in=HackathonSubmission.objects.filter(event=event).values("pk"))
             | Q(subject_type="team_registration",
                 subject_id__in=HackathonTeam.objects.filter(event=event).values("pk")))
    return Payment.objects.filter(makerspace=space).filter(owned)


def venue_fee_payments(space, fee):
    from apps.payments.models import Payment

    return Payment.objects.filter(makerspace=space, subject_type="event_venue_fee", subject_id=fee.pk)


def booking_chain_ids(space, booking_id, limit=50):
    """The originally linked booking then each booking-owned replacement, oldest first (same tenant only)."""
    from apps.bookings.models import Booking

    chain = []
    current = Booking.objects.filter(pk=booking_id, space__makerspace=space).values_list("pk", flat=True).first()
    while current is not None and len(chain) < limit:
        chain.append(current)
        current = Booking.objects.filter(replaces_id=current, space__makerspace=space).values_list(
            "pk", flat=True).first()
    return chain


def booking_payments(space, booking_ids):
    from apps.payments.models import Payment

    return Payment.objects.filter(makerspace=space, subject_type="booking", subject_id__in=list(booking_ids))


def minor_amount(value, currency):
    from apps.payments.money import minor_unit_exponent

    return Decimal(value or 0).scaleb(-minor_unit_exponent(currency))
