"""Take a machine, an item, a unit or a room in or out of service (#93, #128 C-6b).

* Machine: its status goes to `maintenance` (or back to `idle`) through
  `status_tracking.change_status`, which also opens or closes the downtime period; the
  machine-service queue and ETA kernel count only machines with capacity, so the queue
  recomputes on its next read (#44). A running machine is refused. While it is under repair,
  new bookings of its time are refused (`machines.booking_gate`); the bookings already made
  until it is expected back are returned for staff, and their bookers emailed, as for a room.
* Unit: `availability.move_asset_status` (available <-> maintenance).
* Item: `availability.move_available_to_needs_fix` / `repair_from_needs_fix` for a count.
* Room: an outage that blocks (default) or warns; the affected bookings are returned for
  staff to decide on, and their bookers are emailed.

Who: the area manager (#102) or a Technician holding `set_service_state` whose coverage
names the subject (Q-T1 a). Behind the area's repairs or maintenance switch.
"""

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.accounts import rbac
from apps.audit import services as audit

from . import areas, authority, errors, history, notify
from .room_outages import affected_bookings, open_outage


def _gate(actor, space, subject_type, subject):
    area = areas.SUBJECT_AREA[subject_type]
    if not (areas.on(space, areas.REPAIRS[area]) or areas.on(space, areas.MAINTENANCE[area])):
        areas.refuse(areas.REPAIRS[area])
    if not authority.may_act_on_subject(actor, space.pk, rbac.Action.SET_SERVICE_STATE, subject_type, subject):
        raise errors.out_of_scope()


def _machine(actor, machine, in_service, reason, expected_back_at):
    from apps.machines.models import Machine
    from apps.machines.status_tracking import change_status
    machine = Machine.objects.select_for_update(no_key=True).get(pk=machine.pk)
    if in_service:
        if machine.status in ("maintenance", "offline"):
            change_status(machine, "idle", source="service_state", actor=actor)
        return machine.status
    if machine.status == "running":
        raise errors.bad_state("The machine is running a job; finish or stop it first.", "machine_running")
    if machine.status != "maintenance":
        change_status(machine, "maintenance", source="service_state", actor=actor, reason=reason,
                      expected_back_at=expected_back_at)
    return machine.status


def _machine_bookings(machine, expected_back_at):
    from apps.machines.booking_gate import bookings_in_repair
    bookings = bookings_in_repair(machine, expected_back_at)
    notify.bookers_machine_repair(machine, bookings, expected_back_at)
    return bookings


def _asset(asset, in_service):
    from apps.inventory import availability
    from apps.inventory.models import InventoryAsset
    asset = InventoryAsset.objects.select_for_update().get(pk=asset.pk)
    S = InventoryAsset.Status
    source, target = (S.MAINTENANCE, S.AVAILABLE) if in_service else (S.AVAILABLE, S.MAINTENANCE)
    if asset.status != source:
        raise errors.bad_state(f"A unit that is {asset.status} cannot change service state.", "asset_state")
    availability.move_asset_status(asset, target)
    return target


def _product(product, in_service, quantity):
    from apps.inventory import availability
    if type(quantity) is not int or quantity < 1:
        raise ValidationError({"quantity": "Say how many units change state."})
    try:
        if in_service:
            availability.repair_from_needs_fix(product, quantity)
        else:
            availability.move_available_to_needs_fix(product, quantity)
    except availability.InsufficientStock as exc:
        raise errors.bad_state(str(exc), "insufficient_stock")
    return "available" if in_service else "needs_fix"


def _room(actor, space, room, in_service, reason, expected_back_at, mode, issue):
    from apps.maintenance.models import RoomOutage
    current = open_outage(room)
    if in_service:
        if current is not None:
            from django.utils import timezone
            current.ended_at, current.ended_by = timezone.now(), actor
            current.save(update_fields=["ended_at", "ended_by"])
        return "in_service", current, []
    if current is not None:
        raise errors.bad_state("This room is already out of service.", "room_out_of_service")
    if mode not in RoomOutage.Mode.values:
        raise ValidationError({"mode": "Choose block or warn."})
    outage = RoomOutage.objects.create(makerspace=space, room=room, mode=mode, reason=str(reason or "")[:300],
                                       expected_back_at=expected_back_at, started_by=actor, issue=issue)
    bookings = list(affected_bookings(outage))
    notify.bookers_outage(outage, bookings)
    return f"out_of_service:{mode}", outage, bookings


@transaction.atomic
def set_state(actor, space, *, subject_type, subject, in_service, reason="", expected_back_at=None,
              quantity=None, mode="block", issue=None):
    """Returns {"state": ..., "outage": RoomOutage|None, "bookings": [Booking, ...]}."""
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(space.pk)
    if subject.makerspace_id != space.pk or (issue is not None and issue.makerspace_id != space.pk):
        raise ValidationError({"subject_id": "The subject must belong to this makerspace."})
    _gate(actor, space, subject_type, subject)
    outage, bookings = None, []
    if subject_type == "machine":
        was_down = subject.status == "maintenance"
        state = _machine(actor, subject, in_service, reason, expected_back_at)
        if not in_service and not was_down:
            bookings = _machine_bookings(subject, expected_back_at)
    elif subject_type == "inventory_asset":
        state = _asset(subject, in_service)
    elif subject_type == "inventory_product":
        state = _product(subject, in_service, quantity)
    else:
        state, outage, bookings = _room(actor, space, subject, in_service, reason, expected_back_at, mode, issue)
    meta = {"subject_type": subject_type, f"{areas.SUBJECT_FIELD[subject_type]}_id": subject.pk,
            "in_service": bool(in_service), "state": state, "affected_bookings": len(bookings),
            "outage_id": getattr(outage, "pk", None)}
    if issue is not None:
        history.step(issue, "service_state", actor, "service_state.changed", note=reason, meta=meta)
    else:
        audit.record(actor, "service_state.changed", makerspace=space, target=subject, meta=meta)
    return {"state": state, "outage": outage, "bookings": bookings}
