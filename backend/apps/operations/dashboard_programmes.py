"""Optional event and booking queues for the staff dashboard."""

import logging

from apps.makerspaces.platform import module_enabled
from apps.accounts import rbac

logger = logging.getLogger(__name__)


def programme_counts(makerspace, *, events=True, bookings=True, actor=None, failed_areas=None):
    """`failed_areas` (a list) collects the families whose counters failed (U13), so the
    dashboard can say "couldn't load Events" instead of showing a silent zero."""
    counts = {}
    if events and module_enabled(makerspace, "events"):
        try:
            counts.update(_event_counts(makerspace, actor))
        except Exception as exc:
            _log_failure(makerspace, "events", exc, failed_areas)
    if bookings and module_enabled(makerspace, "bookings"):
        try:
            counts.update(_booking_counts(makerspace, actor))
        except Exception as exc:
            _log_failure(makerspace, "bookings", exc, failed_areas)
    return counts


def _event_counts(makerspace, actor):
    from apps.events.models import Event, EventRegistration
    from apps.events.models_attendance import EventCheckInEvent

    start, end = _today_bounds(makerspace)
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
    today_rows = Event.objects.filter(
        makerspace=makerspace, status=Event.Status.PUBLISHED, starts_at__lt=end, ends_at__gt=start,
    )
    if actor is not None:
        today_rows = rbac.scope_by_action(actor, rbac.Action.MANAGE_EVENTS, today_rows)
    return {
        "upcoming_events": event_rows.count(),
        "next_up_events": [{"id": row.pk, "title": row.title,
                            "starts_at": row.starts_at, "ends_at": row.ends_at,
                            "href": f"/admin/events?event={row.pk}"}
                           for row in event_rows.order_by("starts_at", "pk")[:3]],
        "pending_event_registrations": registration_rows.count(),
        # EB12: today's events (local calendar day) and today's check-ins across them.
        "today_events": today_rows.count(),
        "today_check_ins": EventCheckInEvent.objects.filter(event__in=today_rows).count(),
    }


def _booking_counts(makerspace, actor):
    from apps.bookings.models import Booking
    from apps.bookings.models_departure import BookingIssue

    rows = Booking.objects.filter(space__makerspace=makerspace)
    issues = BookingIssue.objects.filter(makerspace=makerspace, resolved_at__isnull=True)
    if actor is not None:
        rows = rbac.scope_by_action(actor, rbac.Action.MANAGE_BOOKINGS, rows, field="space__makerspace_id")
        issues = rbac.scope_by_action(actor, rbac.Action.MANAGE_BOOKINGS, issues, field="makerspace_id")
    start, end = _today_bounds(makerspace)
    return {
        "pending_bookings": rows.filter(status=Booking.Status.PENDING).count(),
        "upcoming_bookings": rows.filter(status=Booking.Status.CONFIRMED, ends_at__gt=_now()).count(),
        "open_booking_issues": issues.count(),
        # BK3: today's live bookings (local day) and rooms out of service in the next 7 days.
        "today_bookings": rows.filter(status__in=(Booking.Status.PENDING, Booking.Status.CONFIRMED),
                                      starts_at__lt=end, ends_at__gt=start).count(),
        "room_outages_week": _room_outages_week(makerspace, actor),
    }


def _room_outages_week(makerspace, actor):
    """Open room outages overlapping the next 7 days, only while room maintenance applies."""
    from datetime import timedelta

    from apps.makerspaces.platform import feature_enabled
    from apps.separability.registry import runtime_active

    if not (runtime_active("maintenance") and feature_enabled(makerspace, "bookings.room_maintenance")):
        return 0
    from django.db.models import Q
    from apps.maintenance.models import RoomOutage

    now = _now()
    rows = RoomOutage.objects.filter(makerspace=makerspace, ended_at__isnull=True,
                                     started_at__lt=now + timedelta(days=7)).filter(
        Q(expected_back_at__isnull=True) | Q(expected_back_at__gt=now))
    if actor is not None:
        rows = rbac.scope_by_action(actor, rbac.Action.MANAGE_BOOKINGS, rows, field="makerspace_id")
    return rows.values("room_id").distinct().count()


def _today_bounds(makerspace):
    from apps.makerspaces.local_time import local_day_bounds, local_now

    return local_day_bounds(makerspace, local_now(makerspace).date())


def _log_failure(makerspace, family, exc, failed_areas=None):
    if failed_areas is not None and family not in failed_areas:
        failed_areas.append(family)
    # Exception messages/tracebacks may contain SQL parameters or personal data.
    logger.error("Dashboard programme aggregation failed", extra={
        "makerspace_id": makerspace.pk, "family": family, "error_type": type(exc).__name__,
    })


def _now():
    from django.utils import timezone

    return timezone.now()
