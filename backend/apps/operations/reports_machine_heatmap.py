"""Elapsed usage split into local hour-of-week cells, respecting DST."""

from collections import defaultdict
from datetime import timedelta, timezone as datetime_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from .reports_machine_common import bucket, hours, result, spaces
from .reports_machine_facts import booking_facts, manual_facts, service_facts

DIMENSIONS = ("period", "measure", "machine_type_id", "machine_type", "weekday", "hour")
FIELDS = (*DIMENSIONS, "service_hours", "manual_hours", "booked_hours")


def hour_cells(start, end, space, date_range=None, grain="day"):
    """Walk real UTC hours; repeated local hours add to the same cell."""
    lower, upper = date_range or (None, None)
    start = max(start, lower) if lower else start
    end = min(end, upper) if upper else end
    cursor = start.astimezone(datetime_timezone.utc)
    end = end.astimezone(datetime_timezone.utc)
    zone = ZoneInfo(space.timezone)
    while cursor < end:
        local = cursor.astimezone(zone)
        # Offset zones need not start their local hour on a UTC whole hour.
        boundary = cursor + timedelta(minutes=60 - local.minute, seconds=-local.second, microseconds=-local.microsecond)
        stop = min(end, boundary)
        yield (bucket(cursor, grain, space), local.weekday(), local.hour), hours(stop - cursor)
        cursor = stop


def build_machine_usage_heatmap(makerspace_id, *, limit=None, date_range=None, grain="day", actor=None):
    totals = defaultdict(Decimal)
    for space, scope in spaces(makerspace_id, ("machines",), actor):
        for row in service_facts(space, scope, date_range, grain, intervals=True):
            type_id = row["assigned_machine__machine_type_id"] or row["queue__machine_type_id"]
            label = row["assigned_machine__machine_type__name"] or row["queue__machine_type__name"] or "Unknown"
            _add(totals, space, row["makerspace_id"], "service", type_id, label, row["started_at"], row["terminal_at"], date_range, grain)
        for row in manual_facts(space, scope, date_range, grain, intervals=True):
            _add(totals, space, row["machine__makerspace_id"], "manual", row["machine__machine_type_id"], row["machine__machine_type__name"],
                 row["started_at"], row["started_at"].astimezone(datetime_timezone.utc) + timedelta(hours=float(row["hours"])), date_range, grain)
        for row in booking_facts(space, scope, date_range, grain, intervals=True):
            _add(totals, space, row["space__makerspace_id"], "booked", row["space__machine_type_id"], row["space__machine_type__name"],
                 row["starts_at"], row["ends_at"], date_range, grain)
    fields = ("makerspace_id", *DIMENSIONS)
    rows = [{**dict(zip(fields, key, strict=True)), f"{key[2]}_hours": value}
            for key, value in sorted(totals.items(), key=lambda item: str(item[0]))]
    return result(FIELDS, rows, makerspace_id, limit, definition="Local hour-of-week elapsed service intervals, recorded manual hours, and booked intervals; separate measures.",
                  limitations="Manual entries without started_at and service jobs without both endpoints are omitted; current in-progress work is not extrapolated.")


def _add(totals, space, space_id, measure, type_id, label, start, end, date_range, grain):
    for (period, weekday, hour), value in hour_cells(start, end, space, date_range, grain):
        totals[(space_id, period, measure, type_id, label, weekday, hour)] += value
