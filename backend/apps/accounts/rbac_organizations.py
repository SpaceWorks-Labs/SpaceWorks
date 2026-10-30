"""Organization-derived RBAC action authority."""

import logging

from django.db.models import Q

from .staff_identity import person_q
from .rbac_actions import (
    ORGANIZATION_GRANTABLE_ACTIONS,
    actions_for_organization_membership,
    actions_satisfying,
    expand_implied_actions,
)


def _organization_authority_memberships(actor, *, makerspace_ids=None):
    """Active organization grants whose linked makerspace may serve traffic."""
    from apps.makerspaces.servability import servable_q
    from apps.organizations.models import OrganizationMembership

    # Native device sessions are membership-only (INVARIANTS: "Native device payloads stay
    # membership-only"). Cutting org authority here, the single source every org branch
    # reads, closes body-targeted requests too -- not just the URL/header pinning that
    # SpaceWorksJWTAuthentication can check.
    from apps.accounts.native_session import is_native_session

    if is_native_session(actor):
        return OrganizationMembership.objects.none()
    # Organization authority belongs to the person, never a platform account or shell.
    filters = (
        person_q("user__")
        & Q(
            user=actor,
            status=OrganizationMembership.Status.ACTIVE,
            organization__is_active=True,
        )
        & servable_q("organization__makerspace_links__makerspace")
    )
    if makerspace_ids is not None:
        filters &= Q(
            organization__makerspace_links__makerspace_id__in=makerspace_ids
        )
    return OrganizationMembership.objects.filter(filters)


def has_any_org_authority(actor) -> bool:
    """Return whether one indexed query finds any usable organization grant."""
    if actor is None or not getattr(actor, "is_authenticated", False):
        return False
    granted_filter = Q()
    for action in ORGANIZATION_GRANTABLE_ACTIONS:
        granted_filter |= Q(granted_actions__contains=[action])
    return _organization_authority_memberships(actor).filter(
        granted_filter
    ).exists()


def _org_actions_for(actor, makerspace_id) -> set:
    """Return actions active organization grants confer in one makerspace.

    Grants reach every servable linked makerspace; the servability filter lives in
    `_organization_authority_memberships`, so every consumer inherits it.
    """
    if actor is None or not getattr(actor, "is_authenticated", False):
        return set()
    granted = set()
    memberships = _organization_authority_memberships(
        actor, makerspace_ids=[makerspace_id]
    ).select_related("organization")
    for membership in memberships:
        granted.update(actions_for_organization_membership(membership))
    return granted


def _org_scope_for_action(actor, action) -> set:
    """Return makerspace ids where an active organization grant satisfies action."""
    if actor is None or not getattr(actor, "is_authenticated", False):
        return set()
    satisfying = actions_satisfying(action) & ORGANIZATION_GRANTABLE_ACTIONS
    if not satisfying:
        return set()
    granted_filter = Q()
    for granted_action in satisfying:
        granted_filter |= Q(granted_actions__contains=[granted_action])
    rows = (
        _organization_authority_memberships(actor)
        .filter(granted_filter)
        .values_list(
            "granted_actions",
            "organization__makerspace_links__makerspace_id",
        )
    )
    scope = set()
    for value, makerspace_id in rows:
        if not isinstance(value, list):
            logging.getLogger("apps.accounts.rbac").warning(
                "Ignoring malformed granted actions on an organization membership."
            )
            continue
        expanded = expand_implied_actions({
            granted_action
            for granted_action in value
            if (
                isinstance(granted_action, str)
                and granted_action in ORGANIZATION_GRANTABLE_ACTIONS
            )
        })
        if action in expanded:
            scope.add(makerspace_id)
    return scope
