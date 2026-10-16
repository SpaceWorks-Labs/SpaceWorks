"""Booking adapter for shared manual reports and saved-view authorization."""

from django.shortcuts import get_object_or_404

from apps.makerspaces.guards import require_feature
from apps.operations.report_subjects import ReportSubject, register
from . import booking_authority
from .booking_permissions import MANAGE_RESERVATIONS
from .models import BookableSpace

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


def register_subject():
    from apps.accounts import rbac
    register("bookable_space", ReportSubject(KEYS, resolve, authorize, rbac.Action.MANAGE_BOOKINGS))
