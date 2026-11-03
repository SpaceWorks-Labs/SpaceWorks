"""Grant and change staff roles on a person (one account per person, #63; Q9).

There is no staff-account creation any more. A role is granted to an existing community
member of the space (``grant``), or an email invite is sent that the invitee redeems
while signed in (``services_staff_invitations``). ``change`` replaces the complete role set
and machine scopes. Revoke and restore live in ``staff_account_lifecycle``.
Every writer runs inside ``staff_write`` (tenant gate) and is audited.
"""

from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.accounts.staff_account_policy import (
    ALREADY_STAFF, NOT_COMMUNITY_MEMBER, StaffRoleRefused, check_staff_quota, require_authority, role_keys, scoped_space, staff_write, target_row,
)
from apps.audit.services import record
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.role_catalog import BUILTIN_ROLE_SLUGS

MACHINE_MANAGER = "machine_manager"


def resolve_roles(space, keys):
    """Distinct built-in staff roles of this space (custom roles stay off staff rows, Q6)."""
    if (not isinstance(keys, (list, tuple)) or not keys
            or any(not isinstance(key, str) or key == "member" or key not in BUILTIN_ROLE_SLUGS for key in keys)
            or len(keys) != len(set(keys))):
        raise ValidationError({"roles": "Choose distinct built-in staff roles."})
    roles = list(space.roles.filter(slug__in=keys))
    if len(roles) != len(keys):
        raise ValidationError({"roles": "Choose built-in staff roles in this makerspace."})
    return roles


def resolve_machine_types(space, roles, machine_type_ids):
    from apps.machines.member_scope_services import assignable_machine_types

    ids = list(machine_type_ids or ())
    if any(type(value) is not int or value <= 0 for value in ids) or len(set(ids)) != len(ids):
        raise ValidationError({"machine_type_ids": "Use distinct positive integer ids."})
    if ids and MACHINE_MANAGER not in {role.slug for role in roles}:
        raise ValidationError({"machine_type_ids": "Machine scopes require the Machine Manager role."})
    if len(set(assignable_machine_types(space).filter(pk__in=ids).values_list("pk", flat=True))) != len(ids):
        raise ValidationError({"machine_type_ids": "Choose machine types of this makerspace."})
    return sorted(ids)


def is_community_member(space, user):
    return MakerspaceMembership.objects.filter(makerspace=space, user=user, status="active").exists()


def grant(actor, space_id, *, user_id, roles, machine_type_ids=()):
    """Give an active community member of this space a staff-track row."""
    from apps.makerspaces.staff_role_grants import grant_staff_role

    with staff_write(space_id):
        space, actor = scoped_space(actor, space_id, lock=True)
        roles = resolve_roles(space, roles)
        target = User.objects.filter(pk=user_id).first()
        if target is None or not is_community_member(space, target):
            raise StaffRoleRefused(NOT_COMMUNITY_MEMBER,
                                   "Staff roles are granted to community members of this makerspace. Invite by email instead.")
        require_authority(actor, space, target=target, roles=roles)
        if MakerspaceMembership.staff_tracks.filter(makerspace=space, user=target).exists():
            raise StaffRoleRefused(ALREADY_STAFF, "This person already has a staff row here; change or restore it.")
        scopes = resolve_machine_types(space, roles, machine_type_ids)
        check_staff_quota(space)
        membership = grant_staff_role(makerspace=space, user=target, roles=roles, actor=actor,
                                      machine_type_ids=scopes)
    from apps.accounts.staff_role_notices import notify_granted
    notify_granted(membership)
    return membership


def _demoted(before_actions, row):
    from apps.accounts.rbac_actions import actions_for_membership
    return not before_actions <= set(actions_for_membership(row))


def change(actor, space_id, membership_id, *, roles=None, machine_type_ids=None):
    """Replace the role set and/or the machine scopes of one staff row."""
    from apps.accounts.rbac_actions import actions_for_membership
    from apps.accounts.services_staff_grants import revoke_staff_grants
    from apps.machines.member_scope_services import current_scope, set_member_machine_scope
    from apps.makerspaces.role_assignments import set_membership_roles

    with staff_write(space_id):
        space, actor = scoped_space(actor, space_id, lock=True)
        row = target_row(space, membership_id, lock=True)
        new_roles = resolve_roles(space, roles) if roles is not None else None
        require_authority(actor, space, target=row.user, roles=new_roles)
        if row.status != "active":
            raise ValidationError({"detail": "Restore this staff row before changing it."})
        roles_before, scopes_before = role_keys(row), current_scope(row)
        before_actions = set(actions_for_membership(row))
        if new_roles is not None:
            # set_membership_roles keeps the last Space Manager (protect_last_manager).
            row = set_membership_roles(makerspace=space, actor=actor, membership=row, roles=new_roles)
        if machine_type_ids is not None:
            scopes = resolve_machine_types(space, new_roles or list(_roles(row)), machine_type_ids)
            if MACHINE_MANAGER in role_keys(row):
                set_member_machine_scope(makerspace=space, actor=actor, membership=row, machine_type_ids=scopes)
        row = target_row(space, row.pk)
        record(actor, "staff_role.changed", makerspace=space, target=row.user,
               meta={"membership_id": row.pk, "roles_before": roles_before, "roles_after": role_keys(row),
                     "machine_type_ids_before": scopes_before, "machine_type_ids_after": current_scope(row)})
        if _demoted(before_actions, row):
            revoke_staff_grants(row.user, space.pk, reason="staff_role.changed", actor=actor)
    return row


def _roles(row):
    from apps.accounts.rbac_roles import membership_roles
    return membership_roles(row)
