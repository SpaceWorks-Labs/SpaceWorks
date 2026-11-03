"""COMMUNITY on the public stats page (#170): four counts, never a name.

Each count is gated by its own module (membership, bookings, presence) and its public
surface; a module that is off leaves its count `None`, and the section is hidden when all
three are off. Every count passes the small-number suppression.
"""

from apps.makerspaces.editions import public_surface_available
from apps.makerspaces.platform import module_enabled

from .public_stats_period import in_window, suppressed


def _on(makerspace, module):
    return public_surface_available(module) and module_enabled(makerspace, module)


def _members(makerspace):
    # The same population the public page builder's member count publishes.
    from apps.accounts.staff_identity import person_q
    from apps.makerspaces.models import MakerspaceMembership
    return MakerspaceMembership.objects.filter(
        person_q("user__"), makerspace=makerspace, status="active", user__is_active=True,
        user__access_status="active", user__is_tenant_dump_stub=False)


def _bookings(makerspace, window):
    from apps.bookings.models import Booking
    rows = Booking.objects.filter(space__makerspace=makerspace,
                                  status__in=(Booking.Status.CONFIRMED, Booking.Status.COMPLETED))
    return in_window(rows, "starts_at", window).count()


def _checkins(makerspace, window):
    from apps.presence.models import PresenceSession
    return in_window(PresenceSession.objects.filter(makerspace=makerspace), "started_at", window).count()


def community_section(makerspace, window):
    membership, bookings, presence = (_on(makerspace, key) for key in ("membership", "bookings", "presence"))
    if not (membership or bookings or presence):
        return None
    members = _members(makerspace) if membership else None
    return {
        "active_members": suppressed(members.count()) if membership else None,
        "new_members": suppressed(in_window(members, "created_at", window).count()) if membership else None,
        "bookings": suppressed(_bookings(makerspace, window)) if bookings else None,
        "checkins": suppressed(_checkins(makerspace, window)) if presence else None,
    }


def community_metrics(section):
    return {f"community.{key}": value for key, value in section.items() if value is not None}
