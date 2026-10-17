"""Staff creation and complete-set authority edits over the P1 writers."""

from rest_framework.exceptions import ValidationError

from apps.accounts.staff_accounts import create_staff_account
from apps.accounts.staff_account_policy import require_authority, scoped_space, target_account
from apps.accounts.services_staff_invitations import issue, onboarding_available
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.role_assignments import set_membership_roles
from apps.tenant_migration.gate_runtime import tenant_write


def resolve_roles(space, keys):
    if (not isinstance(keys, (list, tuple)) or not keys
            or any(not isinstance(key, str) or key == "member" for key in keys)
            or len(keys) != len(set(keys))):
        raise ValidationError({"roles": "Choose distinct built-in staff roles."})
    roles = list(space.roles.filter(slug__in=keys))
    if len(roles) != len(keys):
        raise ValidationError({"roles": "Choose built-in staff roles in this makerspace."})
    return roles


def create(actor, space_id, *, display_name, roles, email="", username=None, machine_type_ids=()):
    if not email and not username:
        raise ValidationError({"email": "Provide an email address or username."})
    invitation = None
    with tenant_write(space_id):
        space, actor = scoped_space(actor, space_id, lock=True)
        roles = resolve_roles(space, roles)
        require_authority(actor, space, roles=roles)
        account = create_staff_account(space, name=display_name, email=email, username=username or None,
            roles=roles, machine_type_ids=list(machine_type_ids), created_by=actor)
        if email and onboarding_available(space):
            invitation = issue(actor, space, account)
    return account, invitation


def change(actor, space_id, user_id, *, roles=None, machine_type_ids=None):
    from apps.machines.member_scope_services import set_member_machine_scope

    with tenant_write(space_id):
        space, actor = scoped_space(actor, space_id, lock=True)
        target = target_account(space, user_id)
        require_authority(actor, space, target=target)
        membership = MakerspaceMembership.objects.get(user=target, makerspace=space)
        if roles is not None:
            membership = set_membership_roles(makerspace=space, actor=actor,
                membership=membership, roles=resolve_roles(space, roles))
        if machine_type_ids is not None:
            from apps.accounts.staff_account_policy import role_keys
            if "machine_manager" in role_keys(membership):
                set_member_machine_scope(makerspace=space, actor=actor, membership=membership,
                                         machine_type_ids=machine_type_ids)
            elif machine_type_ids:
                raise ValidationError({"machine_type_ids": "Machine scopes require Machine Manager."})
    return target
