"""Bulk maintenance lockout for the queue-ETA snapshot, inside its four-query budget.

`schedules_annotation()` rides on the snapshot's machine SELECT: one array per machine
row of its active `blocks_use` schedules, each carrying the meter readings that
`maintenance.meters.readings` derives (independent usage entries since the schedule's
`meter_started_at` plus finished/failed service runs, `maintenance.meters.due_queryset`'s
SQL). `locked_out()` then applies `lockout.schedule_blocks`, the one rule, to those rows
without further queries.
"""

import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.db.models import Count, DecimalField, IntegerField, OuterRef, Subquery, Sum, TextField, Value
from django.db.models.functions import Cast, Coalesce, JSONObject

from apps.machines.lockout import lockout_active, meters_active, schedule_blocks


def schedules_annotation():
    """ARRAY of JSON schedule rows for the outer Machine row (``OuterRef("pk")``)."""
    from django.contrib.postgres.expressions import ArraySubquery

    from apps.maintenance.meter_jobs import runs
    from apps.maintenance.models import MaintenanceSchedule
    from apps.machines.models import MachineUsageEntry
    usage = MachineUsageEntry.objects.filter(machine_id=OuterRef("machine_id"),
                                             created_at__gte=OuterRef("meter_started_at"),
                                             service_request__isnull=True).order_by().values("machine_id")
    hours = usage.annotate(total=Sum("hours")).values("total")
    typed = usage.filter(source=MachineUsageEntry.Source.TYPED_MANUAL).annotate(total=Count("pk")).values("total")
    service = runs(OuterRef("machine_id"), OuterRef("meter_started_at")).order_by().values("assigned_machine_id")
    minutes = service.annotate(total=Sum("actual_minutes")).values("total")
    finished = service.annotate(total=Count("pk")).values("total")
    decimal = DecimalField(max_digits=20, decimal_places=6)
    meter_hours = (Coalesce(Subquery(hours), Value(Decimal("0")), output_field=decimal)
                   + Cast(Coalesce(Subquery(minutes), Value(0), output_field=IntegerField()), decimal)
                   / Value(Decimal("60"), output_field=decimal))
    meter_jobs = (Coalesce(Subquery(typed), Value(0), output_field=IntegerField())
                  + Coalesce(Subquery(finished), Value(0), output_field=IntegerField()))
    rows = MaintenanceSchedule.objects.filter(machine_id=OuterRef("pk"), is_active=True, blocks_use=True)
    return ArraySubquery(rows.order_by("pk").values(row=JSONObject(
        trigger="trigger", next_due="next_due", job_count="job_count",
        usage_hours=Cast("usage_hours", TextField()), hours=Cast(meter_hours, TextField()), jobs=meter_jobs)))


def _schedule(item):
    item = json.loads(item) if isinstance(item, str) else item
    number = lambda value: None if value is None else Decimal(str(value))  # noqa: E731
    return SimpleNamespace(is_active=True, blocks_use=True, trigger=item["trigger"],
                           next_due=date.fromisoformat(str(item["next_due"])[:10]),
                           usage_hours=number(item["usage_hours"]), job_count=item["job_count"],
                           hours=number(item["hours"]) or Decimal("0"), jobs=int(item["jobs"] or 0))


def locked_out(space, items, today, grace_days):
    """`space` needs the capability columns (`lifecycle_state`, `enabled_modules`, `enabled_features`)."""
    if not items or not lockout_active(space):
        return False
    meters_on = meters_active(space)
    for row in map(_schedule, items):
        if schedule_blocks(row, today, grace_days, meters_on=meters_on, reading=lambda row=row: (row.hours, row.jobs)):
            return True
    return False
