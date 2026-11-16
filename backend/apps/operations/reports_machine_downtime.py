"""Time in recorded statuses; current state is never backfilled into history."""

from collections import defaultdict
from datetime import datetime, time, timedelta, timezone as datetime_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from apps.machines.models import MachineStatusEvent
from .reports_machine_common import bucket, hours, machines, result, space_ids, spaces, window

FIELDS = ("period", "machine_id", "machine_name", "machine_type", "status", "status_hours")


def status_segments(start, end, events):
    status = "unknown"
    cursor = start
    for event in events:
        at = event["at"]
        if at <= start:
            status = event["to_status"]
            continue
        if at >= end:
            break
        yield cursor, at, status
        cursor, status = at, event["to_status"]
    if cursor < end:
        yield cursor, end, status


def _period_segments(start, end, grain, space):
    zone = ZoneInfo(space.timezone)
    cursor = start
    while cursor < end:
        local = cursor.astimezone(zone)
        day = local.date()
        if grain == "month":
            day = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
        else:
            day += timedelta(days=7 - day.weekday() if grain == "week" else 1)
        stop = min(end, datetime.combine(day, time.min, tzinfo=zone))
        yield bucket(cursor, grain, space), hours(stop.astimezone(datetime_timezone.utc) - cursor.astimezone(datetime_timezone.utc))
        cursor = stop


def build_machine_downtime(makerspace_id, *, limit=None, date_range=None, grain="day", actor=None):
    rows = []
    for space, scope in spaces(makerspace_id, ("machines",), actor):
        catalog = list(machines(space, scope).values("id", "makerspace_id", "name", "machine_type__name", "created_at"))
        events_by_machine = defaultdict(list)
        events = MachineStatusEvent.objects.filter(makerspace_id__in=space_ids(space), machine_id__in=[m["id"] for m in catalog])
        start, end = date_range or (None, None)
        if start:
            previous = events.filter(at__lte=start).order_by("machine_id", "-at", "-id").distinct("machine_id")
            for event in previous.values("machine_id", "at", "to_status"):
                events_by_machine[event["machine_id"]].append(event)
            events = events.filter(at__gt=start)
        if end:
            events = events.filter(at__lt=end)
        for event in events.order_by("machine_id", "at", "id").values("machine_id", "at", "to_status"):
            events_by_machine[event["machine_id"]].append(event)
        for machine in catalog:
            start, end = window(date_range, machine["created_at"])
            totals = defaultdict(Decimal)
            for lower, upper, status in status_segments(start, end, events_by_machine[machine["id"]]):
                for period, duration in _period_segments(lower, upper, grain, space):
                    totals[(period, status)] += duration
            rows.extend({"makerspace_id": machine["makerspace_id"], "machine_id": machine["id"], "machine_name": machine["name"],
                         "machine_type": machine["machine_type__name"], "period": period, "status": status, "status_hours": value}
                        for (period, status), value in sorted(totals.items()))
    return result(FIELDS, rows, makerspace_id, limit, history="Before the first MachineStatusEvent the status is unknown; from_status and current status are not historical proof.")
