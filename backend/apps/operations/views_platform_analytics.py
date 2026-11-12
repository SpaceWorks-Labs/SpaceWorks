"""Only these superadmin views mint platform analytics authority."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset
from apps.operations import reports
from apps.operations.platform_scope import _platform_context_for_view
from apps.operations.report_request_contract import DATE_RANGE_PARAMETERS, _grain_param
from apps.operations.serializers_report_catalog import PlatformAnalyticsReportSerializer
from apps.operations.views_report_helpers import _date_range, _limit_param
from apps.operations.views_reports import ERROR_RESPONSES

PLATFORM_KEYS = ("platform-services", "platform-usage", "platform-channel-usage")


class AnalyticsMakerspaceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()


class AnalyticsMakerspacePageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = AnalyticsMakerspaceSerializer(many=True)


class AnalyticsPickerPagination(PageNumberPagination):
    page_size = 24


class PlatformAnalyticsView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(
        tags=["Analytics"], summary="Get superadmin platform analytics", request=None,
        description="Platform-only counts with the definition's typed chart_spec across every servable makerspace. Connect includes attributed ledger facts, with no provider-attempt failure history.",
        parameters=[OpenApiParameter("report_key", OpenApiTypes.STR, OpenApiParameter.PATH, enum=PLATFORM_KEYS),
                    *DATE_RANGE_PARAMETERS, OpenApiParameter("limit", OpenApiTypes.INT, OpenApiParameter.QUERY),
                    OpenApiParameter("grain", OpenApiTypes.STR, OpenApiParameter.QUERY, enum=["day", "week", "month"])],
        responses={200: PlatformAnalyticsReportSerializer, **ERROR_RESPONSES},
    )
    def get(self, request, report_key, *args, **kwargs):
        from .report_subjects import reject_aggregate
        reject_aggregate(request.query_params)
        ctx = _platform_context_for_view(request)
        if report_key not in PLATFORM_KEYS:
            raise reports.ReportNotFound()
        definition = reports.validate_report_key(report_key, platform_context=ctx)
        data = reports.report_data(report_key, actor=request.user, platform_context=ctx,
                                   limit=_limit_param(request), date_range=_date_range(request),
                                   grain=_grain_param(request, definition))
        return Response({**data, "chart_spec": definition.chart_spec})


class PlatformAnalyticsMakerspacesView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(
        tags=["Analytics"], summary="List makerspaces available for tenant analytics", request=None,
        description="Paginated platform picker of servable makerspaces. Each tenant read rechecks report actions and modules through explicit platform read routes.",
        parameters=[OpenApiParameter("report_key", OpenApiTypes.STR, OpenApiParameter.QUERY, description="Tenant report key; defaults to summary."),
                    OpenApiParameter("page", OpenApiTypes.INT, OpenApiParameter.QUERY)],
        responses={200: AnalyticsMakerspacePageSerializer, **ERROR_RESPONSES},
    )
    def get(self, request, *args, **kwargs):
        _platform_context_for_view(request)
        definition = reports.validate_report_key(request.query_params.get("report_key") or "summary")
        if definition.key == "organization-membership":
            raise reports.ReportNotFound()
        spaces = rbac.scope_by_action(request.user, definition.required_action, servable_queryset(Makerspace.objects.all()), field="id")
        spaces = spaces.filter(enabled_modules__contains=["reports"])
        from .report_sources import filter_sources
        spaces = filter_sources(spaces, definition.required_modules)
        pager = AnalyticsPickerPagination()
        page = pager.paginate_queryset(spaces.order_by("name", "pk").distinct(), request, view=self)
        return pager.get_paginated_response(AnalyticsMakerspaceSerializer(page, many=True).data)
