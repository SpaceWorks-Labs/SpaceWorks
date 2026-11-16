"""Resolve the authority projection with a fixed set of queries for a page."""

from collections import defaultdict

from django.db.models import Q

from apps.accounts import rbac
from apps.makerspaces.module_registry import module_available
from apps.makerspaces.servability import servable_q

from . import event_authority, organizer_authority, series_authority
from .event_permissions import PERMISSIONS
from .models import Event, EventSeries


def _manager_ids(actor, model, ids, series_ids):
    if not event_authority._active(actor) or not module_available("events"):
        return set()

    # The action scope is the batched counterpart of rbac.can for each venue.
    scope = rbac.makerspaces_for_action(actor, rbac.Action.MANAGE_EVENTS)
    tenant = Q() if scope is rbac.ALL else Q(makerspace_id__in=scope)
    authorized = tenant
    if scope is not rbac.ALL:
        if model is EventSeries:
            authorized |= series_authority.organizer_series_q(actor)
        else:
            authorized |= organizer_authority.organizer_event_q(actor)
            # can_manage_grants also accepts the parent series' tenant/organizer
            # authority. Its module switch is not checked separately there.
            managed_series = EventSeries.objects.filter(pk__in=series_ids).filter(
                tenant | series_authority.organizer_series_q(actor),
            )
            authorized |= Q(series_id__in=managed_series.values("pk"))

    return set(model.objects.filter(pk__in=ids).filter(authorized).filter(
        servable_q("makerspace"), makerspace__enabled_modules__contains=["events"],
    ).values_list("pk", flat=True))


def authority_for_page(actor, rows):
    """Return the same (manager, ordered permissions) tuples as detail checks.

    Only page IDs enter the resource queries. Grants remain keyed by tenant as
    well as target, so a series grant cannot bleed into another venue.
    """
    if not rows:
        return {}
    model = EventSeries if isinstance(rows[0], EventSeries) else Event
    ids = {row.pk for row in rows}
    series_ids = ids if model is EventSeries else {row.series_id for row in rows if row.series_id}
    managers = _manager_ids(actor, model, ids, series_ids)
    event_permissions = defaultdict(set)
    series_permissions = defaultdict(set)
    # Forced-password accounts still expose their live grants for discovery,
    # while _manager_ids (like can_manage_grants) refuses management authority.
    targets = Q(series_id__in=series_ids)
    if model is Event:
        targets |= Q(event_id__in=ids)
    grants = event_authority.active_grants(actor).filter(
        targets, makerspace_id__in={row.makerspace_id for row in rows},
    ).values_list("makerspace_id", "event_id", "series_id", "permissions")
    for makerspace_id, event_id, series_id, permissions in grants:
        mapping = event_permissions if event_id is not None else series_permissions
        mapping[(makerspace_id, event_id if event_id is not None else series_id)].update(
            value for value in permissions if value in PERMISSIONS
        )

    result = {}
    for row in rows:
        manager = row.pk in managers
        if model is EventSeries:
            values = series_permissions[(row.makerspace_id, row.pk)]
        else:
            values = event_permissions[(row.makerspace_id, row.pk)] | series_permissions[
                (row.makerspace_id, row.series_id)
            ]
        permissions = list(PERMISSIONS) if manager else [value for value in PERMISSIONS if value in values]
        result[(row._meta.label, row.pk)] = (manager, permissions)
    return result
