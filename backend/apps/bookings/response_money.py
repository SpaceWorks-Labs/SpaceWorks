"""What a member still owes for a booking they just made, read from the server's own records.

The success screen used to repeat the client's live quote. This reads the booking's Payment
(confirmed bookings) or its frozen request-time quote (pending bookings), so the screen can
never disagree with what was actually recorded.
"""

from apps.payments.availability import charge_tracking_enabled, online_payments_enabled
from apps.payments.models import Payment


def booking_money(booking):
    """`{"amount_due", "currency", "pay_online"}`; `amount_due` is None when nothing is owed."""
    makerspace = booking.space.makerspace
    none = {"amount_due": None, "currency": None, "pay_online": False}
    if booking.member_id is None or not charge_tracking_enabled(makerspace, "bookings"):
        return none
    payment = Payment.objects.filter(
        makerspace=makerspace, subject_type=Payment.SubjectType.BOOKING, subject_id=booking.pk,
    ).first()
    if payment is not None:
        if payment.status != Payment.Status.PENDING:
            return none
        amount, currency = payment.amount, payment.currency
    else:
        snapshot = booking.pricing_snapshot or {}
        amount, currency = snapshot.get("total"), snapshot.get("currency")
        if not amount or float(amount) <= 0:
            return none
    return {
        "amount_due": str(amount), "currency": (currency or "").lower() or None,
        "pay_online": online_payments_enabled(makerspace, "bookings"),
    }
