"""Paid upcoming bookings (rooms and machine time) that would cost less now (#163A).

A confirmed booking that has not started, whose charge is settled, is re-quoted under
the prices just saved -- the same `booking_quote` that priced it, same times, same
member discount rules -- and compared with the quote frozen on its charge. Only a lower
total counts; a rise finds nothing.
"""

from django.utils import timezone

from apps.payments.models import Payment
from apps.payments.price_drop.shares import Affected, by_total, frozen_total, settled_payments


def find_bookings(makerspace, *, space_ids=None):
    from apps.bookings.models import Booking
    from apps.bookings.service_payments import booking_quote

    rows = Booking.objects.filter(space__makerspace=makerspace, status=Booking.Status.CONFIRMED,
                                  starts_at__gt=timezone.now(), member__isnull=False)
    if space_ids is not None:
        rows = rows.filter(space_id__in=list(space_ids))
    rows = list(rows.select_related("space", "space__makerspace", "member").order_by("starts_at", "pk"))
    payments = settled_payments(makerspace, Payment.SubjectType.BOOKING, [row.pk for row in rows])
    found = []
    for booking in rows:
        payment = payments.get(booking.pk)
        if payment is None:
            continue
        before = frozen_total(payment)
        after = booking_quote(booking).total
        result = by_total(payment, f"booking:{booking.pk}", before=before, after=after)
        if result is None:
            continue
        baseline, owed = result
        found.append(Affected(area="bookings", item_type="booking", item_id=booking.pk, label=booking.space.name,
                              payment=payment, before=baseline, after=after, difference=owed,
                              starts_at=booking.starts_at, facts={"booking_id": booking.pk}))
    return found
