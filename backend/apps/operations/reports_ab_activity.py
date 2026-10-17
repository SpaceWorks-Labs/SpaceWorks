"""Problem triage, watch demand and QR activity without raw payload disclosure."""

from collections import defaultdict
from zoneinfo import ZoneInfo

from apps.boxes.models import QrScanEvent
from apps.hardware_requests.models import PublicProblemReport
from apps.inventory.models_watch import InventoryWatch
from apps.operations.report_types import ReportNotFound
from apps.operations.reports_ab_common import bucket, dated, hours, in_range, result, spaces


PROBLEM_FIELDS = ("period", "opened_count", "resolved_count", "resolution_hours", "average_resolution_hours")
WATCH_FIELDS = ("product_id", "product_name", "watch_count", "waiting_count")
QR_FIELDS = ("period", "context", "target_type", "target_id", "hour_of_week", "count")
QR_ACTOR_FIELDS = ("actor_id", "count")


def build_problem_reports(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in spaces(makerspace_id, "guest_handover"):
        groups = {}

        def row(at):
            p = bucket(at, space, grain)
            return groups.setdefault(p, dict(makerspace_id=space.pk, period=p, opened_count=0,
                                             resolved_count=0, resolution_hours=0))

        qs = PublicProblemReport.objects.filter(makerspace=space)
        from django.db.models import Q
        if date_range:
            from apps.operations.reports_common import apply_range
            qs = qs.filter(Q(pk__in=apply_range(qs, "created_at", date_range).values("pk")) |
                           Q(pk__in=apply_range(qs, "resolved_at", date_range).values("pk")))
        for report in qs.iterator():
            if in_range(report.created_at, date_range):
                row(report.created_at)["opened_count"] += 1
            if in_range(report.resolved_at, date_range):
                target = row(report.resolved_at)
                target["resolved_count"] += 1
                target["resolution_hours"] += hours(report.created_at, report.resolved_at)
        for target in groups.values():
            target["average_resolution_hours"] = (round(target["resolution_hours"] / target["resolved_count"], 2)
                                                  if target["resolved_count"] else None)
            records.append(target)
    return result(PROBLEM_FIELDS, sorted(records, key=lambda row: row["period"]), makerspace_id, limit)


def build_inventory_watch_demand(makerspace_id, *, limit=None, date_range=None):
    from django.db.models import Count, Q
    from apps.operations.reports_common import apply_range
    records = []
    for space in spaces(makerspace_id, "public_inventory"):
        qs = apply_range(InventoryWatch.objects.filter(makerspace=space, product__is_archived=False,
                                                       product__available_quantity__lte=0),
                         "created_at", date_range)
        for row in qs.values("product_id", "product__name").annotate(
            watch_count=Count("pk"), waiting_count=Count("pk", filter=Q(notified_at__isnull=True)),
        ):
            records.append(dict(makerspace_id=space.pk, product_id=row["product_id"],
                product_name=row["product__name"], watch_count=row["watch_count"], waiting_count=row["waiting_count"]))
    return result(WATCH_FIELDS, sorted(records, key=lambda row: (-row["waiting_count"], row["product_id"])),
                  makerspace_id, limit)


def build_qr_scans(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in spaces(makerspace_id, "scanner"):
        groups = defaultdict(int)
        qs = dated(QrScanEvent.objects.filter(makerspace=space), "created_at", space, date_range, grain
                   ).select_related("qr_code")
        for event in qs.iterator():
            local = event.created_at.astimezone(ZoneInfo(space.timezone))
            # Member-card targets identify a person; the counts-only projection keeps
            # their type count but never their member-card identifier.
            target_id = None if event.qr_code.target_type == "member_card" else event.qr_code.target_id
            groups[(event.report_period.date(), event.context, event.qr_code.target_type, target_id,
                    local.weekday() * 24 + local.hour)] += 1
        records.extend(dict(makerspace_id=space.pk, period=p, context=c, target_type=t, target_id=i, hour_of_week=h, count=n)
                       for (p, c, t, i, h), n in sorted(groups.items(), key=lambda item: str(item[0])))
    return result(QR_FIELDS, records, makerspace_id, limit)


def build_qr_scan_actors(makerspace_id, *, limit=None, date_range=None, actor=None):
    from django.db.models import Count
    from apps.operations.reports_common import apply_range
    if makerspace_id is None:
        raise ReportNotFound()
    rows = []
    for space in spaces(makerspace_id, "scanner"):
        from apps.operations.reports_ab_assets import _require_inventory
        _require_inventory(actor, space.pk)
        rows.extend(apply_range(QrScanEvent.objects.filter(makerspace=space), "created_at", date_range
                                ).values("actor_id").annotate(count=Count("pk")).order_by("-count", "actor_id"))
    return result(QR_ACTOR_FIELDS, rows, makerspace_id, limit, identity=True)
