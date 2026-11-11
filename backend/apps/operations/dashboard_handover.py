"""Operational queues, available without enabling the analytics module."""

from django.utils import timezone

from apps.accounts import rbac
from apps.hardware_requests.models import HardwareRequest, PublicToolLoan
from apps.makerspaces.platform import feature_enabled, module_enabled


def _day_end(now):
    from datetime import timedelta
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def handover_home(actor, makerspace):
    now = timezone.now()
    queues = {"ready_to_issue": 0, "due_returns": 0, "due_today": 0, "overdue": 0, "pickups": 0, "to_record": 0}
    if feature_enabled(makerspace, "loans.enabled"):
        # Decision 248 / IN11: direct loans are counted on their own, so a desk that only runs direct
        # handouts (no request workflow) still sees what is due back.
        direct = rbac.scope_by_makerspace(actor, PublicToolLoan.objects.filter(makerspace=makerspace))
        open_direct = direct.filter(status=PublicToolLoan.Status.CHECKED_OUT, returned_at__isnull=True)
        due_today = overdue = 0
        if rbac.can(actor, rbac.Action.RETURN_REQUEST, makerspace.pk):
            overdue += open_direct.filter(due_at__lt=now).count()
            due_today += open_direct.filter(due_at__gte=now, due_at__lt=_day_end(now)).count()
        if module_enabled(makerspace, "request_workflow"):
            requests = rbac.scope_by_makerspace(actor, HardwareRequest.objects.filter(makerspace=makerspace))
            if rbac.can(actor, rbac.Action.ISSUE_REQUEST, makerspace.pk):
                queues["ready_to_issue"] = requests.filter(status=HardwareRequest.Status.ACCEPTED).count()
            if rbac.can(actor, rbac.Action.RETURN_REQUEST, makerspace.pk):
                # Direct loans carry a workflow request too; exclude those requests to
                # count a physical handover once.
                open_requests = requests.filter(status__in=("issued", "partially_returned")).exclude(
                    pk__in=direct.values("request_id"))
                overdue += open_requests.filter(return_due_at__lt=now).count()
                due_today += open_requests.filter(return_due_at__gte=now, return_due_at__lt=_day_end(now)).count()
        queues["overdue"], queues["due_today"], queues["due_returns"] = overdue, due_today, overdue
    if rbac.can(actor, rbac.Action.RECORD_PAYMENT, makerspace.pk):
        from apps.payments.models import Payment
        queues["to_record"] = Payment.objects.filter(makerspace=makerspace, status=Payment.Status.PENDING).count()
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
        "awaiting_issue": queues["ready_to_issue"], "overdue_loans": queues["overdue"],
        "due_today_loans": queues["due_today"], "payments_to_record": queues["to_record"],
        "prints_awaiting_collection": queues["pickups"],
    }
