"""Narrow the legacy makerspace-wide staff feed to the reader's areas.

A legacy ``Notification`` row carries only its ``event`` key, so its area is the
audit area of that key (``apps.audit.areas``): ``request.*``/``loan.*``/``stocktake.*``
are lending, ``machine_service.*`` machines, ``email.failed``/``backup.*`` and any
unplaced key platform. The Space Manager (MANAGE_MAKERSPACE) keeps the whole feed;
every other reader sees only rows of an area their effective actions open, so an
Inventory Manager no longer reads machine-service or delivery-failure alerts and an
unscoped Machine Manager no longer reads loan alerts. Unplaced keys fail closed; a
row with no event key (pre-keyed emitters, demo seeds) stays visible to every reader.

Machine provenance (open item B7): a ``machine_service.*`` row names its request in ``url_path``
(``/admin/machine-service/requests/<id>``), so a reader whose MANAGE_MACHINES is scoped to some
machine types reads only the rows of requests inside that scope; a row naming no request fails
closed for them. A reader who also holds MANAGE_PRINTING keeps every machine-service row.
"""

import re

from apps.accounts import rbac
from apps.audit import areas

_SERVICE_PREFIX = "machine_service."
_SERVICE_PATH = re.compile(r"^/admin/machine-service/requests/(\d+)$")


def reader_areas(actor, makerspace_id):
    actions = rbac.effective_actions(actor, makerspace_id)
    held = areas.areas_for_actions(actions)
    # The feed admits VIEW_INVENTORY holders; reading the catalogue opens loan alerts.
    if rbac.Action.VIEW_INVENTORY in actions:
        held |= {areas.LENDING}
    return held


def _machine_scoped(actor, makerspace_id):
    """True when the reader's machine reach is narrower than the whole space (and printing does not widen it)."""
    from apps.machines import role_scope
    actions = rbac.effective_actions(actor, makerspace_id)
    return (rbac.Action.MANAGE_MACHINES in actions and rbac.Action.MANAGE_PRINTING not in actions
            and role_scope.manage_scope_for(actor, makerspace_id) is not role_scope.EXEMPT)


def _request_id(url_path):
    match = _SERVICE_PATH.match(url_path or "")
    return int(match.group(1)) if match else None


def _in_machine_scope(actor, makerspace_id, request_ids):
    from apps.machines.models_service import MachineServiceRequest
    from apps.machines.role_scope_queries import scoped_service_requests
    rows = MachineServiceRequest.objects.filter(pk__in=request_ids, makerspace_id=makerspace_id)
    return set(scoped_service_requests(actor, rows, [makerspace_id]).values_list("pk", flat=True))


def event_visible(actor, makerspace_id, event, held=None, url_path=""):
    held = reader_areas(actor, makerspace_id) if held is None else held
    # A row with no event key predates the keyed emitter: it stays visible to every reader.
    if areas.PLATFORM in held or not event:
        return True
    if not set(areas.areas_for_action(event)) & held:
        return False
    if event.startswith(_SERVICE_PREFIX) and _machine_scoped(actor, makerspace_id):
        request_id = _request_id(url_path)
        return request_id is not None and request_id in _in_machine_scope(actor, makerspace_id, [request_id])
    return True


def scope_feed(actor, makerspace_id, queryset):
    """Keep only rows whose event belongs to an area the reader works in."""
    held = reader_areas(actor, makerspace_id)
    if areas.PLATFORM in held:
        return queryset
    events = set(queryset.order_by().values_list("event", flat=True).distinct())
    visible = queryset.filter(event__in=sorted(e for e in events if event_visible(actor, makerspace_id, e, held)))
    if not (_machine_scoped(actor, makerspace_id) and any(e.startswith(_SERVICE_PREFIX) for e in events)):
        return visible
    service = list(visible.filter(event__startswith=_SERVICE_PREFIX).order_by().values_list("pk", "url_path"))
    allowed = _in_machine_scope(actor, makerspace_id, [rid for _, path in service if (rid := _request_id(path))])
    hidden = [pk for pk, path in service if _request_id(path) not in allowed]
    return visible.exclude(pk__in=hidden) if hidden else visible
