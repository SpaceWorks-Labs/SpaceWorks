"""Shared authority, calendar and output boundaries for machine analytics."""

from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Q
from django.utils import timezone

from apps.accounts import rbac
from apps.admin_api.permissions import active_user, require_action
from apps.machines import role_scope
from apps.machines.models import Machine, MachineServiceRequest
from apps.makerspaces.guards import require_module
from apps.operations.report_types import ReportResult
from apps.operations.reports_common import limited, report_spaces

GRAINS = ("day", "week", "month")
CENT = Decimal("0.01")


def spaces(makerspace_id, modules, actor=None, *, identities=False):
    """None actor is the existing trusted internal/org builder seam.

    HTTP and scheduled dispatch always forward their actor. A resolved local role
    still narrows a superadmin, including in a hidden tenant.
    """
    if identities and (makerspace_id is None or actor is None):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied("Member analytics require a tenant staff actor.")
    queryset = report_spaces(makerspace_id, *modules)
    if actor is not None and not active_user(actor):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied()
    if makerspace_id is None:
        if actor is not None:
            queryset = rbac.scope_by_action(actor, rbac.Action.MANAGE_MACHINES, queryset, field="id")
        catalog = list(queryset)
        scopes = role_scope.manage_scopes_for(actor, [s.pk for s in catalog]) if actor is not None else {}
        groups = {}
        for space in catalog:
            # One SQL calendar bucket per timezone/source-module cohort. Keep
            # tenant identity on every fact; this batches reads, never flattens rows.
            key = (space.timezone, tuple(sorted(set(space.enabled_modules) & {"machine_service", "bookings"})))
            groups.setdefault(key, []).append(space)
        for group in groups.values():
            representative = group[0]
            representative._machine_report_ids = tuple(s.pk for s in group)
            yield representative, {s.pk: scopes.get(s.pk, role_scope.EXEMPT if actor is None else role_scope.NOTHING) for s in group}
        return
    for space in queryset:
        for module in modules:
            require_module(space, module)
        if actor is not None:
            require_action(actor, rbac.Action.MANAGE_MACHINES, space.pk)
            from .platform_scope import tenant_local_hidden_block_applies
            if tenant_local_hidden_block_applies(actor, space, rbac.Action.MANAGE_MACHINES):
                from .report_types import ReportNotFound
                raise ReportNotFound()
            if identities:
                require_action(actor, rbac.Action.VIEW_AUDIT, space.pk)
        scope = role_scope.manage_scope_for(actor, space.pk) if actor is not None else role_scope.EXEMPT
        yield space, scope


def machines(space, scope):
    return Machine.objects.filter(makerspace_id__in=space_ids(space)).filter(scope_q(
        scope, machine_id_paths=("pk",), type_id_paths=("machine_type_id",), makerspace_field="makerspace_id",
    )).order_by()


def requests(space, scope):
    return MachineServiceRequest.objects.filter(makerspace_id__in=space_ids(space)).filter(scope_q(
        scope, machine_id_paths=role_scope.SERVICE_REQUEST_MACHINE_PATHS,
        type_id_paths=role_scope.SERVICE_REQUEST_TYPE_PATHS, makerspace_field="makerspace_id",
    )).order_by()


def type_q(scope, path):
    return scope_q(scope, type_id_paths=(path,), makerspace_field="space__makerspace_id")


def space_ids(space):
    return getattr(space, "_machine_report_ids", (space.pk,))


def scope_q(scope, *, makerspace_field, **paths):
    if not isinstance(scope, dict):
        return role_scope.scope_q_for(scope, **paths)
    if not scope:
        return Q(pk__in=[])
    if all(resolved is role_scope.EXEMPT for resolved in scope.values()):
        return Q()
    query = Q(pk__in=[])
    for space_id, resolved in scope.items():
        query |= Q(**{makerspace_field: space_id}) & role_scope.scope_q_for(resolved, **paths)
    return query


def bucket(at, grain, space):
    if grain not in GRAINS:
        raise ValueError("Unsupported report grain.")
    local = at.astimezone(ZoneInfo(space.timezone))
    day = local.date()
    if grain == "week":
        day -= timedelta(days=day.weekday())
    elif grain == "month":
        day = day.replace(day=1)
    return day.isoformat()


def hours(delta):
    return Decimal(str(delta.total_seconds())) / Decimal(3600)


def measured_service_hours(request):
    # The terminal workflow records actual_minutes for failures as well as success.
    # Completion percentage describes the job outcome, not elapsed machine time.
    return Decimal(request["actual_minutes"]) / Decimal(60)


def result(fields, rows, makerspace_id, limit, **meta):
    rows = list(rows)
    for row in rows:
        for field, value in row.items():
            if isinstance(value, Decimal):
                row[field] = value.quantize(CENT)
    if makerspace_id is not None:
        rows = [{key: value for key, value in row.items() if key != "makerspace_id"} for row in rows]
    else:
        fields = ("makerspace_id", *fields)
    return ReportResult(fields, limited(rows, limit), meta)


def window(date_range, created_at):
    start, end = date_range or (None, None)
    return max(start or created_at, created_at), end or timezone.now()
