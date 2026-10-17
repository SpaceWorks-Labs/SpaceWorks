"""The single complete-set writer for membership roles and lifecycle cleanup."""

from rest_framework.exceptions import ValidationError

from apps.accounts.rbac_roles import membership_roles
from apps.makerspaces.models import MakerspaceMembership, MembershipAdditionalRole
from apps.makerspaces.role_catalog import BUILTIN_ROLE_SLUGS, COMBINABLE_ROLE_SLUGS


def validated_roles(membership, roles):
    roles = {role.pk: role for role in roles}
    if not roles or None in roles:
        raise ValidationError({"role_ids": "Choose at least one saved role."})
    values = list(roles.values())
    slugs = {role.slug for role in values}
    if (any(role.makerspace_id != membership.makerspace_id for role in values)
            or not slugs <= set(BUILTIN_ROLE_SLUGS)
            or len(slugs) != len(values)):
        raise ValidationError({"role_ids": "Choose built-in roles from this makerspace."})
    if not slugs <= COMBINABLE_ROLE_SLUGS and len(values) != 1:
        raise ValidationError({"role_ids": "Space Manager and Member must be assigned alone."})
    if membership.user_id:
        kind = membership.user.account_kind
        if ((kind == "member" and slugs != {"member"})
                or (kind == "staff" and ("member" in slugs
                    or membership.user.retired_at is not None
                    or membership.user.staff_makerspace_id != membership.makerspace_id))
                or kind == "platform"):
            raise ValidationError({"role_ids": "The role set does not match this account's kind and makerspace."})
    order = {slug: index for index, slug in enumerate(BUILTIN_ROLE_SLUGS)}
    return sorted(values, key=lambda role: order[role.slug])


def replace_membership_roles(*, membership, roles, actor, reason, fresh_lifecycle=False):
    """Replace the complete set; return evidence for the caller's audit entry.

    Takes NO locks. Caller must hold Makerspace FOR NO KEY UPDATE (or its
    existing stronger lock), then membership FOR UPDATE OF self. Existing
    user/invitation-first lock orders are preserved by their callers. A newly
    inserted membership is already exclusively owned by the transaction.
    ``reason`` identifies that caller's audited lifecycle operation.
    """
    roles = validated_roles(membership, roles)
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
