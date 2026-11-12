"""Track/window limits on staff-grant invitations (decision 221(i)).

A co-organizer whose `manage_team` is limited to a track or time window invites helpers
limited to the same track/window: the invite inherits the inviter's limit when none is
asked for, a narrower one is allowed, anything wider is refused by `can_delegate_helpers`.
Redemption writes the manual entitlement with the invite's limit. The shared grant lifecycle
has no limit parameters, so the limit in play travels in a context variable set by
`services_staff_grants` around the lifecycle call.
"""
from contextlib import contextmanager
from contextvars import ContextVar

from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import event_authority

_limit: ContextVar = ContextVar("event_staff_invite_limit", default=None)


@contextmanager
def limit_in_play(track_ids, valid_from, valid_until):
    token = _limit.set((sorted(set(track_ids or ())), valid_from, valid_until))
    try:
        yield
    finally:
        _limit.reset(token)


def current_limit(row=None):
    """The `(tracks, from, until)` to enforce: an invite row's own, else the one in play, else None."""
    if row is not None and getattr(row, "track_ids", None) is not None:
        return sorted(set(row.track_ids)), row.valid_from, row.valid_until
    return _limit.get()


def is_limited(limit):
    return bool(limit and (limit[0] or limit[1] or limit[2]))


def helper_role(permissions):
    from .contributions.authority import HELPER_PERMISSIONS
    for role, allowed in HELPER_PERMISSIONS.items():
        if permissions and set(permissions) <= allowed:
            return role
    return None


def can_delegate(actor, event, permissions, limit):
    from .contracts.services import DelegationScope
    from .contributions.authority import can_delegate_helpers
    role, (tracks, start, end) = helper_role(permissions), limit
    return bool(role and can_delegate_helpers(
        actor=actor, target=event, permissions=tuple(sorted(permissions)),
        scope=DelegationScope(event_id=event.pk, helper_role=role, track_ids=tuple(tracks),
                              valid_from=start, valid_until=end)))


def _inherited_tracks(actor, event, permissions):
    """Tracks every covering source of the actor shares; [] when some source is event-wide."""
    from django.db.models import Q
    from .contributions.authority import active_entitlements
    sources = active_entitlements(event_id=event.pk).filter(
        Q(event=event) | Q(series_id=event.series_id, series__isnull=False), grant__user=actor)
    shared = None
    for permission in permissions:
        covering = list(sources.filter(permissions__contains=[permission]).order_by("pk"))
        if not covering or any(not source.track_ids for source in covering):
            continue
        tracks = set(covering[0].track_ids)
        shared = tracks if shared is None else shared & tracks
    return sorted(shared or ())


def resolve(*, actor, event, permissions, track_ids=(), valid_from=None, valid_until=None):
    """Return the `(tracks, from, until)` an invite is issued with, or refuse it."""
    tracks = sorted({int(x) for x in track_ids or ()})
    if valid_from and valid_until and valid_until <= valid_from:
        raise ValidationError({"valid_until": gettext("The end must be after the start.")})
    if tracks and not event_authority._is_series(event):
        from .models import HackathonTrack
        known = set(HackathonTrack.objects.filter(event_id=event.pk, pk__in=tracks).values_list("pk", flat=True))
        if known != set(tracks):  # m3: a track id from another event would widen or dangle the limit
            raise ValidationError({"track_ids": gettext("Every track must belong to this event.")})
    if event_authority._is_series(event) or event_authority.can_manage_grants(actor, event):
        return tracks, valid_from, valid_until
    from .contributions.authority import inherited_window
    # 221(i): the limit is the inviter's manage_team grant as well as the helper permissions'.
    covering = (*permissions, "manage_team")
    tracks = tracks or _inherited_tracks(actor, event, covering)
    start, end = inherited_window(actor=actor, target=event, permissions=covering, track_ids=tracks)
    limit = (tracks, valid_from or start, valid_until or end)
    if not can_delegate(actor, event, permissions, limit):
        raise PermissionDenied(gettext("An invitation cannot be wider than your own track or time limit."))
    return limit


def my_limit(actor, event):
    """The inviter's own track/window limit, for prefilling the invite form.

    None when the actor is not a limited `manage_team` co-organizer (a full manager, a series,
    or no delegation right): nothing to inherit. Otherwise the same `(tracks, from, until)`
    `resolve` would apply to an invite that asks for no limit of its own.
    """
    if actor is None or event_authority._is_series(event) or event_authority.can_manage_grants(actor, event):
        return None
    # `permissions_for` answers unscoped questions only and drops a track-limited source, which is
    # exactly the co-organizer this prefill is for; ask the live entitlements directly.
    from django.db.models import Q
    from .contributions.authority import active_entitlements, inherited_window
    if not event_authority._active(actor) or not active_entitlements(event_id=event.pk).filter(
            Q(event=event) | Q(series_id=event.series_id, series__isnull=False),
            grant__user=actor, permissions__contains=["manage_team"]).exists():
        return None
    tracks = _inherited_tracks(actor, event, ("manage_team",))
    start, end = inherited_window(actor=actor, target=event, permissions=("manage_team",), track_ids=tracks)
    if not is_limited((tracks, start, end)):
        return None
    return {"track_ids": tracks, "valid_from": start, "valid_until": end}
