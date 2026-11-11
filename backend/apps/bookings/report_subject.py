"""Booking adapter for shared manual reports and saved-view authorization."""

from django.shortcuts import get_object_or_404

from apps.makerspaces.guards import require_feature
from apps.operations.report_subjects import ReportSubject, register
from . import booking_authority
from .booking_permissions import MANAGE_RESERVATIONS, VIEW
from .models import BookableSpace, Booking

KEYS = (
    "booking-utilization", "booking-resource-utilization", "booking-resource-utilization-pdf",
    "booking-reservations", "booking-answers",
)


def resolve(tenant, pk):
    return get_object_or_404(BookableSpace.objects.select_related("makerspace"), makerspace=tenant, pk=pk)


def authorize(actor, resource, definition):
    booking_authority.require(actor, resource, None if definition.key.endswith("-pdf") else MANAGE_RESERVATIONS)
    # Legacy utilisation gains the new conjunction only when subject-filtered.
    if definition.key == "booking-utilization":
        require_feature(resource.makerspace, "bookings.analytics")


def resolve_booking(tenant, pk):
    return get_object_or_404(Booking.objects.select_related("space__makerspace"),
                            space__makerspace=tenant, pk=pk)


def authorize_booking(actor, booking, definition):
    booking_authority.require(actor, booking.space, VIEW)


def register_subject():
    from apps.accounts import rbac
    register("bookable_space", ReportSubject(KEYS, resolve, authorize, rbac.Action.MANAGE_BOOKINGS))
    register("booking", ReportSubject(("booking-equipment", "booking-consumables", "booking-loan-timeline"), resolve_booking, authorize_booking, rbac.Action.MANAGE_BOOKINGS))
