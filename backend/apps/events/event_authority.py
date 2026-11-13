"""The single event authority API; event credentials never widen tenant RBAC."""

from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from apps.accounts.staff_identity import is_person
from apps.accounts import rbac
from apps.makerspaces.guards import require_module
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable, servable_q

from . import organizer_authority, series_authority
from .event_permissions import PERMISSIONS, VIEW
from .models import Event, EventSeries, EventStaffGrant


def _active_account(actor):
    return bool(actor and getattr(actor, "is_authenticated", False)
                and actor.is_active and actor.access_status == "active"
                and not getattr(actor, "is_tenant_dump_stub", False))


def _active(actor):
    return _active_account(actor) and not getattr(actor, "must_change_password", False)


def active_grants(actor, *, makerspace_id=None):
    rows = EventStaffGrant.objects.none()
    # Discovery must permit the existing forced-password login/rotation gate.
    # Mutation authority separately checks _active, which refuses that credential.
    if not _active_account(actor) or not is_person(actor):
        return rows
    rows = EventStaffGrant.objects.filter(user=actor, revoked_at__isnull=True).filter(
        Q(event__makerspace_id=F("makerspace_id"))
        | Q(series__makerspace_id=F("makerspace_id")),
    ).filter(servable_q("makerspace"), makerspace__enabled_modules__contains=["events"])
    # module_enabled also applies deployment tombstones.
    from apps.makerspaces.module_registry import module_available
    if not module_available("events"):
        return rows.none()
    if makerspace_id is not None:
        rows = rows.filter(makerspace_id=makerspace_id)
    from .contributions.authority import grant_ids
    return rows.filter(pk__in=grant_ids(discovery=True, scope_grants=rows))


def _is_series(target):
    return isinstance(target, EventSeries)


def can_manage_grants(actor, event):
    if not _active(actor) or not is_servable(event.makerspace):
        return False
    if not module_enabled(event.makerspace, "events"):
        return False
    if rbac.can(actor, rbac.Action.MANAGE_EVENTS, event.makerspace_id):
        return True
    if _is_series(event):
        return series_authority.can_manage_series(actor, event)
    return organizer_authority.can_manage_event(actor, event) or bool(
        event.series_id and series_authority.can_manage_series(actor, event.series)
    )


def can(actor, event, permission, *, track_id=None, team_id=None):
    if permission not in (*PERMISSIONS, VIEW, None) or not _active(actor):
        return False
    if team_id is not None and permission in ("judge", "review_applications"):
        from .mentoring.policy import is_conflicted
        if is_conflicted(member_id=actor.pk, team_id=team_id):
            return False
    if can_manage_grants(actor, event):
        return True
    if permission is None:
        return False
    rows = active_grants(actor, makerspace_id=event.makerspace_id)
    if _is_series(event):
        rows = rows.filter(series=event)
    else:
        rows = rows.filter(Q(event=event) | Q(series_id=event.series_id, series__isnull=False))
    from .contributions.authority import grant_ids
    rows = rows.filter(pk__in=grant_ids(permission=None if permission == VIEW else permission,
        track_id=track_id, discovery=permission == VIEW, scope_grants=rows))
    return rows.exists()


def require(actor, event, permission, **scope):
    require_module(event.makerspace, "events")
    if not can(actor, event, permission, **scope):
        raise PermissionDenied()


def permissions_for(actor, event, *, track_id=None):
    """Granted permissions, batched per resource after the manager check."""
    rows = active_grants(actor, makerspace_id=event.makerspace_id)
    if _is_series(event):
        rows = rows.filter(series=event)
    else:
        rows = rows.filter(Q(event=event) | Q(series_id=event.series_id, series__isnull=False))
    from .contributions.authority import permissions_for as source_permissions
    values = set(source_permissions(grant_ids=rows.values("pk"), track_id=track_id))
    return [permission for permission in PERMISSIONS if permission in values]


def require_tenant(actor, makerspace):
    """Tenant collection/configuration surfaces never accept a resource grant."""
    require_module(makerspace, "events")
    if not rbac.can(actor, rbac.Action.MANAGE_EVENTS, makerspace.pk):
        raise PermissionDenied()


def events_for(actor, permission, queryset):
    """SQL union of authority sources, with subqueries to avoid inflating aggregates."""
    from apps.makerspaces.module_registry import module_available
    if not _active(actor) or not module_available("events"):
        return queryset.none()
    series = queryset.model is EventSeries
    all_rows = queryset.model.objects.all()
    tenant = rbac.scope_by_action(actor, rbac.Action.MANAGE_EVENTS, all_rows)
    org_q = (series_authority.organizer_series_q(actor) if series
             else organizer_authority.organizer_event_q(actor))
    if not series:
        org_q |= series_authority.organizer_series_q(actor, prefix="series__")
    authorized = Q(pk__in=tenant.values("pk")) | Q(pk__in=all_rows.filter(org_q).values("pk"))
    if permission in (*PERMISSIONS, VIEW):
        grants = active_grants(actor)
        from .contributions.authority import grant_ids
        grants = grants.filter(pk__in=grant_ids(permission=None if permission == VIEW else permission,
            discovery=permission == VIEW, scope_grants=grants))
        if series:
            authorized |= Q(pk__in=grants.values("series_id"))
        else:
            authorized |= Q(pk__in=grants.values("event_id"))
            authorized |= Q(
                series_id__in=grants.filter(series__isnull=False).values("series_id"),
                series__makerspace_id=F("makerspace_id"),
            )
    elif permission is not None:
        return queryset.none()
    return queryset.filter(authorized).filter(
        servable_q("makerspace"), makerspace__enabled_modules__contains=["events"],
    )


def visible_events(actor, queryset):
    """Keep local-visible/forbidden = 403 and unrelated/hidden = 404."""
    visible = rbac.scope_by_visibility_or_action(actor, rbac.Action.MANAGE_EVENTS, queryset)
    allowed = events_for(actor, VIEW, queryset)
    return queryset.filter(Q(pk__in=visible.values("pk")) | Q(pk__in=allowed.values("pk")))


def organized_events_for(actor, queryset):
    """Preserve the organizer-only discovery contract through the authority API."""
    organized_ids = Event.objects.filter(organizer_authority.organizer_event_q(actor)).values("pk")
    return events_for(actor, None, queryset.filter(pk__in=organized_ids))


def get_event(actor, pk, permission=None, *, series=False):
    model = EventSeries if series else Event
    rows = model.objects.select_related("makerspace")
    if not series:
        rows = rows.select_related("series").prefetch_related(
            "organizers__organization", "audience_organizations__organization")
    event = get_object_or_404(visible_events(actor, rows), pk=pk)
    require(actor, event, permission)
    return event
