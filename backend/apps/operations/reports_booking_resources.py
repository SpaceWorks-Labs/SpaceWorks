"""Resource projections reuse the canonical occupancy calculation."""

from dataclasses import replace
from rest_framework.exceptions import ValidationError

from .reports_bookings import build_booking_utilization


def extend_with_booking_arrival_counts(result, *, makerspace_id, space_id, date_range):
    """BK-C extension point: append separately labelled arrival counts when available.

    Absence of the arrival model is not a zero count. Never derive arrival from
    completed/no-show status or reinterpret reserved hours as physical use.
    """
    return replace(result, meta={**result.meta, "arrival_counts_available": False})


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
        raise ValidationError({"start": "Resource PDFs require a complete, positive start/end period."})


def build_resource_utilization_pdf(makerspace_id, *, subject_kind, subject_id, limit=None, date_range=None):
    require_bounded_period(date_range)
    return build_resource_utilization(
        makerspace_id, subject_kind=subject_kind, subject_id=subject_id, limit=limit, date_range=date_range,
    )
