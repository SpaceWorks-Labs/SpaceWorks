"""The sole state-transition authority for machine service requests."""

from apps.accounts.account_kind_guards import require_member_account

from django.db import transaction
from django.utils import timezone
from apps.accounts.account_obligations import lock_obligation_owner

from apps.makerspaces import limits
from apps.machines import role_scope
from apps.machines.certifications import require_certification_for_member
from apps.machines.models import Machine, MachineServiceRequest, ServiceBucket, ServiceQueue, get_or_create_default_bucket
from apps.machines.service_consumption import debit_consumptions
from apps.machines.service_errors import ServiceConsumptionInvalid, ServiceInvalidTransition, ServiceMachineUnavailable
from apps.machines.service_queue_notices import initiator_for, reevaluate_head, reserve_milestone
from apps.machines.service_workflow_helpers import (
    _assert_request_write_allowed,
    _assert_submission_write_allowed,
    _audit_transition,
    _decimal,
    _lock_assigned_machine,
    _locked_request,
    _locked_submission_machine,
    _locked_submission_target,
    _lock_scope,
    _minutes,
    _notify_after_commit,
    _percent,
    _release_hold,
    _release_queue_machine,
    _require_available,
    _require_edge,
    _require_module,
    _require_printer_start_inputs,
    _submission_makerspace_id,
    _validate_capability_payload,
)


def submit(bucket_or_machine, requester, *, requester_name, contact_email, contact_phone, title, description="", source_link="", actor=None, member=None, capability_payload=None, certification_override_reason=""):
    """Create a pending legacy bucket request or unassigned pooled request."""
    require_member_account(requester)
    if member is not None:
        require_member_account(member)
    with transaction.atomic():
        _assert_submission_write_allowed(bucket_or_machine)
        # Makerspace fence FIRST, then the queue / bucket machine: the same order as the
        # device printer adapter (makerspace -> ... -> request -> machine), so submit can
        # never close a submit/device/request->queue lock cycle.
        _require_module(_submission_makerspace_id(bucket_or_machine), locked=True)
        target = _locked_submission_target(bucket_or_machine) if isinstance(bucket_or_machine, ServiceQueue) else _locked_submission_machine(bucket_or_machine)
        makerspace = target.makerspace
        machine_type = target.machine_type if isinstance(target, ServiceQueue) else target.machine_type
        _validate_capability_payload(machine_type, capability_payload or {}, makerspace)
        # Certification gating. Only for a member-attributed submission: an anonymous or
        # staff-entered request is somebody asking staff to run the machine, which is not
        # the member operating it, so there is nothing to have been trained for.
        require_certification_for_member(
            makerspace, member, machine_type, purpose="service", actor=actor,
            override_reason=certification_override_reason,
        )
        owner = lock_obligation_owner(member if member is not None else requester)
        if member is not None:
            member = owner
        else:
            requester = owner
        limits.check_quota(makerspace, "machine_service_open", adding=1)
        limits.check_quota(makerspace, "machine_service_submit", adding=1)
        if isinstance(target, ServiceQueue):
            if not target.is_active:
                raise ServiceMachineUnavailable("Service queue is inactive.")
            bucket, queue, assigned = None, target, None
        else:
            _require_available(target)
            bucket = get_or_create_default_bucket(target, makerspace=makerspace)
            queue, assigned = None, target
        service_request = MachineServiceRequest.objects.create(
            bucket=bucket, queue=queue, makerspace=makerspace, requester=requester, member=member,
            requester_name=(requester_name or "").strip(), contact_email=(contact_email or "").strip(),
            contact_phone=(contact_phone or "").strip(), title=(title or "").strip(),
            description=(description or "").strip(), source_link=(source_link or "").strip(),
            capability_payload=capability_payload or {}, assigned_machine=assigned,
        )
        _audit_transition(actor, service_request, "submitted")
        _notify_after_commit(service_request, "submitted")
        return service_request


def accept(service_request, actor, *, estimated_minutes=None, planned_grams=None, note="", override_length=False):
    with transaction.atomic():
        _assert_request_write_allowed(service_request)
        locked = _locked_request(service_request)
        _require_module(locked.makerspace)
        _require_edge(locked, MachineServiceRequest.Status.ACCEPTED)
        if locked.status == MachineServiceRequest.Status.QUOTED:
            raise ServiceInvalidTransition("A quoted job enters the queue when the member approves it.")
        _lock_scope(locked)
        if estimated_minutes is not None:
            locked.estimated_minutes = _minutes(estimated_minutes, "estimated_minutes")
        from apps.machines.job_rules import require_acceptable
        require_acceptable(locked, planned_grams=planned_grams, override_length=override_length)
        if planned_grams is not None:
            grams = _decimal(planned_grams, "planned_grams")
            if grams < 0:
                raise ServiceConsumptionInvalid("planned_grams must be non-negative.")
            locked.planned_grams = grams
            payload = dict(locked.capability_payload or {})
            if grams:
                payload["estimated_grams"] = str(grams)
            else:
                payload.pop("estimated_grams", None)
            locked.capability_payload = payload
        if note:
            locked.reason = str(note).strip()
        locked.status, locked.handled_by, locked.accepted_by, locked.accepted_at = MachineServiceRequest.Status.ACCEPTED, actor, actor, timezone.now()
        locked.save(update_fields=["status", "handled_by", "accepted_by", "accepted_at", "estimated_minutes", "planned_grams", "capability_payload", "reason", "updated_at"])
        _audit_transition(actor, locked, "accepted")
        reevaluate_head(locked, initiator=initiator_for(actor))
        _notify_after_commit(locked, "accepted")
        return locked


def reject(service_request, actor, *, reason, code=""):
    with transaction.atomic():
        _assert_request_write_allowed(service_request)
        if not str(reason or "").strip():
            raise ServiceConsumptionInvalid("A rejection reason is required.")
        locked = _locked_request(service_request)
        _require_module(locked.makerspace)
        _require_edge(locked, MachineServiceRequest.Status.REJECTED)
        _lock_scope(locked)
        locked.refresh_from_db()  # fresh hold fields/relations under the lock
        released = _release_hold(locked, actor, reason=str(reason).strip())
        locked.status, locked.handled_by, locked.reason = MachineServiceRequest.Status.REJECTED, actor, str(reason).strip()
        locked.reject_code = str(code or "")[:32]
        locked.save(update_fields=["status", "handled_by", "reason", "reject_code", "updated_at"])
        _audit_transition(actor, locked, "rejected", extra={"released_hold": released, "code": locked.reject_code})
        reevaluate_head(locked, initiator=initiator_for(actor))
        _notify_after_commit(locked, "rejected")
        return locked


def complete(service_request, actor, *, actual_minutes, consumptions, actual_grams=None, actual_quantity=None, initiator=None, pickup_location=""):
    with transaction.atomic():
        _assert_request_write_allowed(service_request)
        locked = _locked_request(service_request)
        _require_module(locked.makerspace)
        _require_edge(locked, MachineServiceRequest.Status.COMPLETED)
        _lock_assigned_machine(locked)
        locked.actual_minutes = _minutes(actual_minutes, "actual_minutes")
        debit_consumptions(locked, actor, consumptions, outcome="completed")
        if locked.run_consumable_pool_id:
            from apps.machines.service_consumable_pools import reconcile_request
            reconcile_request(locked, actor, actual_grams=locked.planned_grams if actual_grams is None else actual_grams,
                              actual_quantity=actual_quantity)
            locked.refresh_from_db()
            locked.actual_minutes = _minutes(actual_minutes, "actual_minutes")
        locked.status, locked.handled_by, locked.completed_at = MachineServiceRequest.Status.COMPLETED, actor, timezone.now()
        from apps.machines.job_pickup import new_pickup_code
        locked.pickup_code, locked.pickup_location = new_pickup_code(), str(pickup_location or "").strip()[:120]
        locked.save(update_fields=["status", "handled_by", "actual_minutes", "completed_at", "pickup_code",
                                   "pickup_location", "updated_at"])
        from .consumable_costs import record_service_cost
        record_service_cost(locked, actor)
        _release_queue_machine(locked, actor)
        _audit_transition(actor, locked, "completed")
        reserve_milestone(locked, "completed", initiator=initiator or initiator_for(actor))
        _notify_after_commit(locked, "completed")
        from apps.machines.job_charges import charge_completed
        charge_completed(locked, actor)
        return locked


def fail(service_request, actor, *, reason, percent_complete, actual_minutes, consumptions, actual_grams=None, actual_quantity=None, code="", fault=""):
    with transaction.atomic():
        _assert_request_write_allowed(service_request)
        if not str(reason or "").strip():
            raise ServiceConsumptionInvalid("A failure reason is required.")
        locked = _locked_request(service_request)
        _require_module(locked.makerspace)
        _require_edge(locked, MachineServiceRequest.Status.FAILED)
        _lock_assigned_machine(locked)
        locked.actual_minutes, locked.fail_percent_complete, locked.reason, locked.failed_at = _minutes(actual_minutes, "actual_minutes"), _percent(percent_complete), str(reason).strip(), timezone.now()
        debit_consumptions(locked, actor, consumptions, outcome="failed")
        if locked.run_consumable_pool_id:
            from apps.machines.service_consumable_pools import reconcile_request
            if locked.reserved_quantity is not None and locked.metering_unit != "weight":
                expected_quantity = locked.reserved_quantity * locked.fail_percent_complete / 100
                reconcile_request(locked, actor,
                                  actual_quantity=expected_quantity if actual_quantity is None else actual_quantity,
                                  reason=locked.reason)
            else:
                expected = locked.planned_grams * locked.fail_percent_complete / 100
                reconcile_request(locked, actor, actual_grams=expected if actual_grams is None else actual_grams,
                                  reason=locked.reason)
            locked.refresh_from_db()
            locked.actual_minutes = _minutes(actual_minutes, "actual_minutes")
            locked.fail_percent_complete = _percent(percent_complete)
            locked.reason = str(reason).strip()
            locked.failed_at = timezone.now()
        from apps.machines.service_workflow_failure import after_fail, validate_failure
        locked.fail_code, locked.fail_fault = validate_failure(code, fault)
        locked.status, locked.handled_by = MachineServiceRequest.Status.FAILED, actor
        locked.save(update_fields=["status", "handled_by", "actual_minutes", "fail_percent_complete", "reason", "failed_at",
                                   "fail_code", "fail_fault", "updated_at"])
        from .consumable_costs import record_service_cost
        record_service_cost(locked, actor)
        _release_queue_machine(locked, actor)
        _audit_transition(actor, locked, "failed", extra={"code": locked.fail_code, "fault": locked.fail_fault})
        _notify_after_commit(locked, "failed")
        after_fail(locked, actor)
        return locked


def create_reprint(service_request, actor):
    """Create an accepted child request that retains the original attachment root."""
    with transaction.atomic():
        _assert_request_write_allowed(service_request)
        from apps.makerspaces.models import Makerspace
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        assert_write_allowed(service_request.makerspace_id)
        Makerspace.objects.select_for_update().get(pk=service_request.makerspace_id)
        original = _locked_request(service_request)
        lock_obligation_owner(original.member if original.member_id else original.requester)
        if original.status not in {MachineServiceRequest.Status.FAILED, MachineServiceRequest.Status.COMPLETED, MachineServiceRequest.Status.COLLECTED}:
            raise ServiceInvalidTransition("Only terminal service requests can be reprinted.")
        root = original.reprint_of or original
        _lock_scope(original)
        child = MachineServiceRequest.objects.create(
            bucket=original.bucket, queue=original.queue, makerspace=original.makerspace, requester=original.requester, member=original.member,
            requester_name=original.requester_name, contact_email=original.contact_email, contact_phone=original.contact_phone,
            title=original.title, description=original.description, source_link=original.source_link,
            capability_payload=original.capability_payload, status=MachineServiceRequest.Status.ACCEPTED,
            assigned_machine=original.assigned_machine if original.bucket_id else None, accepted_by=actor,
            accepted_at=timezone.now(), estimated_minutes=original.estimated_minutes, planned_grams=original.planned_grams,
            reprint_of=root,
            # A re-run keeps the original's place (#142: reprints keep their place) and,
            # when prepaid, is covered by the original's charge.
            queued_at=original.queued_at or original.created_at, urgent=original.urgent, prepay=original.prepay,
            copies=original.copies, own_material=original.own_material, material_note=original.material_note,
        )
        _audit_transition(actor, child, "reprint_created", extra={"reprint_of_id": root.pk})
        reevaluate_head(child, initiator=initiator_for(actor))
        _notify_after_commit(child, "reprinted")
        return child


# Re-exported so `service_workflow_actions.start` keeps resolving for existing callers.
from apps.machines.service_workflow_start import start  # noqa: E402
from apps.machines.service_workflow_cancel import cancel  # noqa: E402
from apps.machines.service_workflow_collect import collect  # noqa: E402
