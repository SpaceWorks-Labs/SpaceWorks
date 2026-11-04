"""Grant built-in staff roles to an existing person (one account per person, #63).

The service the seeds use today and U-B's staff-roles API wraps: it never creates an
account. The person gets ONE staff-track row in the space holding the roles; machine
scopes follow the Machine Manager role. Authority is the role-assignment ceiling, so only
the superadmin grants the Space Manager role (#110, #111 Q14).
"""

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.accounts.staff_identity import is_person
from apps.audit import services as audit
from apps.makerspaces import limits
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole
from apps.makerspaces.role_assignments import can_assign_roles
from apps.makerspaces.role_membership_writes import replace_membership_roles, validated_roles


@transaction.atomic
def grant_staff_role(*, makerspace, user, roles, actor, machine_type_ids=()):
    """Create ``user``'s staff-track row in ``makerspace``; return it. Audited."""
    makerspace = Makerspace.objects.select_for_update(no_key=True).get(pk=makerspace.pk)
    actor = User.objects.filter(pk=getattr(actor, "pk", None)).first()
    if actor is None or not actor.is_active or actor.access_status != User.AccessStatus.ACTIVE:
        raise PermissionDenied()
    user = User.objects.select_for_update().get(pk=user.pk)
    if not is_person(user) or not user.is_active or user.is_walk_in or user.is_tenant_dump_stub:
        raise ValidationError({"user": "Staff roles are granted to an active personal account."})
    role_ids = {role.pk for role in roles}
    roles = list(MakerspaceRole.objects.filter(pk__in=role_ids, makerspace=makerspace))
    if not roles or len(roles) != len(role_ids):
        raise ValidationError({"roles": "Choose roles from this makerspace."})
    membership = MakerspaceMembership(makerspace=makerspace, user=user, track=MakerspaceMembership.Track.STAFF)
    roles = validated_roles(membership, roles)
    if any(role.slug == "member" for role in roles):
        raise ValidationError({"roles": "Choose built-in staff roles."})
    can_assign_roles(actor, makerspace, roles)
    if MakerspaceMembership.staff_tracks.filter(makerspace=makerspace, user=user).exists():
        raise ValidationError({"user": "This person already holds staff roles here."})
    limits.check_quota(makerspace, "staff", adding=1)
    membership.assigned_role = roles[0]
    membership.role = roles[0].legacy_role or MakerspaceMembership.Role.CUSTOM
    membership.save()
    replace_membership_roles(membership=membership, roles=roles, actor=actor,
                             reason="staff_role.granted", fresh_lifecycle=True)
    if "machine_manager" in {role.slug for role in roles}:
        from apps.machines.member_scope_services import set_member_machine_scope

        set_member_machine_scope(makerspace=makerspace, membership=membership, actor=actor,
                                 machine_type_ids=list(machine_type_ids))
    audit.record(actor, "staff_role.granted", makerspace=makerspace, target=user,
                 meta={"membership_id": membership.pk, "roles": [role.slug for role in roles],
                       "machine_type_ids": sorted(machine_type_ids)})
    return membership
