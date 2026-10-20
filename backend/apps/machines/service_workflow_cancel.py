"""Cancellation of a waiting or running machine-service job (decision 45).

One atomic transaction, in the shared lock order (C1): write fence -> request ->
scope (queue row / bucket machine, only for a waiting row) -> assigned machine (only for
a running row) -> consumable pool. Any hold is released with ZERO consumption before
the terminal transition is saved; no consumption debit, no charge. The owner's
``cancelled`` intent is reserved under its immutable marker and, for a waiting row, the
scope's new accepted head is re-evaluated for its once-only ``next`` notice. A device
report arriving afterwards is refused by ``printer_access.live_target`` (not running).
"""

from django.db import transaction
from django.utils import timezone

from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.machines import role_scope
from apps.machines.models import MachineServiceRequest
from apps.machines.service_queue_notices import initiator_for, reevaluate_head, reserve_milestone
from apps.machines.service_workflow_helpers import (
    _assert_request_write_allowed,
    _audit_transition,
    _lock_assigned_machine,
    _lock_scope,
    _locked_request,
    _notify_after_commit,
    _release_hold,
    _release_queue_machine,
    _require_edge,
    _require_module,
)

Status = MachineServiceRequest.Status
CANCELLABLE = frozenset({Status.PENDING, Status.ACCEPTED, Status.IN_PROGRESS})


def owner_may_cancel(row, user, *, service_enabled=None):
    """Owner-surface eligibility; claim sessions never own a job's account controls.

    List callers pass ``service_enabled`` once so the module gate is not re-read per row.
    """
    if service_enabled is None:
        from apps.makerspaces.platform import module_enabled
        service_enabled = module_enabled(row.makerspace, "machine_service")
    return bool(
        service_enabled and row.status in CANCELLABLE and user is not None
        and row.member_id == getattr(user, "pk", None)
        and getattr(user, "_claim_audit_context", None) is None
        and user.is_active and user.access_status == "active"
    )


class CancelRefused(PermissionDenied):
    """The caller no longer owns, or may no longer manage, this job (re-checked under lock)."""


def _assert_authority(locked, actor, by_owner):
    if by_owner:
        if locked.member_id is None or locked.member_id != getattr(actor, "pk", None):
            raise CancelRefused("Only the request owner can cancel this job.")
        if not (actor.is_active and actor.access_status == "active"):
            raise CancelRefused("Only an active account can cancel this job.")
        return
    if not rbac.can(actor, rbac.Action.MANAGE_MACHINES, locked.makerspace_id):
        raise CancelRefused("Machine management permission is required.")
    # The view resolved the row through the actor's machine partition before the lock;
    # re-check it here so a scope narrowed in that window refuses the cancel.
    if not role_scope.covers_service_request(actor, locked):
        raise CancelRefused("This job is outside your machine scope.")


def cancel(service_request, actor, *, reason="", by_owner=False):
    """Cancel a pending, accepted or in-progress job; repeat calls return the result."""
    reason = str(reason or "").strip()
    with transaction.atomic():
        _assert_request_write_allowed(service_request)
        locked = _locked_request(service_request)
        # After waiting on a concurrent writer, Postgres re-checks only the locked row:
        # joined relations (pool, assigned machine) can be from the older snapshot.
        # Re-read everything now that the row lock is held.
        locked.refresh_from_db()
        _assert_authority(locked, actor, by_owner)
        if locked.status == Status.CANCELLED:
            return locked
        _require_module(locked.makerspace)
        _require_edge(locked, Status.CANCELLED)
        previous = locked.status
        running = previous == Status.IN_PROGRESS
        if running:
            _lock_assigned_machine(locked)
        else:
            _lock_scope(locked)
        released = _release_hold(locked, actor, reason=reason or "cancelled")
        locked.status, locked.cancelled_at = Status.CANCELLED, timezone.now()
        fields = ["status", "cancelled_at", "updated_at"]
        if reason:
            locked.reason = reason
            fields.append("reason")
        if not by_owner:
            locked.handled_by = actor
            fields.append("handled_by")
        locked.save(update_fields=fields)
        if running:
            # Only the cancelled RUNNING job frees its machine; maintenance/offline stay put.
            _release_queue_machine(locked, actor)
        _audit_transition(actor, locked, "cancelled", extra={
            "previous_status": previous, "reason": reason,
            "cancelled_by": "owner" if by_owner else "staff",
            "released_hold": released,
            "released_machine_id": locked.assigned_machine_id if running else None,
        })
        initiator = initiator_for(actor)
        reserve_milestone(locked, "cancelled", initiator=initiator)
        if not running:
            reevaluate_head(locked, initiator=initiator)
        _notify_after_commit(locked, "cancelled")
        return locked
