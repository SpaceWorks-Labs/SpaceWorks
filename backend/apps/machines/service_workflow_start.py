"""The accepted -> in_progress transition, split out of service_workflow_actions.

Every lock is ``no_key=True, of=("self",)``: FOR NO KEY UPDATE still serializes workflow
writers (it conflicts with itself and with FOR UPDATE) but never with the FOR KEY SHARE
locks a concurrent commit's deferred foreign-key checks take; a joined or plain FOR UPDATE
deadlocked start/submit/cancel against the device printer adapter.

Lock order (C1/C13/C15): write fence -> request -> scope (pooled queue row, or the
bucket's own machine) -> chosen machine(s) in id order -> consumable pool. The queue's
in-progress count is read BEFORE locking the chosen machine and without a row lock:
every entry into in_progress already holds the queue lock, so it can only over-count.
"""

from django.db import transaction
from django.utils import timezone

from apps.machines import role_scope
from apps.machines.models import Machine, MachineServiceRequest, ServiceQueue
from apps.machines.service_errors import ServiceConsumptionInvalid, ServiceMachineUnavailable
from apps.machines.service_workflow_helpers import (
    _assert_request_write_allowed,
    _audit_transition,
    _locked_request,
    _minutes,
    _notify_after_commit,
    _require_available,
    _require_edge,
    _require_module,
    _require_printer_start_inputs,
)


def _choose_machine(locked, queue, candidate_scope, machine_id):
    if machine_id is None and queue and queue.allocation_policy == ServiceQueue.AllocationPolicy.FIRST_IDLE:
        return Machine.objects.select_for_update(no_key=True, of=("self",)).select_related("makerspace", "machine_type").filter(
            candidate_scope,
            makerspace_id=locked.makerspace_id, machine_type_id=queue.machine_type_id,
            is_active=True, status=Machine.Status.IDLE,
        ).order_by("id").first()
    if machine_id is None:
        raise ServiceMachineUnavailable("A machine is required to start service.")
    if not locked.queue_id:
        # C15: the bucket's own machine (its scope lock) and the chosen one, in id order.
        chosen = None
        for pk in sorted({locked.bucket.machine_id, machine_id}):
            rows = Machine.objects.select_for_update(no_key=True, of=("self",)).select_related("makerspace", "machine_type").filter(pk=pk)
            if pk == machine_id:
                chosen = rows.filter(candidate_scope).first()
            else:
                rows.first()
        return chosen
    return Machine.objects.select_for_update(no_key=True, of=("self",)).select_related("makerspace", "machine_type").filter(
        candidate_scope, pk=machine_id,
    ).first()


def start(service_request, actor, machine_scope, *, machine_id=None, estimated_minutes=None, consumable_pool_id=None, planned_grams=None, planned_quantity=None):
    with transaction.atomic():
        _assert_request_write_allowed(service_request)
        locked = _locked_request(service_request)
        _require_module(locked.makerspace)
        _require_edge(locked, MachineServiceRequest.Status.IN_PROGRESS)
        queue = None
        if locked.queue_id:
            queue = ServiceQueue.objects.select_for_update(no_key=True, of=("self",)).select_related("makerspace", "machine_type").get(pk=locked.queue_id)
            locked.queue = queue
            if queue.capacity is not None:
                active = MachineServiceRequest.objects.filter(
                    queue_id=queue.pk, status=MachineServiceRequest.Status.IN_PROGRESS).count()
                if active >= queue.capacity:
                    raise ServiceMachineUnavailable("Service queue capacity has been reached.")
        candidate_scope = role_scope.scope_q_for(
            machine_scope,
            machine_id_paths=("pk",),
            type_id_paths=("machine_type_id",),
        )
        machine = _choose_machine(locked, queue, candidate_scope, machine_id)
        if machine is None or machine.makerspace_id != locked.makerspace_id:
            raise ServiceMachineUnavailable("Machine is not available for this service request.")
        if locked.queue_id and machine.machine_type_id != queue.machine_type_id:
            raise ServiceMachineUnavailable("Machine is not compatible with this service queue.")
        _require_available(machine)
        if MachineServiceRequest.objects.filter(
            assigned_machine_id=machine.pk, status=MachineServiceRequest.Status.IN_PROGRESS,
        ).exclude(pk=locked.pk).exists():
            # C8: a coherent in-progress row governs availability whatever the flag says.
            raise ServiceMachineUnavailable("Machine is not available for service requests.")
        if estimated_minutes is not None:
            locked.estimated_minutes = _minutes(estimated_minutes, "estimated_minutes")
        _require_printer_start_inputs(locked, machine, consumable_pool_id, planned_grams)
        if consumable_pool_id is not None or planned_grams is not None or planned_quantity is not None:
            if consumable_pool_id is None or (planned_grams is None) == (planned_quantity is None):
                raise ServiceConsumptionInvalid("A consumable pool and exactly one planned quantity must be supplied together.")
            from apps.machines.models import MachineConsumablePool
            from apps.machines.service_consumable_pools import reserve_for_request
            reserve_for_request(locked, actor, pool=MachineConsumablePool.objects.get(pk=consumable_pool_id),
                                planned_grams=planned_grams, planned_quantity=planned_quantity, machine=machine)
            locked.refresh_from_db()
        locked.assigned_machine, locked.status, locked.handled_by, locked.started_at = machine, MachineServiceRequest.Status.IN_PROGRESS, actor, timezone.now()
        locked.run_machine_name = machine.name
        locked.run_machine_model = str((machine.type_payload or {}).get("model", ""))
        locked.run_estimated_minutes = locked.estimated_minutes
        locked.run_planned_grams = locked.planned_grams
        if locked.run_consumable_pool_id:
            pool = locked.run_consumable_pool
            locked.run_consumable_label, locked.run_consumable_material, locked.run_consumable_color = pool.label, pool.material, pool.color
        locked.save(update_fields=["assigned_machine", "status", "handled_by", "started_at", "estimated_minutes", "run_machine_name", "run_machine_model", "run_consumable_label", "run_consumable_material", "run_consumable_color", "run_estimated_minutes", "run_planned_grams", "updated_at"])
        machine.status = Machine.Status.RUNNING
        machine.save(update_fields=["status", "updated_at"])
        _audit_transition(actor, locked, "assigned", extra={"machine_id": machine.pk})
        _audit_transition(actor, locked, "started")
        from apps.machines.service_queue_notices import initiator_for, reevaluate_head, reserve_milestone
        reserve_milestone(locked, "started", initiator=initiator_for(actor))
        reevaluate_head(locked, initiator=initiator_for(actor))
        _notify_after_commit(locked, "started")
        return locked
