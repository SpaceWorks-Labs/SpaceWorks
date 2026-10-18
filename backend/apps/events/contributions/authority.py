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


def _candidates(*, at=None, discovery=False):
    at = at or timezone.now()
    return EventGrantEntitlement.objects.filter(
        revoked_at__isnull=True, grant__revoked_at__isnull=True,
        makerspace_id=F("grant__makerspace_id"),
        grant__user__account_kind="member", grant__user__is_active=True,
        grant__user__access_status="active", grant__user__is_tenant_dump_stub=False,
        grant__user__retired_at__isnull=True,
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


def active_entitlements(*, at=None, scope_grants=None, event_id=None, series_id=None, discovery=False):
    """Every authority query includes the source and its current issuer chain.

    A cached grant union cannot revive a removed issuer, stale import or cyclic
    delegation. No source may widen its issuer's time or track restrictions.
    """
    rows = _candidates(at=at, discovery=discovery)
    if not discovery:
        rows = rows.filter(grant__user__must_change_password=False)
    if scope_grants is not None:
        from apps.events.models import Event
        targets = list(scope_grants.values_list("event_id", "series_id"))
        events = {eid for eid, _ in targets if eid is not None}
        series = {sid for _, sid in targets if sid is not None}
        series.update(Event.objects.filter(pk__in=events).exclude(series_id=None).values_list("series_id", flat=True))
        rows = rows.filter(Q(event_id__in=events) | Q(series_id__in=series))
    elif event_id is not None:
        from apps.events.models import Event
        parent = Event.objects.values_list("series_id", flat=True).get(pk=event_id)
        rows = rows.filter(Q(event_id=event_id) | Q(series_id=parent, series__isnull=False))
    elif series_id is not None:
        rows = rows.filter(series_id=series_id)
    candidates = list(rows.select_related("created_by", "grant", "role_assignment", "shift_signup__shift",
        "event__makerspace", "series__makerspace"))
    by_user_target, checked = {}, {}
    for source in candidates:
        by_user_target.setdefault((source.grant.user_id, source.event_id, source.series_id), []).append(source)

    def live(source, visiting=frozenset()):
        if source.pk in checked:
            return checked[source.pk]
        if source.pk in visiting or not event_authority._active(source.created_by):
            return False
        if source.source_kind in ("role", "shift"):
            from apps.makerspaces.platform import feature_enabled
            event = source.event
            role_kind = source.role_assignment.role if source.source_kind == "role" else "volunteer"
            feature = {"volunteer": "events.volunteering", "mentor": "events.mentoring"}.get(role_kind, "events.hackathons")
            if event.status != "published" or event.ends_at <= (at or timezone.now()) or not feature_enabled(event.makerspace, feature):
                return False
        if source.source_kind == "role":
            from .sources import ROLE_PERMISSIONS
            role = source.role_assignment
            desired = set(role.delegated_permissions or ROLE_PERMISSIONS.get(role.role, ()))
            if (role.approved_by_id != source.created_by_id or not set(source.permissions) <= desired
                    or set(source.track_ids) != set(role.track_ids)):
                return False
            if role.role == "sponsor_rep":
                from .models_roles import EventSponsorTrack
                tracks = set(EventSponsorTrack.objects.filter(event_id=role.event_id,
                    sponsor_id=role.sponsor_id, track__event_id=role.event_id).values_list("track_id", flat=True))
                if not source.track_ids or not set(source.track_ids) <= tracks:
                    return False
        if source.source_kind == "shift":
            shift = source.shift_signup.shift
            if not set(source.permissions) <= set(shift.permission_preset):
                return False
        target = source.event if source.event_id else source.series
        if event_authority.can_manage_grants(source.created_by, target):
            checked[source.pk] = True
            return True
        # Full co-organizer authority must itself have a live coherent issuer.
        parents = by_user_target.get((source.created_by_id, source.event_id, source.series_id), [])
        if source.event_id and target.series_id:
            parents += by_user_target.get((source.created_by_id, None, target.series_id), [])
        wanted = set(source.permissions)
        for parent in parents:
            if "manage_team" not in parent.permissions or "manage_team" in wanted:
                continue
            if not wanted <= set(parent.permissions):
                continue
            if parent.track_ids and (not source.track_ids or not set(source.track_ids) <= set(parent.track_ids)):
                continue
            if parent.valid_from and (source.valid_from is None or source.valid_from < parent.valid_from):
                continue
            if parent.valid_until and (source.valid_until is None or source.valid_until > parent.valid_until):
                continue
            if live(parent, visiting | {source.pk}):
                checked[source.pk] = True
                return True
        checked[source.pk] = False
        return False

    return rows.filter(pk__in=[row.pk for row in candidates if live(row)])


def grant_ids(*, permission=None, at=None, track_id=None, discovery=False, scope_grants=None):
    rows = active_entitlements(at=at, scope_grants=scope_grants, discovery=discovery)
    if permission:
        rows = rows.filter(permissions__contains=[permission])
    if track_id is not None:
        rows = rows.filter(Q(track_ids=[]) | Q(track_ids__contains=[track_id]))
    elif not discovery:
        # A track-restricted source cannot authorize an unscoped roster operation.
        rows = rows.filter(track_ids=[])
    return rows.values("grant_id")


def permissions_for(*, grant_ids, at=None, track_id=None):
    from apps.events.models_staff_grants import EventStaffGrant
    rows = active_entitlements(at=at,
        scope_grants=EventStaffGrant.objects.filter(pk__in=grant_ids)).filter(grant_id__in=grant_ids)
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
    sources = active_entitlements(event_id=target.pk).filter(Q(event=target) | Q(series_id=target.series_id,
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
    if event_authority._is_series(target):
        return False
    desired = set(permissions)
    if row is not None:
        if operation in ("update_permissions", "revoke_grant"):
            old = EventGrantEntitlement.objects.filter(grant_id=row.pk, source_kind="manual",
                revoked_at__isnull=True).values_list("permissions", flat=True)
            desired.update(p for values in old for p in values)
        else:
            desired.update(row.permissions)
    if "manage_team" in desired:
        return False
    if not desired:
        return event_authority.can(actor, target, "manage_team")
    return ports().delegation_scope(actor_id=actor.pk, target_id=target.pk,
        permissions=tuple(sorted(desired)), operation=operation,
        row_id=row.pk if row is not None else None) is True
