"""Local staff eligibility shared by browser sign-in and native grant creation.

Staff authority is a staff-TRACK row (one account per person); community rows never count.
"""

from apps.accounts import rbac
from apps.accounts.rbac_roles import additional_roles_prefetch
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.servability import servable_queryset


def has_local_staff_authority(user, *, makerspace_id=None):
    memberships = servable_queryset(
        MakerspaceMembership.staff_tracks.filter(user=user, status="active"),
        relation="makerspace",
    ).select_related("assigned_role").prefetch_related(additional_roles_prefetch())
    if makerspace_id is not None:
        memberships = memberships.filter(makerspace_id=makerspace_id)
    return any(rbac.actions_for_membership(row) for row in memberships)
