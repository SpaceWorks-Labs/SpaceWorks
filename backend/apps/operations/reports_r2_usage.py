"""How a space uses its own reporting: scheduled deliveries and saved views, in counts."""

from django.db.models import Count

from apps.operations.reports_r2_common import metric_report


def _usage_rows(space, start, end):
    from apps.operations.models import ReportDelivery, ReportSchedule, SavedView
    schedules = ReportSchedule.objects.filter(makerspace=space)
    deliveries = ReportDelivery.objects.filter(schedule__makerspace=space, created_at__gte=start, created_at__lt=end)
    by_cadence = schedules.filter(is_active=True).order_by().values("cadence").annotate(n=Count("pk")).order_by("cadence")
    return [
        ("schedules_active", schedules.filter(is_active=True).count()),
        ("schedules_paused", schedules.filter(is_active=False).count()),
        *[(f"schedules_{row['cadence']}", row["n"]) for row in by_cadence],
        ("deliveries_sent", deliveries.filter(status="sent").count()),
        ("deliveries_failed", deliveries.filter(status="failed").count()),
        ("saved_views", SavedView.objects.filter(makerspace=space).count()),
    ]


def build_report_usage(makerspace_id, *, limit=None, date_range=None, actor=None, grain=None):
    return metric_report(makerspace_id, ("reports",), _usage_rows, limit=limit, date_range=date_range,
                         definition="Scheduled report deliveries and saved views, in counts; no recipient appears.")
