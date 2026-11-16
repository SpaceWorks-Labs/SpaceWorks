"""Staff free/busy for one room around a requested window (decision 216, event hall picker).

Read-only, no audit, no new availability math: opening hours come from
`published_open_intervals`, busy time from `confirmed_occupancy` + `occupied_window` (the same
reads the public availability view uses), and the requested window's verdict from the same
seams admission calls (`enforce_booking_rules`, `confirmed_overlap`, `admission_status`).
Pending bookings are listed but hold nothing, exactly as admission treats them. Room outages,
machine repair and closures are SHOWN as `unavailable` (`busy_overlay`); the readiness preview
still runs those admission seams.
"""

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.makerspaces.local_time import local_day_bounds, to_local

from .admission import admission_status
from .busy_overlay import busy_blocks
from .event_labels import event_labels
from .models import Booking
from .services_rules import enforce_booking_rules
from .services_schedule import confirmed_occupancy, confirmed_overlap, occupied_window, published_open_intervals


def display_range(makerspace, starts_at, ends_at):
    """The whole local day(s) the requested window touches, in the space's timezone."""
    first = local_day_bounds(makerspace, to_local(makerspace, starts_at).date())[0]
    last = local_day_bounds(makerspace, to_local(makerspace, ends_at).date())[1]
    return first, max(last, ends_at)


def _rule_detail(error):
    detail = error.detail
    if isinstance(detail, dict):
        detail = next(iter(detail.values()), "")
    if isinstance(detail, list):
        detail = detail[0] if detail else ""
    return str(detail)


def _requested(space, starts_at, ends_at):
    try:
        enforce_booking_rules(space, starts_at, ends_at, timezone.now())
        rule_detail = ""
    except ValidationError as refused:
        rule_detail = _rule_detail(refused)
    return {
        "starts_at": starts_at, "ends_at": ends_at,
        "within_rules": not rule_detail, "rule_detail": rule_detail,
        "conflict": confirmed_overlap(space, starts_at, ends_at),
        "holds_room_on_create": admission_status(space) == Booking.Status.CONFIRMED,
    }


def _label(labels, booking):
    return labels.get(booking.pk) or {"kind": "booking"}


def availability(actor, space, *, starts_at, ends_at):
    makerspace = space.makerspace
    range_start, range_end = display_range(makerspace, starts_at, ends_at)
    busy = list(confirmed_occupancy(space, range_start, range_end).only("id", "starts_at", "ends_at", "status"))
    pending = list(Booking.objects.filter(
        space=space, status=Booking.Status.PENDING, starts_at__lt=range_end, ends_at__gt=range_start,
    ).exclude(pk__in=[row.pk for row in busy]).only("id", "starts_at", "ends_at").order_by("starts_at", "id"))
    labels = event_labels(actor, makerspace, [row.pk for row in busy + pending])

    def busy_row(row):
        start, end = occupied_window(space, row.starts_at, row.ends_at)
        return {"booking_id": row.pk, "starts_at": start, "ends_at": end, "booking_starts_at": row.starts_at,
                "booking_ends_at": row.ends_at, "label": _label(labels, row),
                "tentative": row.status == Booking.Status.PENDING}

    return {
        "space_id": space.pk, "timezone": makerspace.timezone,
        "range_starts_at": range_start, "range_ends_at": range_end,
        "opening_intervals": published_open_intervals(makerspace, range_start, range_end),
        "busy": [busy_row(row) for row in busy],
        "pending": [{"booking_id": row.pk, "starts_at": row.starts_at, "ends_at": row.ends_at,
                     "label": _label(labels, row)} for row in pending],
        "requested": _requested(space, starts_at, ends_at),
        # Room outage, machine repair and closures over the same range, with staff detail.
        "unavailable": busy_blocks(space, range_start, range_end, staff=True),
    }
