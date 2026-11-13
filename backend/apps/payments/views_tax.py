"""Staff tax policy: read, change, check a GSTIN, preview a sample invoice, GSTR-1 JSON (lane L5)."""

from django.utils.translation import gettext
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.audit import services as audit
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.platform import feature_enabled
from apps.makerspaces.servability import servable_queryset
from apps.payments.models import MakerspaceTaxSettings
from apps.payments.serializers_tax import (
    GstinCheckSerializer, GstinResultSerializer, TaxPreviewRequestSerializer, TaxPreviewSerializer,
    TaxSettingsSerializer, TaxValidationErrorSerializer,
)
from apps.payments.tax.gstin import STATE_NAMES, GstinError, validate_gstin

ERRORS = {401: OpenApiResponse(ErrorSerializer), 403: OpenApiResponse(ErrorSerializer),
          404: OpenApiResponse(ErrorSerializer)}
NOT_ENABLED = {"detail": "Turn on the Tax capability (billing.tax) before choosing a tax mode.",
               "code": "tax_not_enabled"}


def _space(request, makerspace_id, *, lock=False):
    """Finance staff read the tax policy; only the Space Manager changes it (finance setting, #101)."""
    spaces = rbac.scope_by_action(request.user, rbac.Action.VIEW_FINANCE, servable_queryset(), field="pk")
    if lock:
        spaces = spaces.select_for_update()
    return get_object_or_404(spaces, pk=makerspace_id)


def _policy(space):
    return MakerspaceTaxSettings.objects.filter(makerspace=space).first() or MakerspaceTaxSettings(makerspace=space)


class TaxSettingsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Read the space's tax policy",
                   description="Requires view_finance. `enabled` reports the billing.tax capability; with it "
                               "off no tax is charged whatever the mode says.",
                   responses={200: TaxSettingsSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        return Response(TaxSettingsSerializer(_policy(_space(request, makerspace_id))).data)

    @extend_schema(tags=["Payments"], summary="Change the space's tax policy",
                   description="Space Manager only (a finance setting, 403 `setting_not_delegated`) and the "
                               "billing.tax capability (409 `tax_not_enabled`). "
                               "Applies to charges raised from now on; existing charges keep their frozen snapshot "
                               "and issued documents never change. India GST validates the GSTIN (400 "
                               "`gstin_invalid`).",
                   request=TaxSettingsSerializer,
                   responses={200: TaxSettingsSerializer, 400: OpenApiResponse(TaxValidationErrorSerializer),
                              409: OpenApiResponse(ErrorSerializer), **ERRORS})
    @transaction.atomic
    def put(self, request, makerspace_id):
        from apps.makerspaces.settings_authority import assert_setting_write

        space = _space(request, makerspace_id, lock=True)
        decision = assert_setting_write(request.user, space, "billing", "billing.tax")
        if not feature_enabled(space, "billing.tax"):
            return Response(NOT_ENABLED, status=status.HTTP_409_CONFLICT)
        policy = _policy(space)
        serializer = TaxSettingsSerializer(policy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for key, value in serializer.validated_data.items():
            setattr(policy, key, value)
        policy.updated_by = request.user
        try:
            policy.save()
        except ValidationError as exc:
            errors = exc.message_dict
            return Response({**errors, "code": "gstin_invalid" if "gstin" in errors else "tax_settings_invalid"},
                            status=status.HTTP_400_BAD_REQUEST)
        audit.record(request.user, "payment.tax_settings_updated", makerspace=space, target=space,
                     meta={"fields": sorted(serializer.validated_data), "mode": policy.mode, "via": decision.via})
        return Response(TaxSettingsSerializer(policy).data)


class GstinValidateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Check a GSTIN's format, state code and check character",
                   description="Requires view_finance. Offline check only; nothing is looked up or stored.",
                   request=GstinCheckSerializer,
                   responses={200: GstinResultSerializer, 400: OpenApiResponse(ErrorSerializer), **ERRORS})
    def post(self, request, makerspace_id):
        _space(request, makerspace_id)
        payload = GstinCheckSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            gstin = validate_gstin(payload.validated_data["gstin"])
        except GstinError as exc:
            return Response({"detail": str(exc), "code": "gstin_invalid"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"valid": True, "gstin": gstin, "state_code": gstin[:2], "state_name": STATE_NAMES[gstin[:2]]})


class TaxPreviewView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Preview a sample invoice under saved or unsaved tax settings",
                   description="Requires view_finance. Computes only; nothing is saved or numbered.",
                   request=TaxPreviewRequestSerializer,
                   responses={200: TaxPreviewSerializer, 400: OpenApiResponse(TaxValidationErrorSerializer), **ERRORS})
    def post(self, request, makerspace_id):
        from apps.payments.tax_preview import preview

        space = _space(request, makerspace_id)
        payload = TaxPreviewRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            return Response(preview(space, _policy(space), payload.validated_data))
        except ValidationError as exc:
            return Response({**exc.message_dict, "code": "tax_settings_invalid"}, status=status.HTTP_400_BAD_REQUEST)


class Gstr1JsonView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Download GSTR-1 for one month as GSTN offline-tool JSON",
                   description="Requires view_finance, `billing.tax` and India GST mode. Built from the frozen "
                               "breakdown of each tax document issued in the month; review it in the offline "
                               "tool before filing. `month` is YYYY-MM (default: last month).",
                   parameters=[OpenApiParameter("month", OpenApiTypes.STR)],
                   responses={200: OpenApiTypes.OBJECT, 409: OpenApiResponse(ErrorSerializer), **ERRORS})
    def get(self, request, makerspace_id):
        from datetime import date

        from apps.makerspaces.local_time import local_day_bounds, local_now
        from apps.operations.reports_tax_gst import gstr1_tables
        from apps.operations.reports_tax_gst_json import gstr1_json

        space = _space(request, makerspace_id)
        policy = _policy(space)
        if not feature_enabled(space, "billing.tax") or policy.mode != MakerspaceTaxSettings.Mode.GST_INDIA:
            return Response({"detail": gettext("India GST is not switched on for this space."), "code": "tax_not_enabled"},
                            status=status.HTTP_409_CONFLICT)
        raw = request.query_params.get("month") or ""
        today = local_now(space).date()
        try:
            first = date.fromisoformat(f"{raw}-01") if raw else (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        except ValueError:
            return Response({"detail": gettext("Use YYYY-MM."), "code": "month_invalid"}, status=status.HTTP_400_BAD_REQUEST)
        following = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        bounds = (local_day_bounds(space, first)[0], local_day_bounds(space, following)[0])
        tables = gstr1_tables(space, bounds)
        response = Response(gstr1_json(policy.gstin, first.strftime("%m%Y"), tables))
        response["Content-Disposition"] = f'attachment; filename="GSTR1_{policy.gstin}_{first:%m%Y}.json"'
        return response
