"""The one resolver for "is this person in the organization" (decision 293).

A person is an organization member when EITHER they hold an explicit, active
`OrganizationMembership` OR they hold an active community membership in a servable
makerspace the organization OWNS (owner link only: manager and affiliate links never
count). The second half is computed live from the space membership -- no copied rows -- so
leaving, expiry, revocation or restriction in the space ends it automatically.

This confers NO authority: it never creates a governor seat, a granted action or a local
role (`rbac.py` and `governance.py` do not read this module). It also never exposes who
the derived members are; the counts below are aggregates. The predicate itself lives in
`audience.eligible_accounts` (the events audience uses it), so a person is counted once
however many of those paths apply.
"""
from django.db.models import Exists, OuterRef

from apps.organizations.audience import eligible_accounts, owned_space_ids
from apps.organizations.models import OrganizationMembership

__all__ = ["org_member_accounts", "is_org_member", "org_member_count", "org_member_breakdown"]


def org_member_accounts(organization_ids, queryset=None):
    """Distinct active accounts in ANY of the organizations (explicit or derived)."""
    return eligible_accounts(list(organization_ids), queryset)


def is_org_member(user, organization) -> bool:
    if user is None or not getattr(user, "pk", None):
        return False
    return org_member_accounts([organization.pk]).filter(pk=user.pk).exists()


def org_member_count(organization) -> int:
    return org_member_accounts([organization.pk]).count()


def org_member_breakdown(organization) -> dict:
    """Counts only: total people, plus how many are explicit and how many derived-only."""
    members = org_member_accounts([organization.pk])
    explicit = OrganizationMembership.objects.filter(
        organization=organization, user_id=OuterRef("pk"), status="active")
    total = members.count()
    explicit_count = members.filter(Exists(explicit)).count()
    return {"total": total, "explicit": explicit_count, "derived_only": total - explicit_count,
            "owned_spaces": len(owned_space_ids([organization.pk]))}
