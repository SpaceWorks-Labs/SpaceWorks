"""Explicit export projections read PII through Booking's model accessors."""

from django.utils.translation import gettext
import json

from apps.bookings.models import Booking
from rest_framework.exceptions import ValidationError
from .report_definitions_bookings import ANSWER_FIELDS, RESERVATION_FIELDS
from .report_types import ReportResult


def _reservations(makerspace_id, subject_kind, subject_id, date_range, limit):
    if makerspace_id is None or subject_kind != "bookable_space" or subject_id is None:
        raise ValidationError(gettext("Reservation exports require a tenant-local bookable_space subject."))
    # Load the encryption tenant path in one query; values()/raw __dict__ bypass
    # ScopedPiiModelMixin and could export ciphertext or cause a query per row.
    rows = Booking.objects.filter(space__makerspace_id=makerspace_id, space_id=subject_id).select_related("space")
    start, end = date_range or (None, None)
    if start is not None:
        rows = rows.filter(ends_at__gt=start)
    if end is not None:
        rows = rows.filter(starts_at__lt=end)
    rows = rows.order_by("starts_at", "pk")
    return rows if limit is None else rows[:limit]


def build_reservations(makerspace_id, *, subject_kind, subject_id, limit=None, date_range=None):
    rows = list(_reservations(makerspace_id, subject_kind, subject_id, date_range, limit))
    from apps.bookings.organization_booking import organization_names
    organizations = organization_names(row.pk for row in rows)
    return ReportResult(RESERVATION_FIELDS, [{
        "organization": organizations.get(row.pk, ""), "booking_id": row.pk, "space_id": row.space_id, "space_name": row.space.name,
        "name": row.name, "email": row.email, "phone": row.phone,
        "starts_at": row.starts_at, "ends_at": row.ends_at, "status": row.status, "created_at": row.created_at,
    } for row in rows])


def build_answers(makerspace_id, *, subject_kind, subject_id, limit=None, date_range=None):
    rows = _reservations(makerspace_id, subject_kind, subject_id, date_range, limit)
    return ReportResult(ANSWER_FIELDS, [{
        "booking_id": row.pk, "space_id": row.space_id, "starts_at": row.starts_at,
        "ends_at": row.ends_at, "status": row.status,
        # Preserve the stored answer/schema snapshot; a later form edit does not
        # relabel historical answers. No token, note or payment fields are read.
        "answers": json.dumps(row.custom_answers, ensure_ascii=False),
    } for row in rows])
