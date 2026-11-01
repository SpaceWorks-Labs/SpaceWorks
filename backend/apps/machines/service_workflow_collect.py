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


def collect(service_request, actor, *, pickup_code="", collector_name=""):
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
        by_code = _check_handover(locked, pickup_code)
        name = str(collector_name or "").strip()[:120] or _member_name(locked)
        locked.status, locked.handled_by, locked.collected_by, locked.collected_at = MachineServiceRequest.Status.COLLECTED, actor, actor, timezone.now()
        locked.collected_by_name = name
        locked.save(update_fields=["status", "handled_by", "collected_by", "collected_at", "collected_by_name",
                                   "updated_at"])
        _audit_transition(actor, locked, "collected", extra={"by_code": by_code})
        _notify_after_commit(locked, "collected")
        return locked


def _check_handover(locked, pickup_code):
    """#142 OQ-15 and the pay-before-pickup switch. Returns whether the code was shown."""
    from rest_framework.exceptions import ValidationError

    from apps.machines import job_charges, job_pickup, job_policy
    from apps.makerspaces.platform import feature_enabled
    if pickup_code and not job_pickup.matches(locked, pickup_code):
        raise ValidationError({"pickup_code": "That pickup code does not match this job.", "code": "pickup_code"})
    if feature_enabled(locked.makerspace, job_policy.PAY_BEFORE_PICKUP):
        payment = job_charges.prepaid_payment(locked) if locked.prepay else job_charges.payment_for(locked)
        if payment is not None and payment.status == payment.Status.PENDING:
            from apps.machines.job_rules import JobRuleRefused
            raise JobRuleRefused("payment_due", "This job's charge must be settled before pickup.",
                                 payment_id=payment.pk)
    return bool(pickup_code)


def _member_name(locked):
    owner = locked.member or locked.requester
    return (getattr(owner, "display_name", "") or getattr(owner, "username", "") or "")[:120]


def mark_uncollected(service_request, actor, *, now=None):
    """#142 OQ-7: from day 14 staff mark a finished job Not collected (the item is the space's)."""
    from datetime import timedelta

    from apps.machines import job_policy
    from apps.machines.service_errors import ServiceInvalidTransition
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
        _require_edge(locked, MachineServiceRequest.Status.UNCOLLECTED)
        now = now or timezone.now()
        if locked.completed_at and now - locked.completed_at < timedelta(days=job_policy.UNCOLLECTED_AFTER_DAYS):
            raise ServiceInvalidTransition(
                f"A job can be marked not collected {job_policy.UNCOLLECTED_AFTER_DAYS} days after it was ready.")
        locked.status, locked.handled_by, locked.uncollected_at = MachineServiceRequest.Status.UNCOLLECTED, actor, now
        locked.save(update_fields=["status", "handled_by", "uncollected_at", "updated_at"])
        _audit_transition(actor, locked, "uncollected")
        from apps.machines.notifications_job_flow import flag_no_shows, notify_job
        notify_job(locked, "uncollected")
        flag_no_shows(locked)
        return locked
