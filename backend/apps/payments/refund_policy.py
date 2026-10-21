"""What a cancellation entitles a member to get back. Pure arithmetic over one charge.

Computing a figure is all this does: it never opens a case, writes a row or moves
money. The order is fixed so two staff screens can never disagree:

1. the refundable balance (amount minus pending and succeeded refunds) caps everything;
2. a space-cancelled event is owed in full (owner decision 60);
3. otherwise the area's `RefundPolicy` picks a band -- for events and bookings from how
   long before the start the cancellation happened, for a membership term from how far
   into the term it was (`refund_policy_membership`, decision 68) -- then keeps the fee;
4. money already refunded outside a case is subtracted (R7);
5. the result is floored at zero and rounded DOWN to the stored precision, so a policy
   can never owe a fraction of a minor unit more than the space agreed to.

Amounts are stored at two decimal places, so a three-decimal currency rounds to two and
a zero-decimal one to whole units: min(ISO exponent, 2) (R10).
"""

from decimal import ROUND_DOWN, Decimal

from django.utils import timezone

from apps.payments.availability import SUBJECT_DOMAINS
from apps.payments.models import Payment, Refund
from apps.payments.models_refund_cases import RefundCase, RefundPolicy
from apps.payments.money import minor_unit_exponent

ZERO = Decimal("0.00")
POLICY_AREAS = frozenset(RefundPolicy.Area.values)


def round_down(amount, currency):
    places = min(minor_unit_exponent(currency), 2)
    return Decimal(amount).quantize(Decimal(1).scaleb(-places), rounding=ROUND_DOWN)


def precision_ok(amount, currency):
    """Whether `amount` is expressible in the currency at the stored precision."""
    return round_down(amount, currency) == Decimal(amount)


def refundable_balance(payment):
    return max(payment.amount - Refund.counted_total(payment), ZERO)


def succeeded_total(payment):
    rows = Refund.objects.filter(payment=payment, status=Refund.Status.SUCCEEDED, amended_by__isnull=True)
    return sum((row.amount for row in rows), ZERO)


def area_for(payment):
    return SUBJECT_DOMAINS.get(payment.subject_type, "")


def reference_time(payment):
    """When the thing being paid for starts. None means no window applies."""
    if payment.subject_type == Payment.SubjectType.EVENT_REGISTRATION:
        from apps.events.models import EventRegistration
        row = EventRegistration.objects.filter(pk=payment.subject_id).values("event__starts_at").first()
        return row["event__starts_at"] if row else None
    if payment.subject_type == Payment.SubjectType.BOOKING:
        from apps.bookings.models import Booking
        return Booking.objects.filter(pk=payment.subject_id).values_list("starts_at", flat=True).first()
    return None


def _space_currency(makerspace):
    from apps.payments.models import MakerspacePaymentSettings
    return MakerspacePaymentSettings.for_makerspace(makerspace).default_currency


def assess(payment, *, reason_code, cancelled_at=None):
    """Return `(due, snapshot)` for a cancellation of `payment`'s subject."""
    cancelled_at = cancelled_at or timezone.now()
    balance = refundable_balance(payment)
    refunded = payment.amount - balance
    snapshot = {"assessed_at": cancelled_at.isoformat(), "currency": payment.currency,
                "paid": str(payment.amount), "already_refunded": str(refunded), "balance": str(balance)}
    if balance <= 0:
        return ZERO, {**snapshot, "rule": "nothing_left"}
    if reason_code == RefundCase.ReasonCode.EVENT_CANCELLED:
        return round_down(balance, payment.currency), {**snapshot, "rule": "event_cancelled_full"}
    area = area_for(payment)
    if area not in POLICY_AREAS:
        return ZERO, {**snapshot, "rule": "no_policy_area"}
    if area == RefundPolicy.Area.MEMBERSHIP:
        found = _membership(payment, cancelled_at)
        if found is None:
            return ZERO, {**snapshot, "rule": "no_reference_time"}
        policy, band, gross, facts = found
        if policy is None:
            return ZERO, {**snapshot, "rule": "no_policy"}
    else:
        policy = RefundPolicy.objects.filter(makerspace_id=payment.makerspace_id, area=area,
                                             plan__isnull=True).first()
        starts_at = reference_time(payment)
        if policy is None or starts_at is None:
            return ZERO, {**snapshot, "rule": "no_policy" if policy is None else "no_reference_time"}
        band, gross, facts = _timed_band(payment, policy, starts_at, cancelled_at)
    fee_currency = _space_currency(payment.makerspace)
    # The fee is written in the space's currency; a charge in another one keeps no fee
    # rather than subtracting a figure in the wrong unit.
    fee = policy.cancellation_fee if fee_currency == payment.currency else ZERO
    due = max(gross - fee - refunded, ZERO)
    due = round_down(min(due, balance), payment.currency)
    return due, {
        **snapshot, **facts, "rule": "policy", "area": area, "band": band,
        "cancellation_fee": str(policy.cancellation_fee), "fee_currency": fee_currency,
        "fee_applied": str(fee), "due": str(due),
    }


def _timed_band(payment, policy, starts_at, cancelled_at):
    """Events and bookings: how long before the start the cancellation happened."""
    minutes = int((starts_at - cancelled_at).total_seconds() // 60)
    if minutes >= policy.full_before_minutes:
        band, gross = "full", payment.amount
    elif minutes >= policy.partial_before_minutes:
        band, gross = "partial", payment.amount * Decimal(policy.partial_percent) / Decimal(100)
    else:
        band, gross = "none", ZERO
    return band, gross, {"minutes_before_start": minutes, "starts_at": starts_at.isoformat(),
                         "full_before_minutes": policy.full_before_minutes,
                         "partial_before_minutes": policy.partial_before_minutes,
                         "partial_percent": policy.partial_percent}


def _membership(payment, cancelled_at):
    """`(policy, band, gross, facts)` for a term charge; None for dues/admission (request-only)."""
    from apps.payments.refund_policy_membership import covered_term, membership_band, membership_policy
    if payment.subject_type != Payment.SubjectType.MEMBERSHIP_TERM:
        return None
    policy = membership_policy(payment, covered_term(payment))
    if policy is None:
        return None, None, None, None
    band, gross, facts = membership_band(payment, policy, cancelled_at)
    return policy, band, gross, facts
