"""Decision 223: the guest-pass arm of the member guards.

`require_member_or_guest` answers "may this person act here right now": a member goes
through exactly the existing guards; a non-member is admitted only by a live, payment-cleared
guest pass (`active_pass_for`), and then only for what the pass's frozen entitlements allow.
Check-in stays what it was: the location presence session plus the staff desk. A pass never
opens a door; it only changes WHO may check in and WHAT they may do once checked in.

* `planning=True` is for requests staff will review later (equipment planning before an
  event): no presence session and no waiver, which belong to the moment of issue at the desk.
  A pass that is issued but not yet started still counts, so a registrant can be planned for.
* `borrow=True` additionally enforces the borrowing mode (`none` refuses).
* `require_guest_waiver` closes gap G2: an on-site non-member needs the CURRENT waiver on
  their pass or on a live event registration, when the space requires it.
"""
from dataclasses import replace

from django.utils import timezone

from apps.makerspaces.guest_pass_policy import GuestPassError
from apps.makerspaces.guest_pass_queries import active_pass_for, pass_entitlements, require_waiver
from apps.makerspaces.models import GuestPass, MakerspaceWaiver
from apps.presence.guard import (
    ActiveMemberPresence, MemberPresenceRequired, PresenceRequired, WaiverAcceptanceRequired,
    _require_active_identity, require_active_member, require_active_member_presence,
)
from apps.presence.models import PresenceSession
from apps.separability.registry import runtime_active


def registration_consent(user, makerspace):
    """True when a live event registration here carries the current waiver (host consent)."""
    waiver = MakerspaceWaiver.objects.filter(makerspace=makerspace, is_active=True).first()
    if waiver is None:
        return True
    try:
        from apps.events.models import EventRegistration
    except (ImportError, LookupError):  # events tombstoned
        return False
    return EventRegistration.objects.filter(
        event__makerspace=makerspace, member=user, status__in=("registered", "attended"),
        host_waiver=waiver, host_waiver_version_accepted=waiver.version,
    ).exists()


def require_guest_waiver(user, makerspace, guest_pass=None):
    """The non-member waiver gate: the pass stamp, else a registration stamp, else refuse."""
    try:
        require_waiver(user, makerspace, guest_pass)
    except WaiverAcceptanceRequired:
        if registration_consent(user, makerspace):
            return
        raise


def planning_pass_for(user, makerspace, at=None):
    """A live pass whose window has not ended (it may start later), for planning only."""
    from apps.makerspaces.guest_pass_policy import guest_passes_on
    from apps.makerspaces.guest_pass_queries import payment_cleared
    if user is None or not getattr(user, "is_active", False) or user.access_status != "active":
        return None
    if not guest_passes_on(makerspace):
        return None
    rows = GuestPass.objects.select_related("product").filter(
        makerspace=makerspace, holder=user, status__in=GuestPass.LIVE_STATUSES,
        valid_until__gt=at or timezone.now()).order_by("valid_from", "pk")
    return next((row for row in rows if payment_cleared(row)), None)


def open_session(user, makerspace):
    now = timezone.now()
    return PresenceSession.objects.filter(
        member=user, makerspace=makerspace, ended_at__isnull=True, expires_at__gt=now,
    ).order_by("-started_at", "-id").first()


def require_borrowing(guest_pass, *, take_home=False):
    """Refuse a borrow the pass does not allow; returns the entitlements."""
    ent = pass_entitlements(guest_pass)
    if ent.borrow == "none":
        raise GuestPassError("guest_pass_no_borrow", "Your guest pass does not include borrowing.", status_code=403)
    if take_home and ent.on_site_only:
        raise GuestPassError("guest_pass_on_site_only",
                             "Your guest pass only covers using items on site; return them before the pass ends.",
                             status_code=403)
    return ent


def require_member_or_guest(user, makerspace, *, presence=True, borrow=False, planning=False):
    """Admit a member (existing guards) or a pass holder; returns `ActiveMemberPresence`.

    For a pass holder `.membership` is None and `.guest_pass` is the pass. Raises the original
    `MemberPresenceRequired` when the person is neither (so refusals are unchanged without a pass).
    """
    if borrow:  # decision 223 (k): a minor borrows only where the space allows it and a guardian consented
        from apps.makerspaces.minors_guard import require_minor_clearance
        require_minor_clearance(user, makerspace, "borrow")
    member_guard = require_active_member_presence if presence and not planning else require_active_member
    try:
        return member_guard(user, makerspace)
    except MemberPresenceRequired:
        guest_pass = planning_pass_for(user, makerspace) if planning else active_pass_for(user, makerspace)
        if guest_pass is None:
            raise
    _require_active_identity(user, makerspace)
    if borrow:
        require_borrowing(guest_pass)
    if planning:
        return ActiveMemberPresence(None, None, None, guest_pass)
    require_guest_waiver(user, makerspace, guest_pass)
    session = None
    if presence and runtime_active("presence"):
        from apps.makerspaces.platform import module_enabled
        if module_enabled(makerspace, "presence"):
            session = open_session(user, makerspace)
            if session is None:
                raise PresenceRequired()
    return replace(ActiveMemberPresence(None, None, session), guest_pass=guest_pass)
