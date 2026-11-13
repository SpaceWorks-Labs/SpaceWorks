"""Batch start (#142 OQ-9): several queued jobs on one machine run (a plate or a sheet).

Each job still goes accepted -> in progress through `start` (its own consumable hold,
estimate snapshot, audit row and notice); the batch only lets them share the machine.
Completing a batch splits the run's actual time and material across its jobs in
proportion to each job's estimate, unless staff give the split themselves, then
completes each job through `complete`. Cancelling stays per job (staff only once
running), and the machine frees when the batch's last job ends.
"""

from django.utils.translation import gettext
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.machines import role_scope
from apps.machines.job_policy import BATCH_START
from apps.machines.models import Machine, MachineJobBatch, MachineServiceRequest
from apps.makerspaces.guards import require_feature

Status = MachineServiceRequest.Status


def start_batch(jobs, actor, *, machine_id, plans=None, note=""):
    """`plans`: {job_id: {estimated_minutes, consumable_pool_id, planned_grams|planned_quantity}}."""
    from apps.machines.service_workflow_start import start
    jobs = list(jobs)
    if len(jobs) < 2:
        raise ValidationError({"jobs": gettext("A batch needs at least two jobs.")})
    spaces = {job.makerspace_id for job in jobs}
    if len(spaces) != 1:
        raise ValidationError({"jobs": gettext("A batch runs in one makerspace.")})
    plans = plans or {}
    with transaction.atomic():
        space_id = spaces.pop()
        require_feature(space_id, BATCH_START)
        machine = Machine.objects.filter(pk=machine_id, makerspace_id=space_id, is_active=True).first()
        if machine is None:
            raise ValidationError({"machine_id": gettext("Choose an active machine.")})
        batch = MachineJobBatch.objects.create(makerspace_id=space_id, machine=machine, started_by=actor,
                                               note=str(note or "")[:200])
        scope = role_scope.manage_scope_for(actor, space_id)
        started = [start(job, actor, scope, machine_id=machine.pk, batch=batch, **plans.get(job.pk, {}))
                   for job in sorted(jobs, key=lambda row: row.pk)]
        return batch, started


def _shares(jobs, total, overrides, field):
    if field in overrides:
        values = overrides[field]
        return {job.pk: Decimal(str(values[job.pk])) for job in jobs}
    weights = {job.pk: Decimal(job.run_estimated_minutes or job.estimated_minutes or 1) for job in jobs}
    whole = sum(weights.values())
    return {pk: (Decimal(total) * weight / whole).quantize(Decimal("0.01"), ROUND_HALF_UP)
            for pk, weight in weights.items()}


def complete_batch(batch, actor, *, actual_minutes, actual_quantity=None, splits=None, pickup_location=""):
    """`splits`: optional {"minutes": {job_id: n}, "quantity": {job_id: q}} set by staff."""
    from apps.machines.service_workflow_actions import complete
    splits = splits or {}
    with transaction.atomic():
        jobs = list(MachineServiceRequest.objects.filter(batch=batch, status=Status.IN_PROGRESS).order_by("pk"))
        if not jobs:
            raise ValidationError({"batch": gettext("This batch has no running jobs.")})
        minutes = _shares(jobs, actual_minutes, splits, "minutes")
        quantities = _shares(jobs, actual_quantity, splits, "quantity") if actual_quantity is not None else {}
        done = []
        for job in jobs:
            kwargs = {"actual_minutes": int(minutes[job.pk]), "consumptions": [], "pickup_location": pickup_location}
            if job.run_consumable_pool_id and job.pk in quantities:
                key = "actual_quantity" if job.reserved_quantity is not None else "actual_grams"
                kwargs[key] = quantities[job.pk]
            done.append(complete(job, actor, **kwargs))
        return done
