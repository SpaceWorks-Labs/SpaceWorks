"""Per-activity consumable usage, derived from inventory-owned use receipts.

Attribution is never stored here. A use receipt belongs to an activity through
its one source (DB-enforced): a plan's active event/booking plan context, or a
kit allocation whose request carries an active event/booking loan context. Plan
and loan contexts are one-to-one with their plan/request, so a receipt counts
once. Read-only: every quantity shown is read from the inventory owners' rows;
nothing here reserves, consumes or adjusts stock.
"""
from decimal import Decimal

from django.apps import apps
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext

from apps.accounts import rbac
from apps.admin_api.permissions import require_action
from apps.hardware_requests.loan_context_access import authorized_request_queryset, safe_id
from apps.makerspaces.platform import module_enabled
from .report_definitions_loan_context import CONSUMABLE_CONTEXT_FIELDS as FIELDS
from .report_types import ReportNotFound, ReportResult
from .reports_ab_common import spaces


def _space(actor, makerspace_id, module):
    if makerspace_id is None or actor is None:
        raise ReportNotFound()
    require_action(actor, rbac.Action.VIEW_INVENTORY, makerspace_id)
    candidates = spaces(makerspace_id, "inventory.consumables", module)
    if len(candidates) != 1:
        raise ReportNotFound()
    return candidates[0]


def _sources(actor, space, plan_contexts, loan_contexts):
    """Plan and allocation querysets linked to one activity, within the actor's authority."""
    plans = apps.get_model("inventory", "EquipmentConsumablePlan").objects.filter(
        makerspace=space, pk__in=plan_contexts.values("plan_id"),
    )
    allocations = apps.get_model("inventory", "EquipmentKitAllocation").objects.none()
    if module_enabled(space, "request_workflow"):
        # Allocation use is shown only for requests the actor may already see.
        allowed = authorized_request_queryset(actor, space).filter(
            pk__in=loan_contexts.values("request_id"),
        )
        allocations = apps.get_model("inventory", "EquipmentKitAllocation").objects.filter(
            makerspace=space, request_id__in=allowed.values("pk"),
        )
    return plans, allocations


def _planned(rows, participants=None):
    """Planned quantity per product: `quantity_per_person` times the people a row covers.

    A plan or allocation made for one named person (an event registration, or a booking's own
    borrower) covers exactly one. A SHARED row, one made for the whole event rather than a
    registration, covers every participant, so its per-person quantity is multiplied by
    `participants` (`{row_pk: people}`); a row absent from the map covers one person.
    """
    participants = participants or {}
    planned = {}
    for pk, lines in rows.values_list("pk", "lines"):
        people = max(1, participants.get(pk, 1))
        for line in lines if isinstance(lines, list) else ():
            if isinstance(line, dict) and line.get("kind") == "consumable" and type(line.get("product_id")) is int:
                quantity = line.get("quantity_per_person")
                planned[line["product_id"]] = planned.get(line["product_id"], 0) + (
                    quantity * people if type(quantity) is int else 0)
    return planned


def _shared_event_rows(event, space):
    """`({plan_pk: n}, {allocation_pk: n})` for event rows not tied to one registration."""
    from apps.events.capacity import confirmed_occupancy
    people = confirmed_occupancy(event)
    plan_ids = apps.get_model("events", "EventConsumablePlanContext").objects.filter(
        makerspace=space, event=event, active=True, participant_registration__isnull=True,
    ).values_list("plan_id", flat=True)
    request_ids = apps.get_model("events", "EventLoanContext").objects.filter(
        makerspace=space, event=event, active=True, participant_registration__isnull=True,
    ).values_list("request_id", flat=True)
    allocation_ids = apps.get_model("inventory", "EquipmentKitAllocation").objects.filter(
        makerspace=space, request_id__in=request_ids).values_list("pk", flat=True)
    return dict.fromkeys(plan_ids, people), dict.fromkeys(allocation_ids, people)


def _summary(actor, space, plans, allocations, limit, shared=({}, {})):
    receipts = apps.get_model("inventory", "EquipmentConsumableUseReceipt").objects.filter(
        makerspace=space,
    ).filter(Q(plan_id__in=plans.values("pk")) | Q(allocation_id__in=allocations.values("pk")))
    used = dict(receipts.order_by().values("product_id").annotate(total=Sum("quantity")).values_list("product_id", "total"))
    planned = _planned(plans, shared[0])
    for product_id, quantity in _planned(allocations, shared[1]).items():
        planned[product_id] = planned.get(product_id, 0) + quantity
    products = rbac.scope_by_action(actor, rbac.Action.VIEW_INVENTORY, apps.get_model(
        "inventory", "InventoryProduct").objects.filter(
        makerspace=space, is_consumable=True, pk__in=set(used) | set(planned),
    )).order_by("name", "pk")
    if limit is not None:
        products = products[:limit]
    records = []
    for product in products:
        used_quantity = used.get(product.pk, 0)
        remaining = max(0, planned.get(product.pk, 0) - used_quantity)
        shortage = max(0, remaining - product.available_quantity)
        at_reorder = product.reorder_point > 0 and product.available_quantity <= product.reorder_point
        replenish = 0 if product.is_archived else max(shortage, product.reorder_quantity if at_reorder else 0)
        priced = product.unit_cost is not None and product.cost_unit == "count"
        records.append({
            "product_id": product.pk, "product_name": product.name,
            "planned_quantity": planned.get(product.pk, 0), "used_quantity": used_quantity,
            "remaining_planned": remaining, "available_quantity": product.available_quantity,
            "shortage_quantity": shortage, "reorder_point": product.reorder_point,
            "replenishment_quantity": replenish,
            "currency": product.cost_currency if priced else "",
            "unit_cost": product.unit_cost if priced else None,
            "estimated_cost": product.unit_cost * Decimal(used_quantity) if priced else None,
        })
    return ReportResult(FIELDS, records, {
        "basis": gettext("Consumables recorded as used against this activity's linked plans and kit allocations, each use counted once, over the activity's lifetime. Kit allocations appear only for loans you may view. Cost is estimated at the product's current unit cost; unpriced products show no cost. Shortage compares the remaining planned quantity with current available stock."),
    })


def build_event_consumables(makerspace_id, *, subject_kind, subject_id, actor=None, limit=None, date_range=None):
    if subject_kind != "event":
        raise ReportNotFound()
    space = _space(actor, makerspace_id, "events")
    from apps.events import event_authority
    from apps.events.event_permissions import VIEW
    event = get_object_or_404(apps.get_model("events", "Event"), makerspace=space, pk=safe_id(subject_id))
    event_authority.require(actor, event, VIEW)
    plans, allocations = _sources(
        actor, space,
        apps.get_model("events", "EventConsumablePlanContext").objects.filter(
            makerspace=space, event=event, active=True),
        apps.get_model("events", "EventLoanContext").objects.filter(
            makerspace=space, request__makerspace=space, event=event, active=True),
    )
    return _summary(actor, space, plans, allocations, limit, _shared_event_rows(event, space))


def build_booking_consumables(makerspace_id, *, subject_kind, subject_id, actor=None, limit=None, date_range=None):
    if subject_kind != "booking":
        raise ReportNotFound()
    space = _space(actor, makerspace_id, "bookings")
    from apps.bookings import booking_authority
    from apps.bookings.booking_permissions import VIEW
    booking = get_object_or_404(
        apps.get_model("bookings", "Booking").objects.select_related("space__makerspace"),
        space__makerspace=space, pk=safe_id(subject_id),
    )
    booking_authority.require(actor, booking.space, VIEW)
    plans, allocations = _sources(
        actor, space,
        apps.get_model("bookings", "BookingConsumablePlanContext").objects.filter(
            makerspace=space, booking=booking, active=True),
        apps.get_model("bookings", "BookingLoanContext").objects.filter(
            makerspace=space, request__makerspace=space, booking=booking, active=True),
    )
    return _summary(actor, space, plans, allocations, limit)
