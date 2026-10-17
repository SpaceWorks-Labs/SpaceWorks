"""Booking outcomes by scheduled start, with elapsed reservation hours per period."""

from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from apps.bookings.models import BookableSpace, Booking
from .reports_de_common import source_spaces as report_spaces
from .report_fields_de import UTILIZATION_FIELDS
from .reports_de_common import hours, next_period, percent, period_at, result

RESERVED = {Booking.Status.CONFIRMED, Booking.Status.COMPLETED, Booking.Status.NO_SHOW}


def booking_window(space, date_range):
    from .reports_finance_sources import finance_window
    return finance_window(space, date_range)


def overlapping(space, bounds):
    qs = Booking.objects.filter(space__makerspace=space)
    start, end = bounds
    if start:
        qs = qs.filter(ends_at__gt=start)
    if end:
        qs = qs.filter(starts_at__lt=end)
    return qs


def resource_periods(space, bounds, grain, bookings):
    """Emit idle buckets too when a complete reporting window is supplied."""
    start, end = bounds
    if not start:
        start = min((b["starts_at"] for b in bookings), default=None)
    if not end:
        end = max((b["ends_at"] for b in bookings), default=None)
    if start is None or end is None:
        if bounds != (None, None):
            return []
        at = period_at(timezone.now(), grain, space)
        return [(at, at, next_period(at, grain))]
    periods = []
    at = period_at(start, grain, space)
    while at < end:
        after = next_period(at, grain)
        periods.append((at, max(at, start), min(after, end)))
        at = after
    return periods


def build_utilization_trend(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    now = timezone.now()
    spaces = list(report_spaces(makerspace_id, "bookings"))
    ids = [space.pk for space in spaces]
    resources_by_space = {}
    for resource in BookableSpace.objects.filter(makerspace_id__in=ids).values("id", "makerspace_id", "name", "kind", "is_active"):
        resources_by_space.setdefault(resource["makerspace_id"], []).append(resource)
    # A single scoped query even for deployment reports. Different tenant-local
    # calendar bounds are ORed server-side; tenant count never adds round trips.
    predicate = Q(pk__in=[])
    for space in spaces:
        start, end = booking_window(space, date_range)
        tenant = Q(space__makerspace_id=space.pk)
        if start:
            tenant &= Q(ends_at__gt=start)
        if end:
            tenant &= Q(starts_at__lt=end)
        predicate |= tenant
    bookings_by_space = {}
    for booking in Booking.objects.filter(predicate).values("space_id", "space__makerspace_id", "starts_at", "ends_at", "status"):
        bookings_by_space.setdefault(booking["space__makerspace_id"], []).append(booking)
    for space in spaces:
        bounds = booking_window(space, date_range)
        resources = resources_by_space.get(space.pk, [])
        bookings = bookings_by_space.get(space.pk, [])
        by_resource = {}
        for booking in bookings:
            by_resource.setdefault(booking["space_id"], []).append(booking)
        for resource in resources:
            for period, start, end in resource_periods(space, bounds, grain, bookings):
                row = dict(makerspace_id=space.pk, period=period, space_id=resource["id"],
                           space_name=resource["name"], kind=resource["kind"], is_active=resource["is_active"],
                           booked=0, completed=0, no_show=0, cancelled=0, upcoming=0, reservations=0,
                           reserved_hours=Decimal(0), completed_hours=Decimal(0),
                           window_hours=hours(start, end) if all(bounds) else None)
                for booking in by_resource.get(resource["id"], []):
                    status = booking["status"]
                    if start <= booking["starts_at"] < end:
                        row["reservations"] += 1
                        field = "booked" if status == "confirmed" else status
                        if field in ("booked", "completed", "no_show", "cancelled"):
                            row[field] += 1
                        if status == "confirmed" and booking["starts_at"] >= now:
                            row["upcoming"] += 1
                    left, right = max(start, booking["starts_at"]), min(end, booking["ends_at"])
                    if left < right and status in RESERVED:
                        elapsed = hours(left, right)
                        row["reserved_hours"] += elapsed
                        if status == "completed":
                            row["completed_hours"] += elapsed
                row["terminal_reservations"] = row["completed"] + row["no_show"]
                row["no_show_rate_percent"] = percent(row["no_show"], row["terminal_reservations"])
                row["cancellation_rate_percent"] = percent(row["cancelled"], row["reservations"])
                row["reservation_utilization_percent"] = percent(row["reserved_hours"], row["window_hours"])
                records.append(row)
    records.sort(key=lambda r: (r["makerspace_id"], r["period"], -r["reserved_hours"], r["space_id"]))
    return result(UTILIZATION_FIELDS, records, makerspace_id, limit, meta={
        "basis": "Current reservation outcomes by scheduled start; elapsed hours split across periods",
        "limitations": "Utilization has a denominator only with a complete reporting window",
    })
