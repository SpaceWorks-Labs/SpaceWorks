"""Shared object and SQL predicates for valid membership role sets."""

from django.db.models import Exists, F, OuterRef, Prefetch, Q

from apps.makerspaces.role_catalog import BUILTIN_ROLE_SLUGS, COMBINABLE_ROLE_SLUGS


def membership_roles(membership):
    """Primary first, then valid additional roles in catalogue order.

    Status deliberately does not participate: revoked authority must still be
    inspectable by reattachment guards. Action resolvers check active status.
    """
    if membership is None or membership.assigned_role_id is None:
        return []
    primary = membership.assigned_role
    if primary.makerspace_id != membership.makerspace_id:
        return []
    if primary.slug not in COMBINABLE_ROLE_SLUGS:
        return [primary]
    roles = {primary.pk: primary}
    for link in membership.additional_roles.all():
        role = link.role
        if (role.makerspace_id == membership.makerspace_id
                and role.slug in COMBINABLE_ROLE_SLUGS):
            roles[role.pk] = role
    order = {slug: index for index, slug in enumerate(BUILTIN_ROLE_SLUGS)}
    additional = sorted(
        (role for role in roles.values() if role.pk != primary.pk),
        key=lambda role: (order[role.slug], role.pk),
    )
    return [primary, *additional]


def stored_actions_for_membership(membership):
    """Direct grants, without implications or an active-status requirement."""
    from .rbac_actions import ROLE_GRANTABLE_ACTIONS, _MEMBERSHIP_ROLE_ACTIONS

    if membership is None:
        return set()
    if membership.assigned_role_id is None:
        return set(_MEMBERSHIP_ROLE_ACTIONS.get(membership.role, ()))
    return {
        action for role in membership_roles(membership)
        if isinstance(role.granted_actions, list)
        for action in role.granted_actions
        if isinstance(action, str) and action in ROLE_GRANTABLE_ACTIONS
    }


def additional_role_exists(*, actions=(), slugs=(), role_ids=()):
    """Correlated SQL twin of the additional-role predicate above.

    The outer queryset must be MakerspaceMembership. Exists avoids multiplying
    rows when multiple roles satisfy one action.
    """
    from apps.makerspaces.models import MembershipAdditionalRole

    links = MembershipAdditionalRole.objects.filter(
        membership_id=OuterRef("pk"),
        membership__assigned_role__makerspace_id=F("membership__makerspace_id"),
        membership__assigned_role__slug__in=COMBINABLE_ROLE_SLUGS,
        role__makerspace_id=F("membership__makerspace_id"),
        role__slug__in=COMBINABLE_ROLE_SLUGS,
    )
    if slugs:
        links = links.filter(role__slug__in=slugs)
    if role_ids:
        links = links.filter(role_id__in=role_ids)
    if actions:
        grants = Q()
        for action in actions:
            grants |= Q(role__granted_actions__contains=[action])
        links = links.filter(grants)
    return Exists(links)


def direct_role_filter(actions):
    primary = Q()
    for action in actions:
        primary |= Q(assigned_role__granted_actions__contains=[action])
    return (
        Q(assigned_role__makerspace_id=F("makerspace_id")) & primary
    ) | Q(additional_role_exists(actions=actions))


def role_slug_filter(slug):
    return Q(
        assigned_role__makerspace_id=F("makerspace_id"), assigned_role__slug=slug,
    ) | Q(additional_role_exists(slugs=[slug]))


def additional_roles_prefetch():
    from apps.makerspaces.models import MembershipAdditionalRole

    return Prefetch("additional_roles", queryset=(
        MembershipAdditionalRole.objects.select_related("role")
    ))

