"""Answer-free scanner result and separately labelled reporting extension."""
from django.db.models import Count, Q
from django.utils import timezone
from apps.makerspaces.models import MakerspaceMembership, MakerspaceWaiver
from apps.makerspaces.waiver_state import current_acceptance
from .services_arrival_policy import arrival_eligible


def arrival_data(booking):
    space = booking.space
    membership = MakerspaceMembership.objects.filter(user_id=booking.member_id, makerspace_id=space.makerspace_id).first()
    waiver = MakerspaceWaiver.objects.filter(makerspace_id=space.makerspace_id, is_active=True).first()
    waiver_state = "not_required"
    if membership and waiver:
        waiver_state = "current" if current_acceptance(membership, active_waiver=waiver) else "missing"
    from apps.makerspaces.platform import feature_enabled
    return {
        "can_print_pass": (booking.arrived_at is not None
                           and booking.status in ("confirmed", "completed")
                           and feature_enabled(space.makerspace, "bookings.passes")),
        "booking_id": booking.pk, "display_name": booking.name, "space_name": space.name,
        "timezone": space.makerspace.timezone, "starts_at": booking.starts_at,
        "ends_at": booking.ends_at, "status": booking.status, "arrived_at": booking.arrived_at,
        "can_arrive": arrival_eligible(booking, now=timezone.now()),
        "can_reverse": booking.arrived_at is not None and booking.status in ("confirmed", "completed"),
        "waiver_state": waiver_state,
        "departed_at": booking.departed_at,
        "can_depart": _can_depart(booking),
    }


def _can_depart(booking):
    from .services_departure import can_depart
    return can_depart(booking, now=timezone.now(), source="staff")


def arrival_metrics(bookings):
    """BK-E calls with its already-authorized tenant/resource/date-filtered queryset.

    Counts current unreversed arrivals, including completed bookings. Reservation
    utilisation remains the existing calendar calculation; no measured-use duration.
    """
    return bookings.aggregate(
        arrived_reservations=Count("pk", filter=Q(arrived_at__isnull=False)),
        confirmed_without_recorded_arrival=Count("pk", filter=Q(status="confirmed", arrived_at__isnull=True)),
    )
