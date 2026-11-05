"""The same list authority for saved preferences and cross-entity discovery."""

from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.makerspaces.guards import require_module
from apps.makerspaces.servability import servable_queryset

ENTITY_ACTIONS = {
    "requests": (rbac.Action.ACCEPT_REQUEST, rbac.Action.ISSUE_REQUEST),
    "inventory": (rbac.Action.VIEW_INVENTORY,),
    "members": (rbac.Action.MANAGE_MEMBERS,),
    "payments": (rbac.Action.VIEW_FINANCE, rbac.Action.RECORD_PAYMENT),
    "bookings": (rbac.Action.MANAGE_BOOKINGS,),
    "events": (rbac.Action.MANAGE_EVENTS,),
    "audit": (rbac.Action.VIEW_AUDIT,),
}
# Release 2 L21b (X40): the five staff event lists. A saved view restores filters only; each list
# re-checks the reader's event permission, so sharing a view never grants access.
EVENT_LIST_ENTITIES = ("event_guests", "event_teams", "event_submissions", "event_results", "event_progress")
ENTITY_ACTIONS.update({entity: (rbac.Action.MANAGE_EVENTS,) for entity in EVENT_LIST_ENTITIES})
ENTITY_MODULES = {"inventory": "staff_admin", "bookings": "bookings", "events": "events",
                  **{entity: "events" for entity in EVENT_LIST_ENTITIES}}


def visible_space(actor, makerspace_id):
    from django.shortcuts import get_object_or_404

    # Visibility includes organization-derived action scopes, without granting any
    # entity access merely because a person belongs to the tenant.
    ids = rbac.makerspaces_for_actions(actor, *{a for actions in ENTITY_ACTIONS.values() for a in actions}, rbac.Action.MANAGE_MACHINES)
    spaces = servable_queryset()
    local = rbac.scope_by_makerspace(actor, spaces, makerspace_field="id")
    if ids is not rbac.ALL:
        spaces = spaces.filter(Q(pk__in=ids) | Q(pk__in=local.values("pk")))
    return get_object_or_404(spaces, pk=makerspace_id)


def require_entity(actor, space, entity):
    if not any(rbac.can(actor, action, space.pk) for action in ENTITY_ACTIONS[entity]):
        raise PermissionDenied()
    if entity == "requests":
        require_module(space, "request_workflow")
    elif entity in ENTITY_MODULES:
        require_module(space, ENTITY_MODULES[entity])
    if entity in EVENT_LIST_ENTITIES:
        from apps.makerspaces.guards import require_feature
        require_feature(space, "events.saved_views")


def request_scope(actor, makerspace_id):
    from apps.hardware_requests.models import HardwareRequest
    from apps.hardware_requests.view_helpers import request_queryset

    statuses = Q(pk__in=[])
    if rbac.can(actor, rbac.Action.ACCEPT_REQUEST, makerspace_id):
        statuses |= Q(status=HardwareRequest.Status.PENDING_APPROVAL)
    if rbac.can(actor, rbac.Action.ISSUE_REQUEST, makerspace_id):
        statuses |= Q(status__in=["accepted", "issued", "partially_returned", "returned", "rejected", "closed_with_issue"])
    scoped = rbac.scope_by_action(actor, rbac.Action.ACCEPT_REQUEST, request_queryset())
    handover = rbac.scope_by_action(actor, rbac.Action.ISSUE_REQUEST, request_queryset())
    return request_queryset().filter(Q(pk__in=scoped.values("pk")) | Q(pk__in=handover.values("pk"))).filter(makerspace_id=makerspace_id).filter(statuses)
