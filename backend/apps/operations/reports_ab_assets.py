"""Asset loan duration and holder lists with explicit disclosure boundaries."""

from collections import defaultdict

from django.utils import timezone

from apps.hardware_requests.display import requester_label
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItemAsset
from apps.inventory.models import InventoryAsset
from apps.operations.report_types import ReportNotFound
from apps.operations.reports_ab_common import (
    dated, hours, percent, result, spaces, window,
)


ASSET_FIELDS = ("asset_id", "product_id", "product_name", "times_lent", "days_on_loan",
                "window_days", "utilisation_percent", "damaged_count", "lost_count")
LONG_FIELDS = ("request_id", "holder", "status", "issued_at", "closed_at", "loan_days")
OVERDUE_FIELDS = ("row_kind", "period", "request_id", "holder", "due_at", "overdue_days",
                  "open_loans", "loans_due", "overdue_count", "open_overdue_count", "overdue_rate_percent")


def asset_records(space, date_range):
    start, end = window(date_range)
    qs = HardwareRequestItemAsset.objects.filter(request_item__request__makerspace=space,
                                                issued_at__lt=end).select_related("asset__product", "request_item__request")
    if start:
        from django.db.models import Q
        qs = qs.filter(Q(returned_at__isnull=True) | Q(returned_at__gt=start))
    groups = {
        asset.pk: dict(makerspace_id=space.pk, asset_id=asset.pk, product_id=asset.product_id,
            product_name=asset.product.name, times_lent=0, days_on_loan=0,
            window_days=hours(max(start, asset.created_at) if start else asset.created_at, end) / 24,
            damaged_count=0, lost_count=0)
        for asset in InventoryAsset.objects.filter(makerspace=space, product__is_archived=False,
                                                   created_at__lt=end).select_related("product")
    }
    for link in qs.iterator():
        # Loss/damage links may have no returned_at on older direct handouts.
        resolved_at = link.returned_at or (link.request_item.request.closed_at if link.outcome != "issued" else None)
        if start and resolved_at and resolved_at <= start:
            continue
        stop = min(resolved_at or end, end)
        begin = max(link.issued_at, start) if start else link.issued_at
        row = groups.setdefault(link.asset_id, dict(makerspace_id=space.pk, asset_id=link.asset_id,
            product_id=link.asset.product_id, product_name=link.asset.product.name, times_lent=0,
            days_on_loan=0, window_days=hours(max(start, link.asset.created_at) if start else link.asset.created_at, end) / 24,
            damaged_count=0, lost_count=0))
        row["times_lent"] += int(start is None or link.issued_at >= start)
        row["days_on_loan"] += hours(begin, stop) / 24
        row["damaged_count"] += int(link.outcome == "damaged" and (resolved_at is None or resolved_at <= end))
        row["lost_count"] += int(link.outcome == "lost" and (resolved_at is None or resolved_at <= end))
    for row in groups.values():
        row["utilisation_percent"] = percent(row["days_on_loan"], row["window_days"])
    return list(groups.values())


def build_asset_usage(makerspace_id, *, limit=None, date_range=None):
    rows = [row for space in spaces(makerspace_id, "asset_units", "request_workflow")
            for row in asset_records(space, date_range)]
    rows.sort(key=lambda row: (-row["times_lent"], row["asset_id"]))
    return result(ASSET_FIELDS, rows, makerspace_id, limit)


def build_longest_loans(makerspace_id, *, limit=None, date_range=None, actor=None):
    if makerspace_id is None:
        raise ReportNotFound()
    records = []
    for space in spaces(makerspace_id, "request_workflow"):
        _require_inventory(actor, space.pk)
        from apps.operations.reports_common import apply_range
        qs = apply_range(HardwareRequest.objects.filter(makerspace=space, issued_at__isnull=False),
                         "issued_at", date_range).select_related("requester")
        end = timezone.now()
        for request in qs.iterator():
            records.append(dict(request_id=request.pk, holder=requester_label(request), status=request.status,
                issued_at=request.issued_at, closed_at=request.closed_at,
                loan_days=round(hours(request.issued_at, request.closed_at or end) / 24, 2)))
    return result(LONG_FIELDS, sorted(records, key=lambda row: (-row["loan_days"], row["request_id"])),
                  makerspace_id, limit, identity=True)


def build_overdue_loans(makerspace_id, *, limit=None, date_range=None, grain="day", actor=None):
    if makerspace_id is None:
        raise ReportNotFound()
    records = []
    for space in spaces(makerspace_id, "request_workflow"):
        _require_inventory(actor, space.pk)
        now = timezone.now()
        groups = defaultdict(lambda: [0, 0, 0, 0])
        borrowers = {}
        from apps.makerspaces.anonymous_requesters import anonymous_requester_ids
        anonymous = set(anonymous_requester_ids([space.pk]))
        # Historical points are due-date cohorts, not reconstructed daily snapshots.
        qs = dated(HardwareRequest.objects.filter(makerspace=space, issued_at__isnull=False,
                                                   return_due_at__isnull=False),
                   "return_due_at", space, date_range, grain).select_related("requester")
        for request in qs.iterator():
            open_loan = request.status in ("issued", "partially_returned")
            overdue = open_loan and request.return_due_at < now
            period = request.report_period.date()
            groups[period][0] += int(open_loan)
            groups[period][1] += int(request.return_due_at < now)
            groups[period][2] += int(overdue or (request.closed_at is not None and request.closed_at > request.return_due_at))
            groups[period][3] += int(overdue)
            if overdue:
                days = round(hours(request.return_due_at, now) / 24, 2)
                records.append(dict(row_kind="holder", period=period, request_id=request.pk,
                    holder=requester_label(request), due_at=request.return_due_at,
                    overdue_days=days))
                if request.requester_id not in anonymous:
                    borrower = borrowers.setdefault(request.requester_id, dict(row_kind="borrower",
                        holder=requester_label(request), overdue_days=0, overdue_count=0, open_overdue_count=0))
                    borrower["overdue_days"] += days
                    borrower["overdue_count"] += 1
                    borrower["open_overdue_count"] += 1
        for period, (open_count, denominator, numerator, open_overdue) in sorted(groups.items()):
            records.append(dict(row_kind="due_cohort", period=period, open_loans=open_count, loans_due=denominator,
                overdue_count=numerator, open_overdue_count=open_overdue, overdue_rate_percent=percent(numerator, denominator)))
        records.extend(borrowers.values())
    records.sort(key=lambda row: (row["row_kind"] != "holder", -row.get("overdue_days", 0)))
    return result(OVERDUE_FIELDS, records, makerspace_id, limit, identity=True,
        meta={"basis": "Current overdue holder list; trend is overdue loans divided by loans due in each due-date cohort."})


def _require_inventory(actor, space_id):
    if actor is not None:
        from apps.accounts import rbac
        from apps.admin_api.permissions import require_action
        require_action(actor, rbac.Action.VIEW_INVENTORY, space_id)
        require_action(actor, rbac.Action.VIEW_AUDIT, space_id)
