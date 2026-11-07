"""The single complete-set writer for membership roles and lifecycle cleanup.

Roles are keyed on the membership TRACK (one account per person): a community row holds
Member alone, a staff row holds built-in staff roles. Only the superadmin grants, changes
or revokes the Space Manager role (owner decisions #110, #111 Q14).
"""

from django.utils.translation import gettext
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.rbac_roles import membership_roles
from apps.accounts.rbac_superadmin import _is_superadmin
from apps.accounts.staff_identity import is_person
from apps.makerspaces.models import MakerspaceMembership, MembershipAdditionalRole
from apps.makerspaces.role_catalog import BUILTIN_ROLE_SLUGS, COMBINABLE_ROLE_SLUGS

SPACE_MANAGER = "space_manager"


def track_for_slugs(slugs):
    return (MakerspaceMembership.Track.COMMUNITY if set(slugs) == {"member"}
            else MakerspaceMembership.Track.STAFF)


def validated_roles(membership, roles):
    roles = {role.pk: role for role in roles}
    if not roles or None in roles:
        raise ValidationError({"role_ids": gettext("Choose at least one saved role.")})
    values = list(roles.values())
    slugs = {role.slug for role in values}
    if (any(role.makerspace_id != membership.makerspace_id for role in values)
            or not slugs <= set(BUILTIN_ROLE_SLUGS)
            or len(slugs) != len(values)):
        raise ValidationError({"role_ids": gettext("Choose built-in roles from this makerspace.")})
    if not slugs <= COMBINABLE_ROLE_SLUGS and len(values) != 1:
        raise ValidationError({"role_ids": gettext("Space Manager and Member must be assigned alone.")})
    # A saved row keeps its track for life (DB trigger); an unsaved template takes its
    # track from the roles, and the commit-time membership check proves the pairing.
    if membership.pk is not None and membership.track != track_for_slugs(slugs):
        raise ValidationError({"role_ids": gettext("The role set does not match this membership's track.")})
    if membership.user_id and not is_person(membership.user):
        raise ValidationError({"role_ids": gettext("Only a personal account holds memberships.")})
    order = {slug: index for index, slug in enumerate(BUILTIN_ROLE_SLUGS)}
    return sorted(values, key=lambda role: order[role.slug])


def assert_space_manager_change_allowed(actor, membership, roles=()):
    """Refuse a non-superadmin touching a Space Manager staff row or granting the role.

    Covers grant, change, revoke and restore: every writer of a staff row calls this
    with the row it touches (and, for role writes, the roles it will hold).
    """
    touches = SPACE_MANAGER in {role.slug for role in roles}
    if membership is not None and membership.pk is not None:
        touches = touches or SPACE_MANAGER in {role.slug for role in membership_roles(membership)}
    if touches and not _is_superadmin(actor):
        raise PermissionDenied(gettext("Only the platform administrator manages Space Managers."),
                               code="space_manager_superadmin_only")


def replace_membership_roles(*, membership, roles, actor, reason, fresh_lifecycle=False):
    """Replace the complete set; return evidence for the caller's audit entry.

    Takes NO locks. Caller must hold Makerspace FOR NO KEY UPDATE (or its
    existing stronger lock), then membership FOR UPDATE OF self. Existing
    user/invitation-first lock orders are preserved by their callers. A newly
    inserted membership is already exclusively owned by the transaction.
    ``reason`` identifies that caller's audited lifecycle operation.
    """
    roles = validated_roles(membership, roles)
    assert_space_manager_change_allowed(actor, membership, roles)
    before = [role.slug for role in membership_roles(membership)]
    primary, *additional = roles
    membership.assigned_role = primary
    membership.role = primary.legacy_role or MakerspaceMembership.Role.CUSTOM
    membership.save(update_fields=["assigned_role", "role"])
    links = MembershipAdditionalRole.objects.filter(membership=membership)
    if fresh_lifecycle:
        links.delete()
    else:
        links.exclude(role_id__in=[role.pk for role in additional]).delete()
    MembershipAdditionalRole.objects.bulk_create([
        MembershipAdditionalRole(membership=membership, role=role, assigned_by=actor)
        for role in additional
    ], ignore_conflicts=True)
    removed = []
    if fresh_lifecycle or "machine_manager" not in {role.slug for role in roles}:
        from apps.machines.models_membership_scope import MembershipMachineTypeScope

        scopes = MembershipMachineTypeScope.objects.filter(membership=membership)
        removed = sorted(scopes.values_list("machine_type_id", flat=True))
        scopes.delete()
    cache = getattr(membership, "_prefetched_objects_cache", {})
    cache.pop("additional_roles", None)
    cache.pop("machine_type_scopes", None)
    return {"before": before, "after": [role.slug for role in roles],
            "removed_machine_type_ids": removed}
