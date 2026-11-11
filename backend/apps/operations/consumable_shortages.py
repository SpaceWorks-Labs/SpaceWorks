"""Upcoming events and bookings whose planned consumables outrun stock (open item C25).

A read-only roll-up of the per-activity consumables reports (`reports_consumable_context`):
each upcoming event/booking with an active consumable plan or loan context is summarised
through the same builder, so the numbers and the authority checks are exactly the report's.
Activities the actor may not view are skipped silently (never an existence oracle); only rows
that need stock (shortage) or a reorder (replenishment) are returned.
"""
from datetime import timedelta

from django.apps import apps
from django.db.models import Q
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.accounts import rbac
from apps.admin_api.permissions import require_action
from apps.makerspaces.folded_capabilities import require_capability
from apps.makerspaces.platform import module_enabled
from .report_types import ReportNotFound
from .reports_consumable_context import build_booking_consumables, build_event_consumables

WINDOW_DAYS = 30
MAX_SUBJECTS = 40
_REFUSED = (ReportNotFound, PermissionDenied, NotFound, Http404, DjangoPermissionDenied)


def _upcoming_events(space, now, until):
    contexts = apps.get_model("events", "EventConsumablePlanContext").objects.filter(makerspace=space, active=True)
    loans = apps.get_model("events", "EventLoanContext").objects.filter(makerspace=space, active=True)
    return apps.get_model("events", "Event").objects.filter(
        makerspace=space, ends_at__gte=now, starts_at__lte=until,
        status__in=("draft", "published"),
    ).filter(Q(pk__in=contexts.values("event_id")) | Q(pk__in=loans.values("event_id"))).order_by("starts_at", "pk")


def _upcoming_bookings(space, now, until):
    contexts = apps.get_model("bookings", "BookingConsumablePlanContext").objects.filter(makerspace=space, active=True)
    loans = apps.get_model("bookings", "BookingLoanContext").objects.filter(makerspace=space, active=True)
    return apps.get_model("bookings", "Booking").objects.filter(
        space__makerspace=space, ends_at__gte=now, starts_at__lte=until,
        status__in=("pending", "confirmed"),
    ).filter(Q(pk__in=contexts.values("booking_id")) | Q(pk__in=loans.values("booking_id"))).select_related(
        "space").order_by("starts_at", "pk")


def _rows(kind, subject, title, records):
    for record in records:
        if record["shortage_quantity"] > 0 or record["replenishment_quantity"] > 0:
            yield {
                "subject_kind": kind, "subject_id": subject.pk, "subject_title": title,
                "starts_at": subject.starts_at, "product_id": record["product_id"],
                "product_name": record["product_name"], "remaining_planned": record["remaining_planned"],
                "available_quantity": record["available_quantity"], "shortage_quantity": record["shortage_quantity"],
                "replenishment_quantity": record["replenishment_quantity"],
            }


def planned_shortages(actor, space):
    """Shortage/replenishment rows for the next `WINDOW_DAYS` days, soonest activity first."""
    require_action(actor, rbac.Action.VIEW_INVENTORY, space.pk)
    require_capability(space, "inventory.consumables")
    now = timezone.now()
    until = now + timedelta(days=WINDOW_DAYS)
    subjects = []
    if module_enabled(space, "events"):
        subjects += [("event", event, event.title, build_event_consumables)
                     for event in _upcoming_events(space, now, until)[:MAX_SUBJECTS]]
    if module_enabled(space, "bookings"):
        # The bookable room, never the booker's name: booking names are scoped personal data.
        subjects += [("booking", booking, booking.space.name, build_booking_consumables)
                     for booking in _upcoming_bookings(space, now, until)[:MAX_SUBJECTS]]
    subjects.sort(key=lambda item: (item[1].starts_at, item[0], item[1].pk))
    rows = []
    for kind, subject, title, build in subjects[:MAX_SUBJECTS]:
        try:
            result = build(space.pk, subject_kind=kind, subject_id=subject.pk, actor=actor)
        except _REFUSED:
            continue
        rows.extend(_rows(kind, subject, title, result.records))
    return rows
