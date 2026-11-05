from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.makerspaces.guards import require_module
from apps.operations import accountability, reports
from apps.operations.org_report_strategies import STRATEGIES
from apps.operations.report_registry import (
    DEPLOYMENT_AGGREGATE_REPORT_DEFINITIONS,
    DEPLOYMENT_AGGREGATE_REPORT_KEYS,
    REPORT_DEFINITIONS,
)
from apps.operations.report_exports import _csv_response, _xlsx_cell, _xlsx_response
from apps.operations.report_condition_metrics import condition_metrics
from apps.operations.report_exports_provenance import (
    actor_label,
    build_provenance,
    export_filters,
)
from apps.operations.schemas_reports import ANALYTICS_REPORT_RESPONSE
from apps.operations.serializers import EmptySerializer, GenericObjectSerializer
from apps.operations.serializers_reports import ReportErrorSerializer
from apps.operations.serializers_problem_reports import AccountabilityReportSerializer
from apps.operations.serializers_report_catalog import ReportCatalogSerializer
from apps.operations.report_request_contract import (
    DATE_RANGE_PARAMETERS,
    PAYMENT_FILTER_PARAMETERS,
    PREVIEW_PARAMETERS,
    SUBJECT_REPORT_DESCRIPTION,
    RETENTION_PARAMETERS,
    _export_format,
    _grain_param,
    _report_filters,
)
from apps.operations.views_report_helpers import (
    _date_range,
    _limit_param,
    _makerspace_for_catalog,
    _makerspace_for_inventory_view,
    _makerspace_for_report_view,
    _page_params,
    _require_source_modules,
    _require_superadmin,
)
from .report_render_throttles import ReportRenderThrottle
from .report_download import _export_response
from .report_definitions_machines import MACHINE_REPORT_KEYS


ERROR_RESPONSES = {
    400: OpenApiResponse(ReportErrorSerializer, description="Invalid report request."),
    401: OpenApiResponse(ReportErrorSerializer, description="Authentication required."),
    403: OpenApiResponse(ReportErrorSerializer, description="Permission denied."),
    404: OpenApiResponse(ReportErrorSerializer, description="Makerspace or report not found."),
}
EXPORT_RESPONSES = {
    429: OpenApiResponse(ReportErrorSerializer, description="Render rate limit exceeded."),
    (200, "application/pdf"): OpenApiTypes.BINARY,
    (200, "text/csv"): OpenApiTypes.STR,
    (200, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"): OpenApiTypes.BINARY,
    **ERROR_RESPONSES,
}


class AnalyticsView(APIView):
    permission_classes = [IsActiveStaff]
    serializer_class = GenericObjectSerializer

    @extend_schema(
        tags=["Analytics"], summary="Get analytics report", request=None,
        description=SUBJECT_REPORT_DESCRIPTION,
        parameters=PREVIEW_PARAMETERS,
        responses={200: ANALYTICS_REPORT_RESPONSE, **ERROR_RESPONSES},
    )
    def get(self, request, makerspace_id, report_key="summary", *args, **kwargs):
        # Inventory-first resolution, deliberately: scoping the queryset by the REPORT's
        # own action would turn "you may not run this report" into a 404 instead of a
        # 403, which is the contract pinned by
        # test_report_rbac_status_codes_match_inventory_first_resolution.
        makerspace = _makerspace_for_report_view(request.user, makerspace_id, report_key)
        definition = reports.validate_report_key(report_key)
        if not definition.previewable:
            raise reports.ReportNotFound()
        from .report_subjects import require_report_action
        require_report_action(request.user, definition, makerspace.id, request.query_params)
        require_module(makerspace, "reports")
        _require_source_modules(makerspace, definition.required_modules)
        # Membership/money builders resolve calendar labels per space, including
        # organization runs; only subject adapters take pre-resolved instants.
        response = Response(reports.report_data(
            report_key, makerspace.id,
            actor=request.user,
            limit=_limit_param(request), date_range=_date_range(request, makerspace if request.query_params.get("subject_kind") or definition.subject_kind or report_key in MACHINE_REPORT_KEYS else None),
            report_filters=_report_filters(request, report_key), grain=_grain_param(request, definition),
        ))
        if definition.subject_kind or request.query_params.get("subject_kind"):
            response["Cache-Control"] = "private, no-store"
        return response


class ReportCatalogView(APIView):
    permission_classes = [IsActiveStaff]
    serializer_class = ReportCatalogSerializer

    @extend_schema(
        tags=["Reports"], summary="List makerspace report catalog", request=None,
        responses={200: ReportCatalogSerializer, **ERROR_RESPONSES},
    )
    def get(self, request, makerspace_id, *args, **kwargs):
        makerspace = _makerspace_for_catalog(request.user, makerspace_id)
        require_module(makerspace, "reports")
        entries = []
        for definition in REPORT_DEFINITIONS:
            if definition.key == "organization-membership":
                continue
            if definition.key == "presence-top-visitors" and not rbac.can(request.user, rbac.Action.VIEW_AUDIT, makerspace.id):
                continue
            # General report controls cannot supply an exact domain subject.
            # Subject-only reports remain available from their resource's UI.
            if definition.subject_kind or definition.platform_only:
                continue
            from .report_types import definition_actions
            if not any(rbac.can(request.user, action, makerspace.id) for action in definition_actions(definition)):
                continue
            if definition.key in {"machine-usage-members", "booking-top-members"} and not rbac.can(request.user, rbac.Action.VIEW_AUDIT, makerspace.id):
                continue
            # A report whose source module or capability is off is hidden, not listed
            # as disabled (#183B): an off switch leaves no menu entry behind.
            from .report_sources import definition_live
            if not definition_live(makerspace, definition):
                continue
            entries.append(_catalog_entry(definition, available=True, reason=None))
        return Response({"results": entries})


class AggregateReportCatalogView(APIView):
    permission_classes = [IsActiveStaff]
    serializer_class = ReportCatalogSerializer

    @extend_schema(
        tags=["Reports"], summary="List deployment report catalog", request=None,
        responses={200: ReportCatalogSerializer, **ERROR_RESPONSES},
    )
    def get(self, request, *args, **kwargs):
        _require_superadmin(request.user)
        from .platform_scope import _platform_context_for_view
        _platform_context_for_view(request)
        return Response({"results": [
            _catalog_entry(definition, available=None, reason=None)
            for definition in DEPLOYMENT_AGGREGATE_REPORT_DEFINITIONS
        ]})


class AccountabilityReportView(APIView):
    permission_classes = [IsActiveStaff]
    serializer_class = GenericObjectSerializer

    @extend_schema(
        tags=["Analytics"], summary="Requester accountability dashboard",
        request=None, responses={200: AccountabilityReportSerializer, **ERROR_RESPONSES},
    )
    def get(self, request, makerspace_id, *args, **kwargs):
        makerspace = _makerspace_for_inventory_view(request.user, makerspace_id)
        require_action(request.user, rbac.Action.VIEW_AUDIT, makerspace.id)
        require_module(makerspace, "reports")
        return Response(accountability.accountability_data(makerspace.id))


class AggregateAnalyticsView(APIView):
    permission_classes = [IsActiveStaff]
    serializer_class = GenericObjectSerializer

    @extend_schema(
        tags=["Analytics"], summary="Get aggregate analytics report", request=None,
        parameters=[
            OpenApiParameter(
                "report_key", OpenApiTypes.STR, OpenApiParameter.PATH,
                enum=DEPLOYMENT_AGGREGATE_REPORT_KEYS,
            ),
            *PREVIEW_PARAMETERS,
        ],
        responses={200: ANALYTICS_REPORT_RESPONSE, **ERROR_RESPONSES},
    )
    def get(self, request, report_key="summary", *args, **kwargs):
        from .report_subjects import reject_aggregate
        reject_aggregate(request.query_params)
        _require_superadmin(request.user)
        from .platform_scope import _platform_context_for_view
        context = _platform_context_for_view(request)
        definition = reports.validate_report_key(report_key, deployment_aggregate=True, platform_context=context)
        return Response(reports.report_data(
            report_key, limit=_limit_param(request), date_range=_date_range(request),
            actor=request.user,
            report_filters=_report_filters(request, report_key),
            grain=_grain_param(request, definition),
            platform_context=context,
        ))


class ReportExportView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [ReportRenderThrottle]
    serializer_class = EmptySerializer

    @extend_schema(
        tags=["Reports"], summary="Export report", request=None,
        description=SUBJECT_REPORT_DESCRIPTION,
        parameters=[
            OpenApiParameter("report_key", OpenApiTypes.STR, OpenApiParameter.PATH, enum=reports.REPORT_KEYS),
            OpenApiParameter("format", OpenApiTypes.STR, OpenApiParameter.QUERY, enum=["csv", "xlsx", "pdf"]),
            *PREVIEW_PARAMETERS[:2],
            *DATE_RANGE_PARAMETERS,
            *PAYMENT_FILTER_PARAMETERS,
            *RETENTION_PARAMETERS,
            OpenApiParameter("grain", OpenApiTypes.STR, OpenApiParameter.QUERY, enum=["day", "week", "month"]),
        ],
        responses=EXPORT_RESPONSES,
    )
    def get(self, request, makerspace_id, report_key, *args, **kwargs):
        # Inventory-first resolution, deliberately: scoping the queryset by the REPORT's
        # own action would turn "you may not run this report" into a 404 instead of a
        # 403, which is the contract pinned by
        # test_report_rbac_status_codes_match_inventory_first_resolution.
        makerspace = _makerspace_for_report_view(request.user, makerspace_id, report_key)
        definition = reports.validate_report_key(report_key, for_export=True)
        from .report_subjects import require_report_action
        require_report_action(request.user, definition, makerspace.id, request.query_params)
        require_module(makerspace, "reports")
        _require_source_modules(makerspace, definition.required_modules)
        return _export_response(request, definition, makerspace.id)


class AggregateReportExportView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [ReportRenderThrottle]
    serializer_class = EmptySerializer

    @extend_schema(
        tags=["Reports"], summary="Export aggregate report", request=None,
        parameters=[
            OpenApiParameter("report_key", OpenApiTypes.STR, OpenApiParameter.PATH, enum=DEPLOYMENT_AGGREGATE_REPORT_KEYS),
            OpenApiParameter("format", OpenApiTypes.STR, OpenApiParameter.QUERY, enum=["csv", "xlsx"]),
            *DATE_RANGE_PARAMETERS,
            *PAYMENT_FILTER_PARAMETERS,
            *RETENTION_PARAMETERS,
            OpenApiParameter("grain", OpenApiTypes.STR, OpenApiParameter.QUERY, enum=["day", "week", "month"]),
        ],
        responses=EXPORT_RESPONSES,
    )
    def get(self, request, report_key, *args, **kwargs):
        from .report_subjects import reject_aggregate
        reject_aggregate(request.query_params)
        _require_superadmin(request.user)
        from .platform_scope import _platform_context_for_view
        context = _platform_context_for_view(request)
        definition = reports.validate_report_key(
            report_key, for_export=True, deployment_aggregate=True, platform_context=context,
        )
        return _export_response(request, definition, None, platform_context=context)


def report_data(makerspace_id, report_key):
    return reports.report_data(report_key, makerspace_id)


def report_rows(makerspace_id, report_key):
    return reports.report_rows(report_key, makerspace_id)


def _catalog_entry(definition, *, available, reason):
    return {
        "key": definition.key, "title": definition.title or definition.key.replace("-", " ").title(),
        "fields": list(definition.fields), "exportable": definition.exportable,
        "summary": definition.summary, "required_modules": list(definition.required_modules),
        "available": available, "unavailable_reason": reason,
        "grains": list(definition.grains or ("day",)), "chart_hint": definition.chart_hint,
        "chart_spec": definition.chart_spec, "identity_bearing": definition.identity_bearing,
        "aggregate_supported": definition.key in STRATEGIES,
        "allowed_formats": list(definition.allowed_formats),
        "schedulable": definition.schedulable, "previewable": definition.previewable,
        "condition_metrics": list(condition_metrics(definition)),
    }
