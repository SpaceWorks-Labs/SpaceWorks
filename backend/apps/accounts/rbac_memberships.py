"""Membership-only RBAC identity helpers: staff authority reads the STAFF track only."""


from apps.accounts.rbac_roles import additional_roles_prefetch
from .membership_context import (
    valid_community_membership_q, valid_membership_context, valid_staff_membership_q,
)
from apps.makerspaces.models import MakerspaceMembership


def _staff_rows(actor):
    if getattr(actor, "pk", None) is None:
        return MakerspaceMembership.staff_tracks.none()
    return MakerspaceMembership.staff_tracks.filter(user_id=actor.pk)


def _scope_ids(actor):
    """Active, valid rows on either track: the spaces a person belongs to or staffs."""
    if getattr(actor, "pk", None) is None:
        return set()
    community = MakerspaceMembership.objects.filter(
        valid_community_membership_q(), user_id=actor.pk, status="active")
    staff = _staff_rows(actor).filter(valid_staff_membership_q(), status="active")
    return {*community.values_list("makerspace_id", flat=True),
            *staff.values_list("makerspace_id", flat=True)}


def membership_role(actor, makerspace_id):
    """Return the actor's staff-track MakerspaceMembership.role here, or None."""
    membership = _staff_rows(actor).filter(status="active", makerspace_id=makerspace_id).first()
    return membership.role if valid_membership_context(membership) else None


def _membership_for(actor, makerspace_id) -> MakerspaceMembership | None:
    """The actor's active staff-track row; community rows never confer actions."""
    return _staff_rows(actor).select_related("assigned_role").prefetch_related(
        additional_roles_prefetch(),
    ).filter(status="active", makerspace_id=makerspace_id).first()


def _membership_is_space_manager(membership) -> bool:
    if not valid_membership_context(membership) or membership.track != MakerspaceMembership.Track.STAFF:
        return False
    if membership.assigned_role_id is not None:
        role = membership.assigned_role
        return bool(
            role
            and role.makerspace_id == membership.makerspace_id
            and role.legacy_role == "space_manager"
        )
    return membership.role == MakerspaceMembership.Role.SPACE_MANAGER
