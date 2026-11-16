"""Core-only request discovery and staff authorization for context adapters."""
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound
from apps.accounts import rbac
from apps.accounts.staff_identity import is_person, is_platform
from apps.hardware_requests.models import HardwareRequest, PublicToolLoan
from apps.makerspaces.guards import require_feature, require_module

MAX_SAFE = 9007199254740991


def safe_id(value):
    if type(value) is not int or not 1 <= value <= MAX_SAFE:
        raise NotFound()
    return value


def request_for_path(makerspace_id, request_id=None, loan_id=None):
    safe_id(makerspace_id)
    if (request_id is None) == (loan_id is None):
        raise NotFound()
    if loan_id is not None:
        loan = get_object_or_404(PublicToolLoan.objects.only("request_id", "makerspace_id"),
            pk=safe_id(loan_id), makerspace_id=makerspace_id)
        request_id = loan.request_id
    return get_object_or_404(HardwareRequest.objects.all(),
        pk=safe_id(request_id), makerspace_id=makerspace_id)


def require_request_actor(actor, request):
    # Refresh model state but preserve request-bound session attributes.
    if not actor or not getattr(actor, "is_authenticated", False) or not getattr(actor, "pk", None):
        raise NotFound()
    try:
        actor.refresh_from_db()
    except ObjectDoesNotExist:  # The account row went away mid-request.
        raise NotFound() from None
    if not actor.is_active or actor.access_status != "active" or actor.is_tenant_dump_stub or actor.deletion_requested_at or actor.must_change_password or not (is_person(actor) or (is_platform(actor) and actor.is_superuser)):
        raise NotFound()
    require_module(request.makerspace, "request_workflow")
    loan = PublicToolLoan.objects.filter(request_id=request.pk).only("source", "makerspace_id").first()
    if loan and loan.makerspace_id != request.makerspace_id:
        raise NotFound()
    if loan:
        require_feature(request.makerspace, "inventory.self_checkout")
        action = (rbac.Action.ISSUE_DIRECT_LOAN if loan.source == PublicToolLoan.Source.ADMIN_DIRECT
            else rbac.Action.ISSUE_REQUEST if loan.source == PublicToolLoan.Source.PUBLIC_SELF_CHECKOUT else None)
    else:
        require_feature(request.makerspace, "loans.enabled")
        action = rbac.Action.ACCEPT_REQUEST
    if action is None or not rbac.can(actor, action, request.makerspace_id):
        raise NotFound()
    return actor


def authorized_request_queryset(actor, makerspace, queryset=None):
    """Batch the same source-action policy; never expands an optional-domain join.

    The caller must independently authorize every event/booking projection. An empty
    result means no source authority, not that no hidden context exists.
    """
    from django.db.models import Q
    from apps.makerspaces.platform import feature_enabled
    rows = HardwareRequest.objects.all() if queryset is None else queryset
    rows = rows.filter(makerspace_id=makerspace.pk)
    if not actor or not getattr(actor, "is_authenticated", False) or not getattr(actor, "pk", None):
        return rows.none()
    try:
        actor.refresh_from_db()
    except ObjectDoesNotExist:
        return rows.none()
    if not actor.is_active or actor.access_status != "active" or actor.is_tenant_dump_stub or actor.deletion_requested_at or actor.must_change_password or not (is_person(actor) or (is_platform(actor) and actor.is_superuser)):
        return rows.none()
    makerspace.refresh_from_db()
    require_module(makerspace, "request_workflow")
    allowed = Q(pk__in=[])
    if feature_enabled(makerspace, "loans.enabled") and rbac.can(actor, rbac.Action.ACCEPT_REQUEST, makerspace.pk):
        allowed |= Q(public_tool_loan__isnull=True)
    if feature_enabled(makerspace, "inventory.self_checkout"):
        if rbac.can(actor, rbac.Action.ISSUE_DIRECT_LOAN, makerspace.pk):
            allowed |= Q(public_tool_loan__source=PublicToolLoan.Source.ADMIN_DIRECT,
                         public_tool_loan__makerspace_id=makerspace.pk)
        if rbac.can(actor, rbac.Action.ISSUE_REQUEST, makerspace.pk):
            allowed |= Q(public_tool_loan__source=PublicToolLoan.Source.PUBLIC_SELF_CHECKOUT,
                         public_tool_loan__makerspace_id=makerspace.pk)
    return rows.filter(allowed)

