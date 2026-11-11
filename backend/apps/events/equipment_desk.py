"""Event-scoped projections of event-linked loans (decision 214, journeys B-D).

Read-only. Every row is an existing canonical HardwareRequest found through an active
EventLoanContext; state changes still go through the request workflow's own issue/return
endpoints, and quantities are the workflow's stored counters, never recomputed stock.
Event authority and inventory authority are checked independently.
"""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts import rbac
from apps.accounts.loan_context_identity import borrower_aliases
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.view_helpers import request_queryset
from apps.makerspaces.guards import require_feature, require_module
from apps.makerspaces.platform import module_enabled

from . import event_authority, event_permissions
from .member_history import registrations_for_space
from .models import Event, EventRegistration
from .models_loan_context import EventLoanContext

S = HardwareRequest.Status
OUT = (S.ISSUED, S.PARTIALLY_RETURNED)
CLOSED = (S.RETURNED, S.CLOSED_WITH_ISSUE)
CLOSED_LIMIT = 100


def outstanding_units(request):
    """Units still with the borrower, read from the workflow's own item counters."""
    return sum(max(0, item.issued_quantity - item.returned_quantity - item.damaged_quantity
                   - item.missing_quantity) for item in request.items.all())


def _linked(event):
    return EventLoanContext.objects.filter(
        makerspace_id=event.makerspace_id, event=event, active=True,
    ).values("request_id")


def staff_desk(actor, makerspace_id, event_id):
    """(event, groups, summary) for one event; 404 unless both authorities hold."""
    event = get_object_or_404(Event.objects.select_related("makerspace"), pk=event_id, makerspace_id=makerspace_id)
    space = event.makerspace
    require_module(space, "events")  # switches answer before the authority check
    require_module(space, "request_workflow")
    if not event_authority.can(actor, event, event_permissions.VIEW):
        raise NotFound()
    require_feature(space, "loans.enabled")
    if not rbac.can(actor, rbac.Action.ISSUE_REQUEST, space.pk):
        raise NotFound()
    # Reviewed requests only: the desk drives the reviewed issue/return endpoints.
    rows = rbac.scope_by_action(actor, rbac.Action.ISSUE_REQUEST, request_queryset()).filter(
        makerspace_id=space.pk, pk__in=_linked(event), public_tool_loan__isnull=True,
    )
    now = timezone.now()
    ready = list(rows.filter(status=S.ACCEPTED).order_by("created_at", "pk"))
    out = list(rows.filter(status__in=OUT).order_by("return_due_at", "pk"))
    closed = list(rows.filter(status__in=CLOSED).order_by("-closed_at", "-pk")[:CLOSED_LIMIT])
    awaiting = list(rows.filter(status=S.PENDING_APPROVAL).order_by("created_at", "pk")[:CLOSED_LIMIT])
    from .equipment_desk_warnings import equipment_warnings
    summary = {
        "awaiting_review": rows.filter(status=S.PENDING_APPROVAL).count(),
        "equipment_warnings": equipment_warnings(ready, awaiting),
        "ready_to_issue": len(ready),
        "out": len(out),
        "overdue": sum(1 for row in out if row.return_due_at and row.return_due_at < now),
        "outstanding_units": sum(outstanding_units(row) for row in out),
        "closed_with_issue": rows.filter(status=S.CLOSED_WITH_ISSUE).count(),
        "event_ends_at": event.ends_at,
        "equipment_return_hours": event.equipment_return_hours,
    }
    return event, {"ready": ready, "out": out, "closed": closed}, summary


def member_equipment(user, makerspace, registration_id):
    """The caller's own loans linked to one of their own registrations' events."""
    require_module(makerspace, "events")
    registration = registrations_for_space(makerspace, user).select_related("event").filter(
        pk=registration_id,
    ).first()
    if registration is None or registration.event.makerspace_id != makerspace.pk:
        raise NotFound()
    require_module(makerspace, "request_workflow")
    require_feature(makerspace, "loans.enabled")
    event = registration.event
    try:
        aliases = borrower_aliases(user)
    except (ValueError, RuntimeError):
        raise NotFound() from None
    rows = HardwareRequest.objects.filter(
        makerspace_id=makerspace.pk, pk__in=_linked(event), requester_id__in=aliases,
    ).prefetch_related("items__product").order_by("-created_at", "-pk")
    now = timezone.now()
    requests = [{
        "public_token": row.public_token, "status": row.status, "created_at": row.created_at,
        "return_due_at": row.return_due_at,
        "overdue": bool(row.status in OUT and row.return_due_at and row.return_due_at < now),
        "items": [{"product_name": item.product.name, "requested_quantity": item.requested_quantity,
                   "accepted_quantity": item.accepted_quantity, "issued_quantity": item.issued_quantity,
                   "returned_quantity": item.returned_quantity} for item in row.items.all()],
    } for row in rows[:50]]
    can_request = (
        registration.status in {EventRegistration.Status.REGISTERED, EventRegistration.Status.ATTENDED}
        and event.status not in {Event.Status.CANCELLED, Event.Status.COMPLETED}
        and makerspace.public_site_enabled and makerspace.public_inventory_enabled
        and module_enabled(makerspace, "public_inventory")
    )
    return {"event_id": event.pk, "event_ends_at": event.ends_at, "can_request": bool(can_request),
            "requests": requests}
