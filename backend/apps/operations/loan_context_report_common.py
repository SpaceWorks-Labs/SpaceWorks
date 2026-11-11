"""Shared physical-loan cohort for linked operational reports."""
from decimal import Decimal

from apps.hardware_requests.models import HardwareRequest
from .reports_ab_common import calendar_range
from .reports_common import apply_range

OUTSTANDING = (HardwareRequest.Status.ISSUED, HardwareRequest.Status.PARTIALLY_RETURNED)
CLOSED = (HardwareRequest.Status.RETURNED, HardwareRequest.Status.CLOSED_WITH_ISSUE)
METRIC_FIELDS = (
    "issued_units", "returned_units", "damaged_units", "missing_units",
    "overdue_count", "loan_hours",
)


def issued_cohort(rows, space, date_range):
    rows = rows.filter(issued_at__isnull=False, status__in=(*OUTSTANDING, *CLOSED))
    return apply_range(rows, "issued_at", calendar_range(date_range, space))


def loan_metrics(request, now):
    """One canonical request's physical measures, read from the workflow's own counters.

    Quantities are summed over the request's items here, once per request, so a
    caller grouping requests can never multiply them by an item or context join.
    The loss estimate uses the product's current per-count unit cost; a missing
    unit that is unpriced, or priced in a second currency, makes it unknown.
    """
    items = list(request.items.all())
    metrics = {field: sum(getattr(item, field.replace("_units", "_quantity")) for item in items)
               for field in METRIC_FIELDS[:4]}
    due = request.return_due_at
    metrics["overdue_count"] = int(request.status in OUTSTANDING and due is not None and due < now)
    end = request.closed_at if request.status in CLOSED and request.closed_at else now
    metrics["loan_hours"] = round(max(0.0, (end - request.issued_at).total_seconds() / 3600), 2)
    currencies, cost, unpriced = set(), Decimal("0"), False
    for item in items:
        if not item.missing_quantity:
            continue
        product = item.product
        if product.unit_cost is None or product.cost_unit != "count" or not product.cost_currency:
            unpriced = True
            continue
        currencies.add(product.cost_currency)
        cost += product.unit_cost * item.missing_quantity
    known = not unpriced and len(currencies) <= 1
    metrics["currency"] = next(iter(currencies)) if known and currencies else ""
    metrics["estimated_loss_cost"] = cost if known else None
    return metrics
