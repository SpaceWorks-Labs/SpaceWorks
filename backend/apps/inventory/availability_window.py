"""Read-only time-window availability projection (decision 221b).

The availability owner's answer to "how many units of this product are free during a
future window?" -- used by event planning and the event equipment desk. It writes nothing
and reserves nothing; accept and issue still decide through `reserve_for_request` /
`issue_items` on the stored counters.

Built only from facts the owner already keeps:

* the stored buckets (`available`, `reserved`, `issued`) -- damaged, lost and needs-fix
  units are never counted as lendable;
* open loans' `return_due_at`: units of an issued loan that is due back at or after now and
  no later than the window's start are expected back before the window opens.

Everything else is treated conservatively as committed for the whole window: every
reserved unit (an accepted request or waitlist hold has no return time yet), every unit of
a loan due back after the window starts, every unit of a loan with no due time, and every
unit of an already-overdue loan (it is late, so it is not counted on).
"""
from django.db.models import F, Sum
from django.utils import timezone


def window_availability(products, starts_at, ends_at, *, now=None):
    """`{product_id: {"free", "committed", "back_before_window", "lendable"}}` for the window."""
    from apps.hardware_requests.models import HardwareRequestItem
    products = list(products)
    if not products:
        return {}
    if starts_at is None or ends_at is None or ends_at < starts_at:
        raise ValueError("A window needs a start at or before its end.")
    now = now or timezone.now()
    back = {}
    if starts_at > now:
        rows = (HardwareRequestItem.objects
                .filter(product_id__in=[row.pk for row in products],
                        request__status__in=("issued", "partially_returned"),
                        request__return_due_at__gte=now, request__return_due_at__lte=starts_at)
                .values("product_id")
                .annotate(out=Sum(F("issued_quantity") - F("returned_quantity")
                                  - F("damaged_quantity") - F("missing_quantity"))))
        back = {row["product_id"]: max(0, row["out"] or 0) for row in rows}
    result = {}
    for product in products:
        lendable = product.available_quantity + product.reserved_quantity + product.issued_quantity
        returning = min(product.issued_quantity, back.get(product.pk, 0))
        free = product.available_quantity + returning
        result[product.pk] = {"free": free, "committed": lendable - free,
                              "back_before_window": returning, "lendable": lendable}
    return result
