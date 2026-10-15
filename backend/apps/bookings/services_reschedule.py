"""Move an owned reservation while holding the same space lock as creation."""

from django.db import transaction
from django.utils import timezone

from apps.bookings.exceptions import BookingInvalidTransition


@transaction.atomic
def reschedule_booking(booking, *, actor, starts_at, ends_at):
    from apps.bookings.services_bookings import _locked_booking
    from apps.makerspaces.guards import require_module_locked
    from .access import require_booking_account

    space, locked = _locked_booking(booking)
    require_module_locked(space.makerspace, 'bookings')
    require_booking_account(actor, space.makerspace)
    from apps.accounts import rbac
    if rbac.personal_notification_membership_refused(actor, space.makerspace_id):
        raise BookingInvalidTransition('Revoked members may not reschedule bookings.')
    locked.space = space
    if locked.member_id != actor.pk:
        raise BookingInvalidTransition('Only the booking owner may reschedule it.')
    from .services_staff_edit import move_locked_booking
    return move_locked_booking(space, locked, actor=actor, starts_at=starts_at,
                               ends_at=ends_at, now=timezone.now())
