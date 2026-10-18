"""Shared programme lock order: source boundary, fences, event, tenant, authority.

User/key rows are read again for live policy, never locked after an Event row.
Account fencing serializes prepared Saved details work with account erasure.
"""
from contextlib import contextmanager
from contextvars import ContextVar

from django.db import connection

from apps.accounts.models import User
from apps.encryption.account_write_fence import account_fences, assert_account_fence_held
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole, MembershipAdditionalRole
from apps.organizations.models import Organization, OrganizationMembership

from .staff_grant_locks import authority_sources

_scopes = ContextVar("programme_lock_scopes", default=None)


@contextmanager
def fences(*, tenant_ids, account_ids):
    tenants = tuple(sorted(set(map(int, tenant_ids))))
    accounts = tuple(sorted(set(map(int, account_ids))))
    with account_fences(accounts, tenants):
        token = _scopes.set((tenants, accounts))
        try:
            yield
        finally:
            _scopes.reset(token)


def assert_lock_context(locks):
    if not connection.in_atomic_block or _scopes.get() != (tuple(locks.tenant_ids), tuple(locks.account_ids)):
        raise RuntimeError("Programme call requires the predeclared transaction/fence context.")


def lock_authority(actor, target):
    """Stabilize membership, organization and grant sources, without account row locks."""
    if actor is None:
        return None
    assert_account_fence_held(actor.pk)
    fresh = User.objects.filter(pk=actor.pk).first()
    if fresh is None:
        return None
    links, events, series, organization_ids = authority_sources(target)
    list(Organization.objects.select_for_update().filter(pk__in=organization_ids).order_by("pk"))
    memberships = list(MakerspaceMembership.objects.select_for_update().filter(
        user_id=fresh.pk, makerspace_id=target.makerspace_id,
    ).order_by("pk"))
    additions = list(MembershipAdditionalRole.objects.select_for_update().filter(
        membership__in=memberships,
    ).order_by("pk"))
    role_ids = {row.assigned_role_id for row in memberships if row.assigned_role_id}
    role_ids.update(row.role_id for row in additions)
    list(MakerspaceRole.objects.select_for_update().filter(pk__in=role_ids).order_by("pk"))
    for rows in (links, events, series):
        list(rows.select_for_update().order_by("pk"))
    list(OrganizationMembership.objects.select_for_update().filter(
        user_id=fresh.pk, organization_id__in=organization_ids,
    ).order_by("pk"))
    from .models_staff_grants import EventStaffGrant
    from .contributions.models_roles import EventGrantEntitlement
    grants = EventStaffGrant.objects.filter(user_id=fresh.pk, makerspace_id=target.makerspace_id)
    ids = list(grants.select_for_update().order_by("pk").values_list("pk", flat=True))
    list(EventGrantEntitlement.objects.select_for_update().filter(grant_id__in=ids).order_by("pk"))
    return fresh
