"""Staff list routes: an adapter's access decisions and usage records, and a binding's dispatched jobs.

Same gate as every adapter staff route (the machines.integrations switch, MANAGE_DEVICES in the space, machine scope
for a machine binding; cross-tenant ids are 404). DRF page-number pagination (count/next/previous/results), newest
first. A malformed filter is a 400, never silently ignored.
"""
from django.utils.translation import gettext
from uuid import UUID

from django.utils.dateparse import parse_datetime
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.devices.adapter_access import scoped_adapter, scoped_binding, visible_rows
from apps.devices.models import AdapterAccessLog, AdapterUsageLog
from apps.devices.models_printers import PrinterJob
from apps.devices.serializers_adapter_logs import AccessDecisionSerializer, BindingJobSerializer, UsageRecordSerializer
from apps.devices.openapi_adapter_staff import page
from apps.devices.views_adapter_admin import ERRORS, TAG

_BINDING = OpenApiParameter("binding", OpenApiTypes.UUID, description="Only this binding of the adapter.")
_SINCE = OpenApiParameter("since", OpenApiTypes.DATETIME, description="created_at >= (ISO 8601).")
_UNTIL = OpenApiParameter("until", OpenApiTypes.DATETIME, description="created_at <= (ISO 8601).")
ACCESS_PARAMS = [_BINDING, _SINCE, _UNTIL, OpenApiParameter("allowed", OpenApiTypes.BOOL),
                 OpenApiParameter("reason", OpenApiTypes.STR), OpenApiParameter("credential_type", OpenApiTypes.STR)]
USAGE_PARAMS = [_BINDING, _SINCE, _UNTIL, OpenApiParameter("outcome", OpenApiTypes.STR)]
JOB_PARAMS = [OpenApiParameter("state", OpenApiTypes.STR,
                               description="awaiting | reported | applied | needs_review | cancelled")]


def _paginate(request, queryset, serializer):
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(queryset, request, view=None)
    return paginator.get_paginated_response(serializer(page, many=True).data)


def _window(request, queryset):
    for param, lookup in (("since", "created_at__gte"), ("until", "created_at__lte")):
        raw = request.query_params.get(param)
        if raw:
            value = parse_datetime(raw)
            if value is None:
                raise ValidationError({param: gettext("Use an ISO 8601 date-time.")})
            queryset = queryset.filter(**{lookup: value})
    return queryset


def _binding_filter(request, queryset, device):
    raw = request.query_params.get("binding")
    if raw:
        try:
            queryset = queryset.filter(binding_id=UUID(raw), binding__device=device)
        except ValueError as exc:
            raise ValidationError({"binding": gettext("Not a valid id.")}) from exc
    return queryset


def _equals(request, queryset, *names):
    for name in names:
        raw = request.query_params.get(name)
        if raw:
            queryset = queryset.filter(**{name: raw})
    return queryset


class AdapterAccessDecisionListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="An adapter's access decisions, grant and deny (paginated, newest first)",
                   parameters=ACCESS_PARAMS, responses={200: page("AdapterAccessDecisionPage", AccessDecisionSerializer), **ERRORS})
    def get(self, request, pk):
        device = scoped_adapter(request.user, pk)
        rows = visible_rows(request.user, device,
                            AdapterAccessLog.objects.filter(device=device, makerspace_id=device.makerspace_id))
        rows = _equals(request, _window(request, _binding_filter(request, rows, device)), "reason", "credential_type")
        allowed = request.query_params.get("allowed")
        if allowed:
            if allowed.lower() not in ("true", "false", "1", "0"):
                raise ValidationError({"allowed": gettext("Use true or false.")})
            rows = rows.filter(allowed=allowed.lower() in ("true", "1"))
        return _paginate(request, rows.order_by("-created_at", "-id"), AccessDecisionSerializer)


class AdapterUsageListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=[TAG], summary="An adapter's reported usage records (paginated, newest first)",
                   parameters=USAGE_PARAMS, responses={200: page("AdapterUsageRecordPage", UsageRecordSerializer), **ERRORS})
    def get(self, request, pk):
        device = scoped_adapter(request.user, pk)
        rows = visible_rows(request.user, device,
                            AdapterUsageLog.objects.filter(device=device, makerspace_id=device.makerspace_id))
        rows = _equals(request, _window(request, _binding_filter(request, rows, device)), "outcome")
        return _paginate(request, rows.order_by("-created_at", "-id"), UsageRecordSerializer)


def binding_jobs(request, pk):
    """A machine binding's dispatched jobs (the adapter's PrinterJobs for its machine) with the command state."""
    binding = scoped_binding(request.user, pk)
    rows = PrinterJob.objects.none()
    if binding.machine_id is not None:
        rows = PrinterJob.objects.filter(device=binding.device, makerspace_id=binding.makerspace_id,
                                         machine_id_snapshot=binding.machine_id).select_related("command")
        state = request.query_params.get("state")
        if state:
            rows = rows.filter(state=state)
    return _paginate(request, rows.order_by("-created_at", "-id"), BindingJobSerializer)
