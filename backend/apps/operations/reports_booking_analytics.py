"""Reservation occupancy, creation lead time, and authorized member rankings."""

from django.utils.translation import gettext
from datetime import timedelta, timezone as dt_timezone
from decimal import Decimal

from django.db.models import Count, F, Sum, DurationField, ExpressionWrapper
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.admin_api.permissions import require_action
from apps.bookings.models import BookableSpace, Booking
from .reports_booking_trends import RESERVED, booking_window, overlapping, resource_periods
from .reports_common import apply_range, period_expression
from .reports_de_common import source_spaces as report_spaces
from .report_fields_de import OCCUPANCY_FIELDS, LEAD_FIELDS, MEMBER_FIELDS
from .reports_de_common import histogram_bucket, hours, percent, period_at, result

LEAD_EDGES = (0, 1, 24, 72, 168, 720)
LEAD_LABELS = ("After start", "Under 1 hour", "1–24 hours", "1–3 days", "3–7 days", "7–30 days", "30+ days")


def _merged(intervals):
    start = end = None
    for left, right in sorted(intervals):
        if end is None or left > end:
            if end is not None:
                yield start, end
            start, end = left, right
        else:
            end = max(end, right)
    if end is not None:
        yield start, end


def _hour_slices(start, end, space):
    from zoneinfo import ZoneInfo
    zone = ZoneInfo(space.timezone)
    at = start.astimezone(dt_timezone.utc)
    end = end.astimezone(dt_timezone.utc)
    while at < end:
        local = at.astimezone(zone)
        # UTC progression visits both folds of a repeated local hour.
        step = timedelta(minutes=60 - local.minute, seconds=-local.second, microseconds=-local.microsecond)
        after = min(at + step, end)
        yield local, hours(at, after)
        at = after


def build_booking_occupancy(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in report_spaces(makerspace_id, "bookings"):
        bounds = booking_window(space, date_range)
        bookings = list(overlapping(space, bounds).filter(status__in=RESERVED).values("space_id", "starts_at", "ends_at"))
        periods = resource_periods(space, bounds, grain, bookings)
        if not periods:
            continue
        start, end = periods[0][1], periods[-1][2]
        resource_count = BookableSpace.objects.filter(makerspace=space).count()
        groups = {}

        def bucket(local):
            key = (period_at(local, grain, space), local.weekday(), local.hour)
            return groups.setdefault(key, dict(makerspace_id=space.pk, period=key[0], weekday=key[1], hour=key[2],
                                               occupied_hours=Decimal(0), window_hours=Decimal(0)))

        for local, elapsed in _hour_slices(start, end, space):
            bucket(local)["window_hours"] += elapsed * resource_count
        intervals = {}
        for booking in bookings:
            intervals.setdefault(booking["space_id"], []).append((
                max(start, booking["starts_at"]), min(end, booking["ends_at"])))
        for rows in intervals.values():
            for left, right in _merged(rows):
                for local, elapsed in _hour_slices(left, right, space):
                    bucket(local)["occupied_hours"] += elapsed
        for key in sorted(groups):
            row = groups[key]
            row["occupancy_percent"] = percent(row["occupied_hours"], row["window_hours"])
            records.append(row)
    return result(OCCUPANCY_FIELDS, records, makerspace_id, limit, meta={
        "basis": "Reserved calendar occupancy; overlapping intervals unioned per resource",
        "limitations": "Denominator includes retained inactive resources; no historical opening-hours calendar",
    })


def build_booking_lead_time(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in report_spaces(makerspace_id, "bookings"):
        qs = apply_range(Booking.objects.filter(space__makerspace=space), "created_at", booking_window(space, date_range))
        qs = qs.annotate(period=period_expression("created_at", grain, makerspace=space))
        groups = {}
        for row in qs.values("period", "starts_at", "created_at").iterator():
            label = histogram_bucket(hours(row["created_at"], row["starts_at"]), LEAD_EDGES, LEAD_LABELS)
            key = (row["period"], label)
            groups[key] = groups.get(key, 0) + 1
        for (period, label), count in sorted(groups.items(), key=lambda item: (item[0][0], LEAD_LABELS.index(item[0][1]))):
            records.append(dict(makerspace_id=space.pk, period=period, lead_time_bucket=label, booking_count=count))
    return result(LEAD_FIELDS, records, makerspace_id, limit, meta={
        "basis": "Creation cohorts; elapsed hours from creation to scheduled start",
    })


def build_booking_top_members(makerspace_id, *, limit=None, date_range=None, actor=None):
    if makerspace_id is None:
        raise PermissionDenied(gettext("Member rankings require a single makerspace."))
    require_action(actor, rbac.Action.MANAGE_BOOKINGS, makerspace_id)
    require_action(actor, rbac.Action.VIEW_AUDIT, makerspace_id)
    records = []
    for space in report_spaces(makerspace_id, "bookings"):
        qs = apply_range(Booking.objects.filter(space__makerspace=space, member__isnull=False,
                                               status__in=RESERVED), "starts_at", booking_window(space, date_range))
        rows = qs.values("member_id", "member__first_name", "member__last_name", "member__username").annotate(
            booking_count=Count("pk"), duration=Sum(ExpressionWrapper(F("ends_at") - F("starts_at"), output_field=DurationField())))
        for row in rows:
            name = " ".join(filter(None, (row["member__first_name"], row["member__last_name"]))) or row["member__username"]
            records.append(dict(member_id=row["member_id"], member=name, booking_count=row["booking_count"],
                                reserved_hours=Decimal(str(row["duration"].total_seconds())) / 3600))
    records.sort(key=lambda r: (-r["booking_count"], r["member_id"]))
    # All source rows contribute to Other; never run a top-N database LIMIT first.
    top_n = min(limit, 10) if limit is not None else 10
    if len(records) > top_n:
        tail = records[top_n:]
        records = records[:top_n] + [dict(member_id=None, member="Other",
                                         booking_count=sum(r["booking_count"] for r in tail),
                                         reserved_hours=sum(r["reserved_hours"] for r in tail))]
    return result(MEMBER_FIELDS, records, makerspace_id, None, meta={
        "basis": "Confirmed, completed and no-show reservations attributed by member FK",
        "limitations": "Unattributed reservations omitted; hours are the full reservation duration",
    })
