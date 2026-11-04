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
    held = _scopes.get()
    if held is not None:
        if not set(tenants) <= set(held[0]) or not set(accounts) <= set(held[1]):
            raise RuntimeError("Cannot extend programme fences below resource locks.")
        yield
        return
    from apps.encryption.preparation import locked_domain
    with account_fences(accounts, tenants, allow_erased=True), locked_domain():
        token = _scopes.set((tenants, accounts))
        try:
            yield
        finally:
            _scopes.reset(token)


def assert_lock_context(locks):
    if not connection.in_atomic_block or _scopes.get() != (tuple(locks.tenant_ids), tuple(locks.account_ids)):
        raise RuntimeError("Programme call requires the predeclared transaction/fence context.")


def current_locks(event_id):
    from .contracts.providers import LockedContext
    held = _scopes.get()
    if not connection.in_atomic_block or held is None:
        raise RuntimeError("Acquire programme fences before event locks.")
    return LockedContext(event_id=event_id, tenant_ids=held[0], account_ids=held[1])


def event_scopes(*, event_id, account_ids=()):
    """Nonlocking discovery, repeated after the event lock; never expand fences."""
    from .models import Event, EventRegistration
    from .hackathons.admission_models import HackathonApplication
    from .hackathons.review_models import ApplicationReviewAssignment
    from .contributions.models_roles import EventRoleAssignment
    from .contributions.models_roles import EventGrantEntitlement, EventRolePosting
    from .models_staff_grants import EventStaffGrant, EventStaffGrantInvite
    from .profile_photos.models import EventMemberPresentation
    from .models_certificates import EventAttendanceCertificate
    from .organization_audience import candidate_ids
    from apps.organizations.audience import owned_space_ids

    event = Event.objects.get(pk=event_id)
    tenants = {event.makerspace_id}
    tenants.update(event.collaborators.filter(status="accepted").values_list("makerspace_id", flat=True))
    tenants.update(owned_space_ids(candidate_ids(event)))
    accounts = set(account_ids)
    for model, fields in ((EventStaffGrant, ("user_id", "granted_by_id")),
            (EventStaffGrantInvite, ("created_by_id", "redeemed_by_id")),
            (EventGrantEntitlement, ("created_by_id",)),
            (EventRoleAssignment, ("approved_by_id",)),
            (EventRolePosting, ("permission_issuer_id",))):
        rows = model.objects.filter(event_id=event_id)
        if model in (EventStaffGrant, EventStaffGrantInvite, EventGrantEntitlement) and event.series_id:
            from django.db.models import Q
            rows = model.objects.filter(Q(event_id=event_id) | Q(series_id=event.series_id))
        for field in fields:
            accounts.update(rows.values_list(field, flat=True))
    for model, field in ((EventRegistration, "member_id"), (HackathonApplication, "member_id"),
                         (EventRoleAssignment, "member_id"), (ApplicationReviewAssignment, "reviewer_id")):
        accounts.update(model.objects.filter(event_id=event_id).values_list(field, flat=True))
    for field in ("registered_via_makerspace_id", "payment_via_makerspace_id"):
        tenants.update(EventRegistration.objects.filter(event_id=event_id).values_list(field, flat=True))
    selections = EventMemberPresentation.objects.filter(event_id=event_id)
    tenants.update(selections.values_list("selected_profile__membership__makerspace_id", flat=True))
    tenants.update(selections.values_list("selected_membership__makerspace_id", flat=True))
    accounts.update(selections.values_list("member_id", flat=True))
    accounts.update(EventAttendanceCertificate.objects.filter(event_id=event_id)
                    .values_list("recipient_member_id", flat=True))
    return tuple(sorted(tenants - {None})), tuple(sorted(accounts - {None}))


def lock_event(*, event_id, account_ids=()):
    """Canonical admission event/tenant lock adapter. Authority follows this call."""
    from .models import Event, EventSeries
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.guards import require_module_locked
    from .programme.commands import ProgrammeConflict

    locks = current_locks(event_id)
    series_id = Event.objects.values_list("series_id", flat=True).get(pk=event_id)
    if series_id:
        EventSeries.objects.select_for_update().get(pk=series_id)
    event = Event.objects.select_for_update().get(pk=event_id)
    tenants, accounts = event_scopes(event_id=event_id, account_ids=account_ids)
    if (event.series_id != series_id or not set(tenants) <= set(locks.tenant_ids)
            or not set(accounts) <= set(locks.account_ids)):
        raise ProgrammeConflict("scope_changed", "Event participants changed. Retry the command.")
    list(Makerspace.objects.select_for_update().filter(pk__in=locks.tenant_ids).order_by("pk"))
    tenants, accounts = event_scopes(event_id=event_id, account_ids=account_ids)
    if not set(tenants) <= set(locks.tenant_ids) or not set(accounts) <= set(locks.account_ids):
        raise ProgrammeConflict("scope_changed", "Event participants changed. Retry the command.")
    event.makerspace = require_module_locked(event.makerspace_id, "events")
    return event


def lock_membership_sources(organization_ids, user_ids, space_ids):
    """Programme variant: account fences replace locks on User/key rows."""
    from apps.organizations.models import OrganizationMakerspace
    for user_id in user_ids:
        assert_account_fence_held(user_id)
    list(Organization.objects.select_for_update().filter(pk__in=organization_ids).order_by("pk"))
    list(OrganizationMakerspace.objects.select_for_update().filter(makerspace_id__in=space_ids).order_by("pk"))
    list(OrganizationMembership.objects.select_for_update().filter(
        organization_id__in=organization_ids, user_id__in=user_ids).order_by("pk"))
    list(MakerspaceMembership.objects.select_for_update().filter(
        makerspace_id__in=space_ids, user_id__in=user_ids).order_by("pk"))


def lock_admission_sources(event, user_ids=(), *, extra_space_ids=(), include_authority=False):
    from .organization_audience import AUDIENCE, AudienceChanged, candidate_ids
    from apps.organizations.audience import owned_space_ids
    from apps.makerspaces.models import Makerspace
    if event.registration_audience != AUDIENCE:
        return
    locks = current_locks(event.pk)
    organizations = candidate_ids(event)
    spaces = owned_space_ids(organizations) | {event.makerspace_id} | set(extra_space_ids)
    if not spaces <= set(locks.tenant_ids):
        raise AudienceChanged()
    list(Makerspace.objects.select_for_update().filter(pk__in=spaces).order_by("pk"))
    if candidate_ids(event) != organizations or not owned_space_ids(organizations) <= spaces:
        raise AudienceChanged()
    authority = authority_sources(event)[3] if include_authority else set()
    lock_membership_sources(organizations | authority, set(user_ids) - {None}, spaces)
    if candidate_ids(event) != organizations or not owned_space_ids(organizations) <= spaces:
        raise AudienceChanged()


def lock_authority(actor, target):
    """Stabilize membership, organization and grant sources, without account row locks."""
    if actor is None:
        return None
    assert_account_fence_held(actor.pk)
    fresh = User.objects.filter(pk=actor.pk).first()
    if fresh is None:
        return None
    from apps.accounts.claim_sessions import carry_claim_context
    carry_claim_context(actor, fresh)
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
