from django.utils.translation import gettext
from datetime import datetime, time, timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.makerspaces.models import Makerspace
from apps.operations import reports
from apps.operations.report_date_ranges import CalendarDateRange
from apps.operations.report_registry import REPORT_DEFINITIONS, REPORT_REGISTRY


def _require_source_modules(makerspace, modules):
    from .report_sources import require_source

    for module in modules:
        require_source(makerspace, module)


def _date_range(request, makerspace=None):
    return date_range_from_dates(_date_param(request, "start"), _date_param(request, "end"), makerspace=makerspace)


def date_range_from_dates(start, end, *, makerspace=None):
    """Inclusive calendar dates -> the half-open aware datetime range every builder takes.

    Shared by the export views and the scheduled-report runner so a schedule's stored
    `start`/`end` mean exactly what the same dates mean on a manual export.
    """
    if start and end and start > end:
        raise ValidationError({"end": gettext("End date must be on or after start date.")})
    try:
        if makerspace is not None:
            from apps.makerspaces.local_time import local_day_bounds
            start_dt = local_day_bounds(makerspace, start)[0] if start else None
            end_dt = local_day_bounds(makerspace, end)[1] if end else None
        else:
            start_dt = timezone.make_aware(datetime.combine(start, time.min)) if start else None
            end_dt = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min)) if end else None
    except (OverflowError, ValueError) as exc:
        raise ValidationError({"end" if end else "start": gettext("Date range exceeds the supported calendar.")}) from exc
    return CalendarDateRange((start_dt, end_dt)) if start_dt or end_dt else None


def _date_param(request, name):
    raw = (request.query_params.get(name) or "").strip()
    if not raw:
        return None
    try:
        parsed = parse_date(raw)
    except ValueError:
        parsed = None
    if parsed is None:
        raise ValidationError({name: gettext("Use YYYY-MM-DD.")})
    return parsed


def refuse_handout_only(user, makerspace):
    """Decision 224(d): a counter-only (handout-only) role gets no inventory-wide report or export.

    The desk role holds view_inventory for item lookup and availability, which are served by
    the hardware routes, not here; reports and exports are a manager's surface.
    """
    if rbac.is_handout_only(user, makerspace.id):
        raise PermissionDenied()
    return makerspace


def _makerspace_for_inventory_view(user, makerspace_id):
    queryset = rbac.scope_by_action(
        user, rbac.Action.VIEW_INVENTORY, Makerspace.objects.all(), field="id"
    )
    return refuse_handout_only(user, get_object_or_404(queryset, pk=makerspace_id))


def makerspace_for_members_view(user, makerspace_id):
    """m23: resolve through manage_members (not view_inventory), so a custom manage_members-only role
    gets the page the console shows it instead of a 404; handout-only roles stay refused."""
    queryset = rbac.scope_by_action(user, rbac.Action.MANAGE_MEMBERS, Makerspace.objects.all(), field="id")
    return refuse_handout_only(user, get_object_or_404(queryset, pk=makerspace_id))


def _makerspace_for_report_view(user, makerspace_id, report_key, subject_kind=None):
    """Inventory scope UNION the requested report's own action scope.

    Resolving through inventory alone locked out a VIEW_AUDIT-only reader (custom role or
    organization grant) of the audit report. The union keeps the pinned matrix: an
    inventory-visible actor without the report action still resolves and gets 403 from
    the explicit check; an actor with neither still gets 404; and an unknown key adds
    nothing, so it cannot help an actor with no inventory scope enumerate a makerspace.
    The registry lookup never invokes a builder.
    """
    if report_key == "organization-membership":
        # Global organization membership is an ORG + PLAT projection. A local
        # makerspace grant does not authorize its owner's global membership data.
        raise reports.ReportNotFound()
    spaces = Makerspace.objects.all()
    queryset = rbac.scope_by_action(user, rbac.Action.VIEW_INVENTORY, spaces, field="id")
    definition = REPORT_REGISTRY.get(report_key)
    if definition is not None and definition.platform_only:
        raise reports.ReportNotFound()
    if definition is not None:
        from .report_types import definition_actions
        for action in definition_actions(definition):
            queryset = queryset | rbac.scope_by_action(user, action, spaces, field="id")
        from .report_subjects import subject_capable
        if subject_capable(definition):
            # The resource-grant path: tenant VIEW_AUDIT plus the subject's own grant.
            queryset = queryset | rbac.scope_by_action(
                user, rbac.Action.VIEW_AUDIT, spaces, field="id"
            )
    if definition is not None and subject_kind:
        from .report_subjects import SUBJECTS
        adapter = SUBJECTS.get(subject_kind)
        if adapter and adapter.grantee_gate and report_key in adapter.report_keys and adapter.grantee_gate(user, makerspace_id):
            queryset = queryset | spaces.filter(pk=makerspace_id)  # decision 248 / EB1: a per-resource grantee
    return refuse_handout_only(user, get_object_or_404(queryset.distinct(), pk=makerspace_id))


def _makerspace_for_catalog(user, makerspace_id):
    queryset = Makerspace.objects.none()
    from .report_types import definition_actions
    actions = {action for definition in REPORT_DEFINITIONS if not definition.platform_only
               for action in definition_actions(definition)}
    for action in actions:
        queryset = queryset | rbac.scope_by_action(
            user, action, Makerspace.objects.all(), field="id"
        )
    return refuse_handout_only(user, get_object_or_404(queryset.distinct(), pk=makerspace_id))


def _require_superadmin(user):
    if not (user.is_superuser or user.role == user.Role.SUPERADMIN):
        raise PermissionDenied()


def _positive_int_param(request, name, default, maximum):
    raw = request.query_params.get(name, default)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError({name: gettext("Enter a positive integer.")}) from exc
    if value < 1:
        raise ValidationError({name: gettext("Enter a positive integer.")})
    return min(value, maximum)


def _page_params(request):
    return (
        _positive_int_param(request, "page", 1, 1000000),
        _positive_int_param(request, "page_size", 100, 500),
    )


def _limit_param(request):
    return _positive_int_param(
        request, "limit", reports.DEFAULT_REPORT_LIMIT, reports.MAX_REPORT_LIMIT
    )
