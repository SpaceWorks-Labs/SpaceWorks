"""Current outstanding debt aged by its due date, falling back to charge creation."""

from collections import defaultdict
from decimal import Decimal

from django.utils import timezone

from apps.accounts import rbac
from apps.makerspaces.local_time import to_local
from apps.operations.membership_report_scope import report_queryset
from apps.operations.report_types import ReportResult
from apps.operations.reports_fg_common import scoped_spaces
from apps.operations.reports_finance_sources import finance_window, in_window
from apps.payments.models import Payment

FIELDS = ("currency", "age_bucket", "payment_count", "outstanding_amount")
AGE_BUCKETS = ("0-30", "31-60", "61-90", "90+")


def build_payments_ageing(makerspace_id, *, limit=None, date_range=None, now=None, actor=None):
    now = now or timezone.now()
    records = []
    action = rbac.Action.VIEW_FINANCE
    for space in scoped_spaces(makerspace_id, action, actor=actor):
        today = to_local(space, now).date()
        window = finance_window(space, date_range)
        groups = defaultdict(lambda: {bucket: [0, Decimal("0.00")] for bucket in AGE_BUCKETS})
        rows = report_queryset(Payment.objects.filter(status=Payment.Status.PENDING, created_at__lte=now),
                               space.pk, action, actor=actor).values("created_at", "due_at", "currency", "amount")
        for payment in rows.iterator():
            if not in_window(payment["created_at"], window):
                continue
            age = max(0, (today - to_local(space, payment["due_at"] or payment["created_at"]).date()).days)
            bucket = AGE_BUCKETS[0 if age <= 30 else 1 if age <= 60 else 2 if age <= 90 else 3]
            values = groups[payment["currency"]][bucket]
            values[0] += 1
            values[1] += payment["amount"]
        for currency, buckets in sorted(groups.items()):
            for bucket, (count, amount) in buckets.items():
                row = dict(currency=currency, age_bucket=bucket, payment_count=count, outstanding_amount=amount)
                if makerspace_id is None:
                    row["makerspace_id"] = space.pk
                records.append(row)
    fields = (("makerspace_id",) + FIELDS) if makerspace_id is None else FIELDS
    return ReportResult(fields, records if limit is None else records[:limit], {
        "observed_at": now.isoformat(),
        "definition": "Current pending charges, aged in local days since due_at or creation; future dues count in 0-30. Day 90 belongs to 61-90; 90+ means over 90 days.",
        "limitations": "Date filters select charge creation dates; this is not a reconstructed historical receivables balance.",
    })
