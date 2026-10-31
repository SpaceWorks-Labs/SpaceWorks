"""Money by provider and method, with the failed-online rate (X35).

Collected money per local month, provider (stripe, razorpay or offline) and method (the
card brand or UPI from the provider's method label for online money; cash, UPI, bank and
so on for offline receipts). The failed-online rate is the share of hosted checkouts
opened in the month whose provider reported a failed attempt; it counts attempts, not
debts, and never moves money.
"""

from collections import defaultdict
from decimal import Decimal

from apps.audit.models import AuditLog
from apps.makerspaces.local_time import to_local
from apps.operations.report_types import ReportResult
from apps.operations.reports_finance_sources import finance_sources, finance_window, in_window

FIELDS = ("month", "provider", "method", "currency", "count", "collected", "online_attempts", "online_failed",
          "failed_rate")
ZERO = Decimal("0.00")


def _spaces(makerspace_id):
    from apps.makerspaces.models import Makerspace
    from apps.operations.report_scope import scoped_ids

    return Makerspace.objects.filter(pk__in=scoped_ids(makerspace_id)).order_by("pk")


def _brand(label):
    """'Visa ••4242' -> 'Visa'; 'UPI ab••cd@ybl' -> 'UPI'. Never the masked digits."""
    return (label or "").split(" ")[0] if label else ""


def build_money_methods(makerspace_id, *, limit=None, date_range=None, actor=None):
    from apps.payments.models import Payment

    records = []
    for space in _spaces(makerspace_id):
        groups = defaultdict(lambda: {"count": 0, "collected": ZERO, "online_attempts": 0, "online_failed": 0})
        rows = [row for _space, row in finance_sources(space.pk, date_range=date_range) if row.get("collected_amount")]
        labels = dict(Payment.objects.filter(pk__in={row["payment_id"] for row in rows}).values_list("pk", "method_label"))
        for row in rows:
            online = row["row_kind"] == "online_settlement"
            provider = row.get("method", "") if online else "offline"
            method = (_brand(labels.get(row["payment_id"])) or "online") if online else (row.get("method") or "unknown")
            group = groups[(to_local(space, row["date"]).strftime("%Y-%m"), provider, method, row["currency"])]
            group["count"] += 1
            group["collected"] += row["collected_amount"]
        bounds = finance_window(space, date_range)
        for action, column in (("payment.checkout_created", "online_attempts"), ("payment.failed", "online_failed")):
            logs = AuditLog.objects.filter(makerspace_id=space.pk, action=action, target_type="payments.payment")
            targets = list(logs.values_list("created_at", "target_id"))
            currencies = dict(Payment.objects.filter(pk__in={int(t) for _at, t in targets if str(t).isdigit()})
                              .values_list("pk", "currency"))
            providers = dict(Payment.objects.filter(pk__in=currencies).values_list("pk", "provider"))
            for at, target in targets:
                if not in_window(at, bounds) or not str(target).isdigit():
                    continue
                pk = int(target)
                key = (to_local(space, at).strftime("%Y-%m"), providers.get(pk, ""), "all", currencies.get(pk, ""))
                groups[key][column] += 1
        for key in sorted(groups):
            month, provider, method, currency = key
            values = groups[key]
            attempts = values["online_attempts"]
            rate = round(values["online_failed"] / attempts, 4) if attempts else None
            records.append({"month": month, "provider": provider, "method": method, "currency": currency,
                            **values, "failed_rate": rate})
    return ReportResult(FIELDS, records if limit is None else records[:limit], {
        "definition": "Collected money by local month, provider and method; online attempt rows (method=all) "
                      "count hosted checkouts opened and failed attempts the provider reported.",
        "columns": "failed_rate=online_failed/online_attempts for the month and provider.",
    })
