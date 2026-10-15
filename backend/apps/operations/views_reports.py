from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.makerspaces.guards import require_module
from apps.makerspaces.platform import module_enabled
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
from apps.operations.serializers_report_catalog import ReportCatalogSerializer
from apps.operations.report_request_contract import (
    DATE_RANGE_PARAMETERS,
    PAYMENT_FILTER_PARAMETERS,
    PREVIEW_PARAMETERS,
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
        require_action(request.user, definition.required_action, makerspace.id)
        require_module(makerspace, "reports")
        _require_source_modules(makerspace, definition.required_modules)
        return Response(reports.report_data(
            report_key, makerspace.id,
            actor=request.user,
            limit=_limit_param(request), date_range=_date_range(request, makerspace if request.query_params.get("subject_kind") or definition.subject_kind or report_key in {"member-retention", "membership-revenue"} else None),
            report_filters=_report_filters(request, report_key), grain=_grain_param(request, definition),
        ))


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
            # General report controls cannot supply an exact domain subject.
            # Subject-only reports remain available from their resource's UI.
            if definition.subject_kind:
                continue
            if not rbac.can(request.user, definition.required_action, makerspace.id):
                continue
            missing = [key for key in definition.required_modules if not module_enabled(makerspace, key)]
            if definition.required_feature:
                from apps.makerspaces.platform import feature_enabled
                if not feature_enabled(makerspace, definition.required_feature):
                    missing.append(definition.required_feature)
            entries.append(_catalog_entry(
                definition, available=not missing,
                reason=f"Required module disabled: {', '.join(missing)}" if missing else None,
            ))
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
        return Response({"results": [
            _catalog_entry(definition, available=None, reason=None)
            for definition in DEPLOYMENT_AGGREGATE_REPORT_DEFINITIONS
        ]})


class AccountabilityReportView(APIView):
    permission_classes = [IsActiveStaff]
    serializer_class = GenericObjectSerializer

    @extend_schema(
        tags=["Analytics"], summary="Requester accountability dashboard",
        request=None, responses={200: OpenApiTypes.OBJECT, **ERROR_RESPONSES},
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
        definition = reports.validate_report_key(report_key, deployment_aggregate=True)
        return Response(reports.report_data(
            report_key, limit=_limit_param(request), date_range=_date_range(request),
            actor=request.user,
            report_filters=_report_filters(request, report_key),
            grain=_grain_param(request, definition),
        ))


class ReportExportView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [ReportRenderThrottle]
    serializer_class = EmptySerializer

    @extend_schema(
        tags=["Reports"], summary="Export report", request=None,
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
        require_action(request.user, definition.required_action, makerspace.id)
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
        definition = reports.validate_report_key(
            report_key, for_export=True, deployment_aggregate=True
        )
        return _export_response(request, definition, None)


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
        "aggregate_supported": definition.key in STRATEGIES,
        "allowed_formats": list(definition.allowed_formats),
        "schedulable": definition.schedulable, "previewable": definition.previewable,
        "condition_metrics": list(condition_metrics(definition)),
    }
