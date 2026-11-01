"""Staff queue-board edits (#141, #142 OQ-6): reorder, urgent pin, pre-assign a machine.

None of these is a status transition; each is audited, takes the scope lock like every
queue writer, and re-evaluates the once-only "You're next" notice because the head of
the queue may have changed.
"""

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.machines import role_scope
from apps.machines.job_order import anchor_for_position
from apps.machines.models import Machine, MachineServiceRequest
from apps.machines.service_errors import ServiceInvalidTransition
from apps.machines.service_queue_notices import initiator_for, reevaluate_head
from apps.machines.service_workflow_helpers import (
    _assert_request_write_allowed, _audit_transition, _lock_scope, _locked_request, _require_module,
)

Status = MachineServiceRequest.Status
QUEUED = (Status.PENDING, Status.ACCEPTED)


def _open(service_request, *, statuses=(Status.ACCEPTED,)):
    _assert_request_write_allowed(service_request)
    locked = _locked_request(service_request)
    locked.refresh_from_db()
    _require_module(locked.makerspace)
    if locked.status not in statuses:
        raise ServiceInvalidTransition("Only a job waiting in the queue can be moved.")
    _lock_scope(locked)
    return locked


def reorder(service_request, actor, *, position):
    with transaction.atomic():
        locked = _open(service_request)
        before = locked.queued_at
        locked.queued_at = anchor_for_position(locked, position)
        locked.save(update_fields=["queued_at", "updated_at"])
        _audit_transition(actor, locked, "reordered", extra={
            "position": int(position), "from": before.isoformat() if before else None,
            "to": locked.queued_at.isoformat()})
        reevaluate_head(locked, initiator=initiator_for(actor))
        return locked


def pin_urgent(service_request, actor, *, urgent, reason=""):
    reason = str(reason or "").strip()[:200]
    if urgent and not reason:
        raise ValidationError({"reason": "Say why this job is urgent."})
    with transaction.atomic():
        locked = _open(service_request, statuses=QUEUED)
        locked.urgent, locked.urgent_reason = bool(urgent), reason if urgent else ""
        locked.save(update_fields=["urgent", "urgent_reason", "updated_at"])
        _audit_transition(actor, locked, "urgent_pinned" if urgent else "urgent_unpinned")
        reevaluate_head(locked, initiator=initiator_for(actor))
        return locked


def assign_machine(service_request, actor, *, machine_id):
    """Pre-assign a waiting job to one compatible machine in the actor's scope (or clear it)."""
    with transaction.atomic():
        locked = _open(service_request, statuses=QUEUED)
        machine = None
        if machine_id is not None:
            machine_type_id = locked.queue.machine_type_id if locked.queue_id else locked.bucket.machine.machine_type_id
            scope = role_scope.scope_q_for(role_scope.manage_scope_for(actor, locked.makerspace_id),
                                           machine_id_paths=("pk",), type_id_paths=("machine_type_id",))
            machine = Machine.objects.filter(scope, pk=machine_id, makerspace_id=locked.makerspace_id,
                                             machine_type_id=machine_type_id, is_active=True).first()
            if machine is None:
                raise ValidationError({"machine_id": "Choose an active compatible machine you manage."})
        locked.preassigned_machine = machine
        locked.save(update_fields=["preassigned_machine", "updated_at"])
        _audit_transition(actor, locked, "machine_preassigned", extra={"machine_id": machine_id})
        return locked
