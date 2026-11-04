"""Optional event and booking queues for the staff dashboard."""

import logging

from apps.makerspaces.platform import module_enabled
from apps.accounts import rbac

logger = logging.getLogger(__name__)


def programme_counts(makerspace, *, events=True, bookings=True, actor=None):
    counts = {}
    if events and module_enabled(makerspace, "events"):
        try:
            counts.update(_event_counts(makerspace, actor))
        except Exception as exc:
            _log_failure(makerspace, "events", exc)
    if bookings and module_enabled(makerspace, "bookings"):
        try:
            counts.update(_booking_counts(makerspace, actor))
        except Exception as exc:
            _log_failure(makerspace, "bookings", exc)
    return counts


def _event_counts(makerspace, actor):
    from apps.events.models import Event, EventRegistration

    event_rows = Event.objects.filter(
        makerspace=makerspace, status=Event.Status.PUBLISHED,
        ends_at__gt=_now(),
    )
    registration_rows = EventRegistration.objects.filter(
        event__makerspace=makerspace, status=EventRegistration.Status.PENDING_APPROVAL,
    )
    if actor is not None:
        event_rows = rbac.scope_by_action(actor, rbac.Action.MANAGE_EVENTS, event_rows)
        registration_rows = rbac.scope_by_action(actor, rbac.Action.MANAGE_EVENTS, registration_rows, field="event__makerspace_id")
    return {
        "upcoming_events": event_rows.count(),
        "next_up_events": [{"id": row.pk, "title": row.title,
                            "starts_at": row.starts_at, "ends_at": row.ends_at,
                            "href": f"/admin/events?event={row.pk}"}
                           for row in event_rows.order_by("starts_at", "pk")[:3]],
        "pending_event_registrations": registration_rows.count(),
    }


def _booking_counts(makerspace, actor):
    from apps.bookings.models import Booking
    from apps.bookings.models_departure import BookingIssue

    rows = Booking.objects.filter(space__makerspace=makerspace)
    issues = BookingIssue.objects.filter(makerspace=makerspace, resolved_at__isnull=True)
    if actor is not None:
        rows = rbac.scope_by_action(actor, rbac.Action.MANAGE_BOOKINGS, rows, field="space__makerspace_id")
        issues = rbac.scope_by_action(actor, rbac.Action.MANAGE_BOOKINGS, issues, field="makerspace_id")
    return {
        "pending_bookings": rows.filter(status=Booking.Status.PENDING).count(),
        "upcoming_bookings": rows.filter(status=Booking.Status.CONFIRMED, ends_at__gt=_now()).count(),
        "open_booking_issues": issues.count(),
    }


def _log_failure(makerspace, family, exc):
    # Exception messages/tracebacks may contain SQL parameters or personal data.
    logger.error("Dashboard programme aggregation failed", extra={
        "makerspace_id": makerspace.pk, "family": family, "error_type": type(exc).__name__,
    })


def _now():
    from django.utils import timezone

    return timezone.now()
