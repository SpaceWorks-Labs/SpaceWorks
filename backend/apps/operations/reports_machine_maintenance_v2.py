"""Maintenance activity by performed calendar period, with schedule snapshots."""

from collections import defaultdict
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Count, Q
from django.utils import timezone

from apps.maintenance.models import MaintenanceLog, MaintenanceSchedule
from .reports_common import apply_range, period_expression
from .reports_machine_common import machines, result, spaces

FIELDS = (
    "period", "machine_id", "machine_name", "machine_type", "is_active", "log_count",
    "costed_log_count", "total_cost", "average_cost", "last_performed_at",
    "average_interval_days", "active_schedules", "overdue_schedules", "currency",
)


def build_maintenance_activity(makerspace_id, *, limit=None, date_range=None, grain="day", actor=None):
    rows = []
    for space, scope in spaces(makerspace_id, ("machines", "machines.maintenance"), actor):
        today = timezone.now().astimezone(ZoneInfo(space.timezone)).date()
        catalog = {m.pk: m for m in machines(space, scope).select_related("machine_type")}
        schedules = {s["machine_id"]: s for s in MaintenanceSchedule.objects.filter(
            machine_id__in=catalog, is_active=True,
        ).order_by().values("machine_id").annotate(
            active=Count("pk"), overdue=Count("pk", filter=Q(next_due__lt=today)),
        )}
        groups = defaultdict(list)
        logs = apply_range(MaintenanceLog.objects.filter(machine_id__in=catalog), "performed_at", date_range)
        for log in logs.annotate(period=period_expression("performed_at", grain, makerspace=space)).order_by("performed_at", "id").values("machine_id", "period", "performed_at", "cost"):
            groups[(log["machine_id"], log["period"].date().isoformat())].append(log)
        # A null period is the current schedule snapshot; never repeat snapshots
        # in each historic bucket where a chart would accidentally sum them.
        for machine_id, machine in catalog.items():
            schedule = schedules.get(machine_id, {})
            rows.append({"makerspace_id": machine.makerspace_id, "period": None, "machine_id": machine_id,
                         "machine_name": machine.name, "machine_type": machine.machine_type.name, "is_active": machine.is_active,
                         "active_schedules": schedule.get("active", 0), "overdue_schedules": schedule.get("overdue", 0)})
        for (machine_id, period), logs in sorted(groups.items()):
            machine = catalog[machine_id]
            costs = [log["cost"] for log in logs if log["cost"] is not None]
            total = sum(costs, Decimal(0))
            gaps = len(logs) - 1
            days = Decimal(str((logs[-1]["performed_at"] - logs[0]["performed_at"]).total_seconds())) / 86400
            rows.append({"makerspace_id": machine.makerspace_id, "period": period, "machine_id": machine_id,
                         "machine_name": machine.name, "machine_type": machine.machine_type.name, "is_active": machine.is_active,
                         "log_count": len(logs), "costed_log_count": len(costs), "total_cost": total,
                         "average_cost": total / len(costs) if costs else None,
                         "last_performed_at": logs[-1]["performed_at"], "average_interval_days": float(days / gaps) if gaps else None,
                         "currency": "unknown", "_interval_total_days": days, "_interval_gap_count": gaps})
    return result(FIELDS, rows, makerspace_id, limit, limitations="MaintenanceLog has no currency. Costs are legacy unspecified-currency values confined to each machine; no cross-machine or cross-tenant monetary total is offered. Null period contains current schedule counts.")
