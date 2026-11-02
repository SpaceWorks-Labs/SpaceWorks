"""What happens after a job fails (#142 OQ-8): reason code, fault, re-queue or charge.

Called by `fail()` inside its transaction, after the failed row is saved and audited:

* **space or machine fault** -- the job is re-run FREE at the front of its queue (the
  re-run keeps the original's place), at most twice automatically; after that staff
  decide (`staff_decide`). A prepaid job is covered by its original charge.
* **member or file fault** -- the member resubmits from a prefilled form, and the type's
  failure charge applies (default none; material only or full where the space set it),
  raised through L15's `create_for_failed_request`.
* **no fault given** (e.g. a device report) -- nothing automatic; staff decide.

The member sees the outcome on the job timeline.
"""

from apps.machines.service_errors import ServiceConsumptionInvalid

FAIL_CODES = ("adhesion", "nozzle_jam", "material_ran_out", "machine_fault", "power_cut", "operator_error",
              "file_problem", "material_defect", "other")
SPACE, MEMBER = "space", "member"


def validate_failure(code, fault):
    code, fault = str(code or "").strip(), str(fault or "").strip()
    if code and code not in FAIL_CODES:
        raise ServiceConsumptionInvalid("Unknown failure reason.")
    if fault and fault not in (SPACE, MEMBER):
        raise ServiceConsumptionInvalid("Fault must be the space's or the member's.")
    return code or "other", fault


def _set_outcome(row, outcome):
    from apps.machines.models import MachineServiceRequest
    MachineServiceRequest.objects.filter(pk=row.pk).update(failure_outcome=outcome)
    row.failure_outcome = outcome


def _requeue(row_id, actor_id, root_id):
    import logging

    from apps.accounts.models import User
    from apps.machines.models import MachineServiceRequest
    from apps.machines.service_workflow_actions import create_reprint
    from apps.machines.service_workflow_helpers import _audit_transition
    row = MachineServiceRequest.objects.get(pk=row_id)
    actor = User.objects.filter(pk=actor_id).first() if actor_id else None
    try:
        child = create_reprint(row, actor)
    except Exception:
        logging.getLogger(__name__).exception("machine_job_requeue_failed", extra={"service_request_id": row_id})
        _set_outcome(row, "staff_decide")
        return None
    MachineServiceRequest.objects.filter(pk=child.pk).update(auto_requeue_count=row.auto_requeue_count + 1)
    _audit_transition(actor, row, "requeued", extra={"rerun_id": child.pk, "root_id": root_id})
    from apps.machines.notifications_job_flow import notify_job
    notify_job(row, "requeued")
    return child


def after_fail(row, actor):
    from apps.machines import job_charges, job_policy
    if row.fail_fault == SPACE:
        root = row.reprint_of or row
        if row.auto_requeue_count < job_policy.MAX_AUTO_REQUEUES:
            # After commit, in its own transaction: `create_reprint` takes the makerspace
            # lock before the request, the order every writer uses.
            from django.db import transaction
            transaction.on_commit(lambda: _requeue(row.pk, getattr(actor, "pk", None), root.pk))
            _set_outcome(row, "requeued")
            return None
        _set_outcome(row, "staff_decide")
        return None
    if row.fail_fault == MEMBER:
        from apps.machines.job_rules import machine_type_of
        charge = job_policy.member_fault_charge(row.makerspace, machine_type_of(row))
        payment = job_charges.charge_failed(row, actor, charge)
        _set_outcome(row, "charged" if payment is not None else "free")
        if row.prepay:
            job_charges.open_refund_due(row, actor)
        return payment
    _set_outcome(row, "staff_decide")
    return None
