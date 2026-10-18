"""Live entitlement predicates consumed by every G event-authority query path."""
from django.db.models import F, Q
from django.utils import timezone
from apps.events import event_authority
from apps.events.contracts.services import DelegationScope
from .models_roles import EventGrantEntitlement
from .ports import ports

HELPER_PERMISSIONS = {
    "volunteer": frozenset({"check_in", "publish_schedule"}),
    "mentor": frozenset({"mentor_queue"}),
    "judge": frozenset({"judge"}),
    "sponsor_rep": frozenset({"view_sponsor_track"}),
}


def active_entitlements(*, at=None):
    at = at or timezone.now()
    return EventGrantEntitlement.objects.filter(
        revoked_at__isnull=True, grant__revoked_at__isnull=True,
        makerspace_id=F("grant__makerspace_id"),
        grant__user__account_kind="member", grant__user__is_active=True,
        grant__user__access_status="active", grant__user__is_tenant_dump_stub=False,
    ).filter(Q(event_id=F("grant__event_id"), event__makerspace_id=F("makerspace_id"))
        | Q(source_kind="manual", series_id=F("grant__series_id"), series__makerspace_id=F("makerspace_id"))
    ).filter(Q(valid_from__isnull=True) | Q(valid_from__lte=at)).filter(
        Q(valid_until__isnull=True) | Q(valid_until__gt=at)).filter(
        Q(source_kind="manual")
        | Q(source_kind="role", role_assignment__state="approved",
            role_assignment__imported_inert=False, role_assignment__event_id=F("event_id"),
            role_assignment__makerspace_id=F("makerspace_id"),
            role_assignment__member_id=F("grant__user_id"))
        | Q(source_kind="shift", shift_signup__state="approved",
            shift_signup__assignment__state="approved", shift_signup__assignment__imported_inert=False,
            shift_signup__assignment__member_id=F("grant__user_id"),
            shift_signup__assignment__event_id=F("event_id"),
            shift_signup__makerspace_id=F("makerspace_id"),
            shift_signup__assignment__makerspace_id=F("makerspace_id"),
            shift_signup__event_id=F("event_id"), shift_signup__member_id=F("grant__user_id"),
            shift_signup__shift__state="open", shift_signup__shift__kind="volunteer",
            shift_signup__shift__starts_at__lte=at, shift_signup__shift__ends_at__gt=at,
            shift_signup__attendance__state__in=["scheduled", "checked_in"])
    ).filter(~Q(source_kind="role") | ~Q(role_assignment__role="sponsor_rep")
             | Q(role_assignment__sponsor__active=True))


def grant_ids(*, permission=None, at=None, track_id=None, discovery=False):
    rows = active_entitlements(at=at)
    if permission:
        rows = rows.filter(permissions__contains=[permission])
    if track_id is not None:
        rows = rows.filter(Q(track_ids=[]) | Q(track_ids__contains=[track_id]))
    elif not discovery:
        # A track-restricted source cannot authorize an unscoped roster operation.
        rows = rows.filter(track_ids=[])
    return rows.values("grant_id")


def permissions_for(*, grant_ids, at=None, track_id=None):
    rows = active_entitlements(at=at).filter(grant_id__in=grant_ids)
    rows = rows.filter(Q(track_ids=[]) | Q(track_ids__contains=[track_id])) if track_id else rows.filter(track_ids=[])
    return sorted({p for values in rows.values_list("permissions", flat=True) for p in values})


def can_delegate_helpers(*, actor, target, permissions, scope: DelegationScope):
    if scope.event_id != target.pk or scope.helper_role not in HELPER_PERMISSIONS:
        return False
    if not permissions or not set(permissions) <= HELPER_PERMISSIONS[scope.helper_role]:
        return False
    if "manage_team" in permissions or not event_authority._active(actor):
        return False
    if scope.valid_from and scope.valid_until and scope.valid_until <= scope.valid_from:
        return False
    if event_authority.can_manage_grants(actor, target):
        return True
    if not event_authority.can(actor, target, "manage_team"):
        return False
    sources = active_entitlements().filter(Q(event=target) | Q(series_id=target.series_id,
        series__isnull=False), grant__user=actor)
    # One coherent source must cover each requested permission for the entire scope.
    for permission in permissions:
        covered = False
        for source in sources.filter(permissions__contains=[permission]):
            if source.track_ids and (not scope.track_ids or not set(scope.track_ids) <= set(source.track_ids)):
                continue
            if source.valid_from and (scope.valid_from is None or scope.valid_from < source.valid_from):
                continue
            if source.valid_until and (scope.valid_until is None or scope.valid_until > source.valid_until):
                continue
            covered = True
            break
        if not covered:
            return False
    return True


def subset_validator(*, actor, target, permissions, operation, row):
    """Install on the G1 GrantAdapter. G resolves BOTH old and requested scopes.

    Redemption passes the *inviter*, as the shared lifecycle already guarantees.
    A co-organizer cannot extend time/tracks or revoke a broader helper grant.
    """
    if event_authority.can_manage_grants(actor, target):
        return all(event_authority.can(actor, target, p) for p in permissions)
    if "manage_team" in permissions:
        return False
    return ports().delegation_scope(actor_id=actor.pk, target_id=target.pk,
        permissions=tuple(permissions), operation=operation,
        row_id=row.pk if row is not None else None) is True
