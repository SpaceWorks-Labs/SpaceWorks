"""Shop sales (release 2 L22, #137 "shop reports"): orders, units, sales and refunds by month.

Read for the Shop Manager and the Space Manager (`manage_shop`), never needing view_finance:
every figure is the shop's own money (domain `shop`). Sales are the amounts of orders paid
in the window (by the makerspace-local month they were paid); refunds are the succeeded
refunds of shop charges in the window. A cancelled or unfilled order counts as sold only
if it was paid, and its refund shows when staff approved it. Amounts never mix currencies.
"""

from collections import defaultdict
from decimal import Decimal

from apps.makerspaces.local_time import to_local
from apps.operations.report_types import ReportResult
from apps.operations.reports_finance_sources import finance_window, in_window

FIELDS = ("month", "channel", "currency", "orders", "units", "sales", "tax", "refunds", "net")
ZERO = Decimal("0.00")
SOLD = ("paid", "ready", "collected", "refunded", "unfulfilled", "cancelled")


def _spaces(makerspace_id):
    from apps.makerspaces.models import Makerspace
    from apps.operations.report_scope import scoped_ids

    return Makerspace.objects.filter(pk__in=scoped_ids(makerspace_id)).order_by("pk")


def paid_orders(space, bounds):
    from apps.shop.models import ShopOrder

    rows = ShopOrder.objects.filter(makerspace=space, status__in=SOLD, paid_at__isnull=False).prefetch_related(
        "lines").order_by("paid_at", "pk")
    return [order for order in rows if in_window(order.paid_at, bounds)]


def shop_refunds(space, bounds):
    from apps.payments.models import Refund

    rows = Refund.objects.filter(payment__makerspace=space, payment__subject_type="shop_order",
                                 status=Refund.Status.SUCCEEDED, amended_by__isnull=True).select_related("payment")
    return [row for row in rows if in_window(row.settled_at or row.created_at, bounds)]


def build_shop_sales(makerspace_id, *, limit=None, date_range=None, actor=None):
    records = []
    for space in _spaces(makerspace_id):
        bounds = finance_window(space, date_range)
        groups = defaultdict(lambda: {"orders": 0, "units": 0, "sales": ZERO, "tax": ZERO, "refunds": ZERO})
        for order in paid_orders(space, bounds):
            group = groups[(to_local(space, order.paid_at).strftime("%Y-%m"), order.channel, order.currency)]
            group["orders"] += 1
            group["units"] += sum(line.quantity for line in order.lines.all())
            group["sales"] += order.amount_due
            group["tax"] += order.tax_total
        for refund in shop_refunds(space, bounds):
            at = refund.settled_at or refund.created_at
            groups[(to_local(space, at).strftime("%Y-%m"), "refund", refund.currency)]["refunds"] += refund.amount
        for (month, channel, currency) in sorted(groups):
            values = groups[(month, channel, currency)]
            records.append({"month": month, "channel": channel, "currency": currency, **values,
                            "net": values["sales"] - values["refunds"]})
    return ReportResult(FIELDS, records if limit is None else records[:limit], {
        "definition": "Shop orders paid in each makerspace-local month, by channel (online or the front desk), "
                      "with the units sold, what was charged and the tax in it; refunds approved through "
                      "refund cases are their own rows.",
        "columns": "sales = amount charged (tax included); net = sales - refunds.",
        "calendar": "makerspace local time",
    })


def shop_summary(space, start=None, end=None):
    """The staff Shop reports view: totals, channels, methods, months and top items."""
    from apps.payments.models import ManualSettlement, MakerspacePaymentSettings

    bounds = (start, end)
    orders = paid_orders(space, bounds)
    refunds = shop_refunds(space, bounds)
    by_channel, by_month, items = defaultdict(lambda: [0, ZERO]), defaultdict(lambda: [ZERO, ZERO]), {}
    for order in orders:
        by_channel[order.channel][0] += 1
        by_channel[order.channel][1] += order.amount_due
        by_month[to_local(space, order.paid_at).strftime("%Y-%m")][0] += order.amount_due
        for line in order.lines.all():
            row = items.setdefault(line.label, [0, ZERO])
            row[0] += line.quantity
            row[1] += line.line_total
    for refund in refunds:
        by_month[to_local(space, refund.settled_at or refund.created_at).strftime("%Y-%m")][1] += refund.amount
    methods = defaultdict(lambda: ZERO)
    settlements = ManualSettlement.objects.filter(payment__subject_type="shop_order", payment__makerspace=space,
                                                  payment__subject_id__in=[o.pk for o in orders],
                                                  amended_by__isnull=True)
    offline = 0
    for row in settlements:
        methods[row.method] += row.amount
        offline += row.amount
    online = sum((o.amount_due for o in orders), ZERO) - offline
    if online > 0:
        methods["online"] += online
    sales = sum((order.amount_due for order in orders), ZERO)
    refunded = sum((refund.amount for refund in refunds), ZERO)
    top = sorted(items.items(), key=lambda pair: (-pair[1][1], pair[0]))[:10]
    return {
        "currency": MakerspacePaymentSettings.for_makerspace(space).default_currency,
        "totals": {"orders": len(orders), "sales": sales, "refunds": refunded, "net": sales - refunded,
                   "tax": sum((order.tax_total for order in orders), ZERO)},
        "by_channel": [{"channel": key, "orders": value[0], "sales": value[1]} for key, value in sorted(by_channel.items())],
        "by_method": [{"method": key, "amount": value} for key, value in sorted(methods.items())],
        "by_month": [{"month": key, "sales": value[0], "refunds": value[1]} for key, value in sorted(by_month.items())],
        "top_items": [{"label": label, "quantity": value[0], "sales": value[1]} for label, value in top],
    }
