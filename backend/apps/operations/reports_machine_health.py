"""Technical fault counts, device-reported jobs, and machine warranty dates."""

from django.db.models import Count
from django.utils import timezone

from apps.machines.models import MachineErrorLog
from .reports_common import apply_range, period_expression
from .reports_machine_common import machines, result, space_ids, spaces

ERROR_FIELDS = ("period", "machine_id", "machine_name", "machine_type", "severity", "error_count")
PRINTER_FIELDS = ("period", "machine_id", "machine_name", "machine_type", "state", "outcome", "job_count")
WARRANTY_FIELDS = ("warranty_id", "machine_id", "machine_name", "machine_type", "purchased_on", "warranty_expires_on", "days_until_expiry")


def build_machine_errors(makerspace_id, *, limit=None, date_range=None, grain="day", actor=None):
    rows = []
    for space, scope in spaces(makerspace_id, ("machines",), actor):
        qs = apply_range(MachineErrorLog.objects.filter(machine__in=machines(space, scope)), "created_at", date_range)
        for row in qs.order_by().annotate(period=period_expression("created_at", grain, makerspace=space)).values(
            "machine__makerspace_id", "period", "machine_id", "machine__name", "machine__machine_type__name", "severity",
        ).annotate(error_count=Count("pk")).order_by("period", "machine_id", "severity"):
            rows.append({"makerspace_id": row["machine__makerspace_id"], "period": row["period"].date().isoformat(),
                         "machine_id": row["machine_id"], "machine_name": row["machine__name"],
                         "machine_type": row["machine__machine_type__name"], "severity": row["severity"], "error_count": row["error_count"]})
    return result(ERROR_FIELDS, rows, makerspace_id, limit)


def build_printer_jobs(makerspace_id, *, limit=None, date_range=None, grain="day", actor=None):
    from apps.devices.models import PrinterJob
    rows = []
    for space, scope in spaces(makerspace_id, ("machines", "machine_service", "devices"), actor):
        qs = apply_range(PrinterJob.objects.filter(makerspace_id__in=space_ids(space), machine__in=machines(space, scope)), "created_at", date_range)
        for row in qs.order_by().annotate(period=period_expression("created_at", grain, makerspace=space)).values(
            "makerspace_id", "period", "machine_id", "machine__name", "machine__machine_type__name", "state", "outcome",
        ).annotate(job_count=Count("pk")).order_by("period", "machine_id", "state", "outcome"):
            rows.append({"makerspace_id": row["makerspace_id"], "period": row["period"].date().isoformat(),
                         "machine_id": row["machine_id"], "machine_name": row["machine__name"],
                         "machine_type": row["machine__machine_type__name"], "state": row["state"],
                         "outcome": row["outcome"], "job_count": row["job_count"]})
    return result(PRINTER_FIELDS, rows, makerspace_id, limit, definition="Current device-job state/outcome by job creation period; not a history of state transitions.",
                  limitations="Jobs whose machine was deleted cannot be type-scoped and are omitted.")


def build_warranty_expiry(makerspace_id, *, limit=None, date_range=None, actor=None):
    from zoneinfo import ZoneInfo
    from apps.warranty.models import Warranty
    rows = []
    for space, scope in spaces(makerspace_id, ("machines",), actor):
        today = timezone.now().astimezone(ZoneInfo(space.timezone)).date()
        qs = Warranty.objects.filter(makerspace_id__in=space_ids(space), machine__in=machines(space, scope), warranty_expires_on__isnull=False)
        if date_range:
            start, end = date_range
            zone = ZoneInfo(space.timezone)
            if start:
                qs = qs.filter(warranty_expires_on__gte=start.astimezone(zone).date())
            if end:
                qs = qs.filter(warranty_expires_on__lt=end.astimezone(zone).date())
        for row in qs.order_by("warranty_expires_on", "pk").values(
            "id", "makerspace_id", "machine_id", "machine__name", "machine__machine_type__name", "purchased_on", "warranty_expires_on",
        ):
            rows.append({"makerspace_id": row["makerspace_id"], "warranty_id": row["id"], "machine_id": row["machine_id"],
                         "machine_name": row["machine__name"], "machine_type": row["machine__machine_type__name"],
                         "purchased_on": row["purchased_on"], "warranty_expires_on": row["warranty_expires_on"],
                         "days_until_expiry": (row["warranty_expires_on"] - today).days})
    rows.sort(key=lambda row: (row["warranty_expires_on"], row["makerspace_id"], row["machine_id"]))
    return result(WARRANTY_FIELDS, rows, makerspace_id, limit)
