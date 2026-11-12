"""Acceptance rules of the job flow: the quote rule and the per-type length cap (#142).

* OQ-2: when the machine type asks for quotes (always, above an amount, or -- the
  default -- whenever the job is priced), staff send a quote instead of accepting.
* OQ-10: a job estimated longer than the type's `max_job_minutes` needs staff to say so
  (`override_length`), and is audited as an override.
"""

from django.utils.translation import gettext
from rest_framework import status
from rest_framework.exceptions import APIException

from apps.machines import job_policy


class JobRuleRefused(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "job_rule"

    def __init__(self, code, detail, **extra):
        super().__init__({"detail": detail, "code": code, **extra}, code)


def machine_type_of(row):
    return row.queue.machine_type if row.queue_id else row.bucket.machine.machine_type


def require_acceptable(row, *, planned_grams=None, override_length=False):
    machine_type = machine_type_of(row)
    policy = job_policy.policy_for(row.makerspace, machine_type)
    if policy.max_job_minutes and row.estimated_minutes > policy.max_job_minutes and not override_length:
        raise JobRuleRefused("job_too_long", gettext("This job is longer than this machine type allows. Confirm the "
                             "override to accept it."), max_job_minutes=policy.max_job_minutes)
    from apps.makerspaces.platform import feature_enabled
    if not feature_enabled(row.makerspace, job_policy.JOB_QUOTES) or not job_policy.charges_tracked(row.makerspace):
        return
    from apps.machines.service_workflow_review import quote_preview
    quantity = planned_grams if planned_grams is not None else row.planned_grams
    try:
        total = quote_preview(row, minutes=row.estimated_minutes, quantity=quantity).total
    except Exception:
        total = 0
    if job_policy.quote_required(row.makerspace, machine_type, total):
        raise JobRuleRefused("quote_required", gettext("This machine type needs a quote the member approves before "
                             "the job joins the queue. Send a quote instead."))


def require_open_job_limit(makerspace, member, machine_type):
    """OQ-10: at most `max_open_jobs` unfinished jobs per member and type (off when unset)."""
    policy = job_policy.policy_for(makerspace, machine_type)
    if not policy.max_open_jobs or member is None:
        return
    from django.db.models import Q

    from apps.machines.models import MachineServiceRequest as Job
    open_states = (Job.Status.PENDING, Job.Status.CHANGES_REQUESTED, Job.Status.QUOTED, Job.Status.ACCEPTED,
                   Job.Status.IN_PROGRESS)
    count = Job.objects.filter(
        Q(queue__machine_type=machine_type) | Q(bucket__machine__machine_type=machine_type),
        makerspace=makerspace, member=member, status__in=open_states).count()
    if count >= policy.max_open_jobs:
        raise JobRuleRefused("job_limit_reached", gettext("You already have the most open jobs allowed for this machine "
                             "type."), max_open_jobs=policy.max_open_jobs)
