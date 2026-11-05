"""Prepaid machine jobs not yet started whose quote would cost less now (#163A).

A prepaid job whose quote the member approved and paid, still waiting to join the queue
or waiting in it, is re-quoted under the prices just saved with the same inputs the
staff quote used (estimated minutes, the material quantity and pool, the machine), all
read back from the frozen quote. A job that is running or finished is "used": its price
was settled at completion (`apps.machines.job_refunds` handles a cheaper actual cost).
A re-run inherits its original's charge and is never re-quoted here.
"""

from decimal import Decimal

from apps.payments.models import Payment
from apps.payments.models_pricing import PriceOverride
from apps.payments.price_drop.shares import Affected, by_total, frozen_total, settled_payments

T = PriceOverride.TargetType


def quote_inputs(job):
    """`{minutes, quantity, pool, machine}` read back from a job's frozen quote."""
    from apps.machines.models import Machine, MachineConsumablePool

    pool_id = machine_id = None
    quantity = Decimal("0")
    for line in (job.quote_snapshot or {}).get("lines") or []:
        target = line.get("target") or {}
        if line.get("component") == "material":
            quantity = Decimal(str(line.get("quantity") or 0))
            if target.get("type") == T.CONSUMABLE_POOL:
                pool_id = target.get("id")
        if target.get("type") == T.MACHINE and machine_id is None:
            machine_id = target.get("id")
    pool = MachineConsumablePool.objects.filter(pk=pool_id, makerspace_id=job.makerspace_id).first() if pool_id else None
    machine = Machine.objects.filter(pk=machine_id, makerspace_id=job.makerspace_id).first() if machine_id else None
    return {"minutes": job.estimated_minutes or 0, "quantity": quantity, "pool": pool, "machine": machine}


def requote(job):
    from apps.machines.service_workflow_review import quote_preview
    return quote_preview(job, **quote_inputs(job))


def find_jobs(makerspace):
    from apps.machines.models import MachineServiceRequest as Job

    rows = list(Job.objects.filter(
        makerspace=makerspace, prepay=True, reprint_of__isnull=True, quote_approved_at__isnull=False,
        quote_snapshot__isnull=False, status__in=(Job.Status.QUOTED, Job.Status.ACCEPTED),
    ).select_related("makerspace", "queue__machine_type", "bucket__machine__machine_type", "member", "requester")
        .order_by("pk"))
    payments = settled_payments(makerspace, Payment.SubjectType.MACHINE_SERVICE_REQUEST, [row.pk for row in rows])
    found = []
    for job in rows:
        payment = payments.get(job.pk)
        if payment is None:
            continue
        before = frozen_total(payment, job.quote_snapshot)
        after = requote(job).total
        result = by_total(payment, f"machine_job:{job.pk}", before=before, after=after)
        if result is None:
            continue
        baseline, owed = result
        found.append(Affected(area="machines", item_type="machine_job", item_id=job.pk, label=f"Machine job #{job.pk}",
                              payment=payment, before=baseline, after=after, difference=owed,
                              facts={"service_request_id": job.pk}))
    return found
