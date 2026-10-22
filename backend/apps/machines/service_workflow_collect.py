"""Collection of a completed machine-service job, with a locked reach re-check."""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.machines.models import MachineServiceRequest
from apps.machines.service_request_partitions import may_collect
from apps.machines.service_workflow_helpers import (
    _assert_request_write_allowed,
    _audit_transition,
    _locked_request,
    _notify_after_commit,
    _require_edge,
    _require_module,
)
from apps.makerspaces.authority_lock import ACCESS_CHANGED, require_under_lock


def collect(service_request, actor):
    """Mark a completed job collected, re-checking the collector's reach under lock.

    The staff view resolves the row through the collect partition with plain reads, so a
    role edit or a revoked direct-collect grant committed between that and this write
    would otherwise still land. Authority rows lock first (tenant -> membership/roles ->
    organizations), then the request, the same tenant-first order as every other path.
    """
    with transaction.atomic():
        _assert_request_write_allowed(service_request)
        require_under_lock(
            actor, service_request.makerspace_id,
            lambda: rbac.can(actor, rbac.Action.COLLECT_SERVICE_REQUEST, service_request.makerspace_id),
        )
        locked = _locked_request(service_request)
        if not may_collect(actor, locked):
            raise PermissionDenied(ACCESS_CHANGED)
        _require_module(locked.makerspace)
        _require_edge(locked, MachineServiceRequest.Status.COLLECTED)
        locked.status, locked.handled_by, locked.collected_by, locked.collected_at = MachineServiceRequest.Status.COLLECTED, actor, actor, timezone.now()
        locked.save(update_fields=["status", "handled_by", "collected_by", "collected_at", "updated_at"])
        _audit_transition(actor, locked, "collected")
        _notify_after_commit(locked, "collected")
        return locked
