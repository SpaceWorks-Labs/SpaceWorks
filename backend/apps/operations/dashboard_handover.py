"""Operational queues, available without enabling the analytics module."""

from django.utils import timezone

from apps.accounts import rbac
from apps.hardware_requests.models import HardwareRequest, PublicToolLoan
from apps.makerspaces.platform import feature_enabled, module_enabled


def handover_home(actor, makerspace):
    now = timezone.now()
    queues = {"ready_to_issue": 0, "due_returns": 0, "pickups": 0}
    if feature_enabled(makerspace, "loans.enabled") and module_enabled(makerspace, "request_workflow"):
        requests = rbac.scope_by_makerspace(actor, HardwareRequest.objects.filter(makerspace=makerspace))
        if rbac.can(actor, rbac.Action.ISSUE_REQUEST, makerspace.pk):
            queues["ready_to_issue"] = requests.filter(status=HardwareRequest.Status.ACCEPTED).count()
        if rbac.can(actor, rbac.Action.RETURN_REQUEST, makerspace.pk):
            # Direct loans carry a workflow request too; exclude those requests to
            # count a physical handover once.
            direct = rbac.scope_by_makerspace(actor, PublicToolLoan.objects.filter(makerspace=makerspace))
            queues["due_returns"] = requests.filter(
                status__in=("issued", "partially_returned"), return_due_at__lt=now,
            ).exclude(pk__in=direct.values("request_id")).count() + direct.filter(
                status=PublicToolLoan.Status.CHECKED_OUT, returned_at__isnull=True, due_at__lt=now,
            ).count()
    if module_enabled(makerspace, "machines") and module_enabled(makerspace, "machine_service") and rbac.can(
        actor, rbac.Action.COLLECT_SERVICE_REQUEST, makerspace.pk,
    ):
        from apps.machines.models import MachineServiceRequest
        from apps.machines import role_scope
        jobs = rbac.scope_by_makerspace(actor, MachineServiceRequest.objects.filter(
            makerspace=makerspace, status=MachineServiceRequest.Status.COMPLETED,
        ))
        if not role_scope.grants_directly(actor, makerspace.pk, rbac.Action.COLLECT_SERVICE_REQUEST):
            jobs = role_scope.scoped_service_requests(actor, jobs, [makerspace.pk])
        queues["pickups"] = jobs.count()
    return queues


def queue_only_dashboard(actor, makerspace):
    queues = handover_home(actor, makerspace)
    return {
        "scope_mode": "handover", "widgets": [], "queue_tiles": queues,
        "awaiting_issue": queues["ready_to_issue"], "overdue_loans": queues["due_returns"],
        "prints_awaiting_collection": queues["pickups"],
    }
