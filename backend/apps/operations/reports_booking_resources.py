"""Resource projections reuse the canonical occupancy calculation."""

from django.utils.translation import gettext
from dataclasses import replace
from rest_framework.exceptions import ValidationError

from .reports_bookings import build_booking_utilization


def extend_with_booking_arrival_counts(result, *, makerspace_id, space_id, date_range):
    """Count current arrival facts over the same reservation-overlap window.

    Reversed arrivals do not count. Completion alone never implies arrival, and
    these counts leave all calendar reservation durations unchanged.
    """
    from apps.bookings.arrival_projection import arrival_metrics
    from apps.bookings.models import Booking
    from .report_definitions_bookings import ARRIVAL_FIELDS

    bookings = Booking.objects.filter(space__makerspace_id=makerspace_id, space_id=space_id)
    start, end = date_range or (None, None)
    if start is not None:
        bookings = bookings.filter(ends_at__gt=start)
    if end is not None:
        bookings = bookings.filter(starts_at__lt=end)
    counts = arrival_metrics(bookings)
    return replace(result, field_order=(*result.field_order, *ARRIVAL_FIELDS),
                   records=[{**row, **counts} for row in result.records],
                   meta={**result.meta, "arrival_counts_available": True})


def build_resource_utilization(makerspace_id, *, subject_kind, subject_id, limit=None, date_range=None):
    result = build_booking_utilization(
        makerspace_id, subject_kind=subject_kind, subject_id=subject_id, limit=limit, date_range=date_range,
    )
    return extend_with_booking_arrival_counts(
        result, makerspace_id=makerspace_id, space_id=subject_id, date_range=date_range,
    )


def require_bounded_period(date_range):
    start, end = date_range or (None, None)
    if start is None or end is None or end <= start:
        raise ValidationError({"start": gettext("Resource PDFs require a complete, positive start/end period.")})


def build_resource_utilization_pdf(makerspace_id, *, subject_kind, subject_id, limit=None, date_range=None):
    require_bounded_period(date_range)
    return build_resource_utilization(
        makerspace_id, subject_kind=subject_kind, subject_id=subject_id, limit=limit, date_range=date_range,
    )
