"""Independent actor and source checks for a retained venue decision."""
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound

from apps.accounts import rbac
from apps.makerspaces.guards import require_module
from apps.hardware_requests.loan_context_access import safe_id
from . import event_authority, event_permissions
from .models import Event


def authorized_event(actor, makerspace, event_id):
    """Require both tenant-wide roles before showing even an absent decision."""
    require_module(makerspace, "events")
    require_module(makerspace, "bookings")
    from apps.bookings.booking_authority import active
    if (not active(actor)
            or not rbac.can(actor, rbac.Action.MANAGE_EVENTS, makerspace.pk)
            or not rbac.can(actor, rbac.Action.MANAGE_BOOKINGS, makerspace.pk)):
        raise NotFound()
    event = get_object_or_404(Event.objects.filter(makerspace_id=makerspace.pk), pk=safe_id(event_id))
    if not event_authority.can(actor, event, event_permissions.VIEW):
        raise NotFound()
    return event


def authorized_booking(actor, makerspace, booking_id):
    """Resolve the exact booking and its independently authorized resource."""
    require_module(makerspace, "bookings")
    from apps.bookings import booking_authority, booking_permissions
    from apps.bookings.models import Booking
    booking = get_object_or_404(Booking.objects.select_related("space__makerspace").filter(
        space__makerspace_id=makerspace.pk), pk=safe_id(booking_id))
    if not booking_authority.can(actor, booking.space, booking_permissions.MANAGE_RESERVATIONS):
        raise NotFound()
    return booking
