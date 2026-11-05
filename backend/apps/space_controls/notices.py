"""What a signed-in account must be told about its spaces: live announcements, and
which of its spaces are paused or read-only (the frontend banner and paused page).

Reads the person's own membership rows on both tracks (``both_tracks``: a whole
relation to a space, never authority). A paused space's private reason is the
superadmin's; everyone else gets the generic sentence.
"""

from django.utils import timezone

from apps.accounts.platform_authority import is_platform_superadmin
from apps.makerspaces.models import Makerspace, MakerspaceMembership

from .announcements import live_q
from .models import PlatformAnnouncement, SpaceControlState
from .services_access import PAUSED_REASON


def _relations(user):
    rows = MakerspaceMembership.both_tracks().filter(user=user, status="active").values_list(
        "makerspace_id", "track")
    staff, community = set(), set()
    for space_id, track in rows:
        (staff if track == MakerspaceMembership.Track.STAFF else community).add(space_id)
    return staff, community


def notices_for(user, now=None):
    now = now or timezone.now()
    superadmin = is_platform_superadmin(user)
    staff, community = (set(), set()) if superadmin else _relations(user)
    mine = staff | community
    if superadmin:
        # The superadmin works in every space, so every paused or read-only one is listed.
        mine = set(Makerspace.objects.filter(lifecycle_state=Makerspace.LifecycleState.SUSPENDED)
                   .values_list("pk", flat=True))
        mine |= set(SpaceControlState.objects.filter(read_only_at__isnull=False).values_list("makerspace_id", flat=True))
    rows = PlatformAnnouncement.objects.filter(live_q(now)).prefetch_related("targets").order_by("-starts_at")
    announcements = []
    for row in rows:
        everywhere = row.audience == PlatformAnnouncement.Audience.ALL_SPACES
        targets = {target.makerspace_id for target in row.targets.all()}
        # Only ever the VIEWER's own spaces: never another target space's id (#195).
        as_member = (community if row.show_to_members else set()) & (community if everywhere else targets)
        as_staff = staff & (staff if everywhere else targets)
        if superadmin or as_member or as_staff:
            announcements.append({
                "id": row.pk, "title": row.title, "body": row.body, "severity": row.severity,
                "starts_at": row.starts_at, "ends_at": row.ends_at,
                "makerspace_ids": sorted(as_staff | as_member) if not superadmin else sorted(targets),
                "member_makerspace_ids": sorted(as_member),
            })
    return {"announcements": announcements, "spaces": _space_states(mine, superadmin)}


def _space_states(space_ids, superadmin):
    if not space_ids:
        return []
    result = []
    states = {row.makerspace_id: row for row in SpaceControlState.objects.filter(makerspace_id__in=space_ids)}
    for space in Makerspace.objects.filter(pk__in=space_ids).order_by("name", "pk"):
        state = states.get(space.pk)
        if space.lifecycle_state == Makerspace.LifecycleState.SUSPENDED:
            since = state.suspended_at if state else None
            reason = (state.suspension_reason if superadmin and state else PAUSED_REASON)
            result.append({"id": space.pk, "name": space.name, "slug": space.slug, "state": "suspended",
                           "reason": reason, "since": since})
        elif state is not None and state.read_only_at is not None:
            result.append({"id": space.pk, "name": space.name, "slug": space.slug, "state": "read_only",
                           "reason": state.read_only_reason, "since": state.read_only_at})
    return result
