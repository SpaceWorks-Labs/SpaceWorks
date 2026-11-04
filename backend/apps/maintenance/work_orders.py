"""Work-order lifecycle (machines D7, MT3): the one repair/maintenance job model.

open -> in_progress | on_hold | cancelled; in_progress <-> on_hold; in_progress -> done.
Authority per subject (#102: managers act in their own scope, no grant):
machines -> machine `manage` reach under `machines.maintenance`; inventory products and
units -> `edit_inventory` under `inventory.maintenance`; bookable spaces ->
`manage_bookings` under `bookings.room_maintenance`. Starting a work order that
`takes_machine_down` puts the machine in maintenance (opening a downtime period); closing
or cancelling it brings the machine back when nothing else holds it down. Closing a
machine work order writes the immutable `MaintenanceLog`. Every step is audited.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.audit.services import record
from apps.makerspaces.folded_capabilities import require_capability

from .models import WorkOrder

S = WorkOrder.Status
EDGES = {S.OPEN: {S.IN_PROGRESS, S.ON_HOLD, S.CANCELLED}, S.IN_PROGRESS: {S.ON_HOLD, S.DONE, S.CANCELLED},
         S.ON_HOLD: {S.IN_PROGRESS, S.CANCELLED}}
FEATURES = {WorkOrder.Subject.MACHINE: "machines.maintenance", WorkOrder.Subject.PRODUCT: "inventory.maintenance",
            WorkOrder.Subject.ASSET: "inventory.maintenance", WorkOrder.Subject.SPACE: "bookings.room_maintenance"}


def may_manage(actor, order):
    if order.subject_type == WorkOrder.Subject.MACHINE:
        from apps.machines import access
        allowed = access.can_manage_machine(actor, order.machine)
    elif order.subject_type == WorkOrder.Subject.SPACE:
        allowed = rbac.can(actor, rbac.Action.MANAGE_BOOKINGS, order.makerspace_id)
    else:
        allowed = rbac.can(actor, rbac.Action.EDIT_INVENTORY, order.makerspace_id)
    # L16: a Technician works the orders assigned to them (#128 C-3).
    from .repairs.authority import technician_may_work_order
    return allowed or technician_may_work_order(actor, order)


def _check(actor, order):
    require_capability(order.makerspace_id, FEATURES[order.subject_type])
    if not may_manage(actor, order):
        raise PermissionDenied()


def _audit_move(actor, order, status):
    space, pk, kind, machine = order.makerspace, order.pk, order.subject_type, order.machine_id
    if status == S.IN_PROGRESS:
        record(actor, "work_order.started", makerspace=space, target=order,
               meta={"work_order_id": pk, "subject_type": kind, "machine_id": machine})
    elif status == S.ON_HOLD:
        record(actor, "work_order.held", makerspace=space, target=order,
               meta={"work_order_id": pk, "subject_type": kind, "machine_id": machine})
    elif status == S.DONE:
        record(actor, "work_order.closed", makerspace=space, target=order,
               meta={"work_order_id": pk, "subject_type": kind, "machine_id": machine, "log_id": order.log_id})
    else:
        record(actor, "work_order.cancelled", makerspace=space, target=order,
               meta={"work_order_id": pk, "subject_type": kind, "machine_id": machine})


@transaction.atomic
def create_work_order(actor, makerspace, *, subject_type, subject, title, description="", priority="normal",
                      due_on=None, assignee=None, takes_machine_down=False, schedule=None):
    order = WorkOrder(makerspace=makerspace, subject_type=subject_type, title=str(title).strip()[:200],
                      description=str(description or ""), priority=priority, due_on=due_on, assignee=assignee,
                      takes_machine_down=bool(takes_machine_down) and subject_type == WorkOrder.Subject.MACHINE,
                      schedule=schedule, created_by=actor)
    field = {WorkOrder.Subject.MACHINE: "machine", WorkOrder.Subject.PRODUCT: "product",
             WorkOrder.Subject.ASSET: "asset", WorkOrder.Subject.SPACE: "space"}[subject_type]
    if getattr(subject, "makerspace_id", None) != makerspace.pk:
        raise ValidationError({"subject": "The subject must belong to this makerspace."})
    setattr(order, field, subject)
    if not order.title:
        raise ValidationError({"title": "Give the work order a title."})
    _check(actor, order)
    order.full_clean()
    order.save()
    record(actor, "work_order.created", makerspace=order.makerspace, target=order,
           meta={"work_order_id": order.pk, "subject_type": order.subject_type, "machine_id": order.machine_id,
                 "priority": order.priority})
    return order


def _machine_status(order, actor, status, reason=""):
    from apps.machines.models import Machine
    from apps.machines.status_tracking import change_status
    machine = Machine.objects.select_for_update(no_key=True).get(pk=order.machine_id)
    if status == "maintenance" and machine.status in ("idle", "offline"):
        change_status(machine, "maintenance", source="work_order", actor=actor, reason=reason)
    elif status == "idle" and machine.status == "maintenance":
        others = WorkOrder.objects.filter(machine_id=machine.pk, takes_machine_down=True,
                                          status=S.IN_PROGRESS).exclude(pk=order.pk)
        if not others.exists():
            change_status(machine, "idle", source="work_order", actor=actor)


@transaction.atomic
def move(actor, order, status, *, resolution="", log_cost=None, parts_note="", log_cost_method=None,
         log_cost_currency=None):
    order = WorkOrder.objects.select_for_update().select_related("makerspace").get(pk=order.pk)
    _check(actor, order)
    if status not in EDGES.get(order.status, set()):
        raise ValidationError({"status": f"A {order.status} work order cannot become {status}."})
    now = timezone.now()
    order.status = status
    if status == S.IN_PROGRESS and order.started_at is None:
        order.started_at = now
    if status in (S.DONE, S.CANCELLED):
        order.closed_at, order.closed_by, order.resolution = now, actor, str(resolution or "")[:4000]
    if status == S.DONE and order.subject_type == WorkOrder.Subject.MACHINE:
        from .services_workflows import log_maintenance
        order.log = log_maintenance(order.machine, actor=actor, summary=order.resolution or order.title,
                                    cost=log_cost, parts_note=parts_note, cost_method=log_cost_method,
                                    cost_currency=log_cost_currency)
    order.save()
    if order.takes_machine_down and status == S.IN_PROGRESS:
        _machine_status(order, actor, "maintenance", order.title)
    if order.takes_machine_down and status in (S.DONE, S.CANCELLED):
        _machine_status(order, actor, "idle")
    _audit_move(actor, order, status)
    return order


@transaction.atomic
def assign(actor, order, assignee):
    order = WorkOrder.objects.select_for_update().select_related("makerspace").get(pk=order.pk)
    _check(actor, order)
    if order.status not in WorkOrder.OPEN_STATUSES:
        raise ValidationError({"status": "Only an open work order can be reassigned."})
    staff = (rbac.Action.MANAGE_MACHINES, rbac.Action.EDIT_INVENTORY, rbac.Action.MANAGE_BOOKINGS,
             rbac.Action.MANAGE_MAKERSPACE, rbac.Action.WORK_REPAIRS)
    if assignee is not None and not any(rbac.can(assignee, action, order.makerspace_id) for action in staff):
        raise ValidationError({"assignee_id": "Assign a staff member of this makerspace."})
    order.assignee = assignee
    order.save(update_fields=["assignee", "updated_at"])
    record(actor, "work_order.assigned", makerspace=order.makerspace, target=order,
           meta={"work_order_id": order.pk, "subject_type": order.subject_type, "assigned": assignee is not None})
    return order
