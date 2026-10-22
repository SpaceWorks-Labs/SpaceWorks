"""Who may see a refund case: the staff who own its subject, plus finance read-only (R9).

The queue follows the same rule as `reconciliation_authority.payment_list_action`:
a case belongs to the domain that raised its charge, so an Event Manager sees event
cases and a Machine Manager sees cases for the jobs their role scope covers. Holders
of VIEW_FINANCE see every case in the space but cannot decide one -- deciding goes
back through `_require_subject_authority` per case.
"""

from django.db.models import Q
from rest_framework.exceptions import NotFound

from apps.accounts import rbac
from apps.payments.models import Payment, RefundCase
from apps.payments.reconciliation_authority import SUBJECT_ACTIONS

FIELD = "payment__makerspace_id"


def visible_cases(actor, makerspace_id):
    """Every case in one makerspace this actor may read; empty when none."""
    base = RefundCase.objects.filter(payment__makerspace_id=makerspace_id)
    if rbac.can(actor, rbac.Action.VIEW_FINANCE, makerspace_id):
        return rbac.scope_by_action(actor, rbac.Action.VIEW_FINANCE, base, field=FIELD)
    allowed = Q(pk__in=[])
    for subject_type, action in SUBJECT_ACTIONS.items():
        if not rbac.can(actor, action, makerspace_id):
            continue
        rows = rbac.scope_by_action(actor, action, base.filter(payment__subject_type=subject_type), field=FIELD)
        if subject_type == Payment.SubjectType.MACHINE_SERVICE_REQUEST:
            rows = rows.filter(payment__subject_id__in=_covered_jobs(actor, makerspace_id))
        allowed |= Q(pk__in=rows.values("pk"))
    return base.filter(allowed)


def _covered_jobs(actor, makerspace_id):
    from apps.machines.models import MachineServiceRequest
    from apps.machines.role_scope import scoped_service_requests

    jobs = MachineServiceRequest.objects.filter(makerspace_id=makerspace_id)
    return scoped_service_requests(actor, jobs, {makerspace_id}).values("pk")


def may_read_queue(actor, makerspace_id):
    return rbac.can(actor, rbac.Action.VIEW_FINANCE, makerspace_id) or any(
        rbac.can(actor, action, makerspace_id) for action in set(SUBJECT_ACTIONS.values())
    )


def require_queue(actor, makerspace_id):
    """404, not 403, for a space the actor has no refund authority in: no disclosure."""
    from apps.makerspaces.servability import servable_queryset

    if not may_read_queue(actor, makerspace_id) or not servable_queryset().filter(pk=makerspace_id).exists():
        raise NotFound("Makerspace not found.")


def with_case_rows(queryset):
    """Everything `RefundCaseSerializer` reads, fetched for the page in bulk."""
    return queryset.select_related("payment__makerspace", "payment__member", "refund").prefetch_related(
        "payment__refunds__amended_by", "refund__amended_by",
    )


def get_visible_case(actor, makerspace_id, case_id):
    case = with_case_rows(visible_cases(actor, makerspace_id)).filter(pk=case_id).first()
    if case is None:
        raise NotFound("Refund case not found.")
    return case
