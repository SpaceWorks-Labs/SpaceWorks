"""Superadmin managed-hosting screens (#187A, #190 web parity). Every route 404s while
MANAGED_PLANS_ENABLED is off; writes need recent re-authentication and are audited."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.audit import services as audit
from apps.makerspaces.models import Makerspace
from apps.openapi_errors import errors

from . import billing, plans, serializers as s
from .availability import require_plans_enabled
from .models import HostingInvoice, HostingPlan, PlatformHostingBillingSettings, SpacePlanAssignment

TAGS = ["Managed hosting"]


class _Platform(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]

    def initial(self, request, *args, **kwargs):
        require_plans_enabled()
        super().initial(request, *args, **kwargs)

    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError):
            exc = PermissionDenied(" ".join(exc.messages))
        return super().handle_exception(exc)


class PlanListCreateView(_Platform):
    @extend_schema(tags=TAGS, summary="List hosting plans", responses={200: s.HostingPlanSerializer(many=True),
                                                                     **errors(401, 403, 404)})
    def get(self, request):
        return Response(s.HostingPlanSerializer(HostingPlan.objects.all(), many=True).data)

    @extend_schema(tags=TAGS, summary="Create a hosting plan", request=s.HostingPlanSerializer,
                   responses={201: s.HostingPlanSerializer, **errors(400, 401, 403, 404)})
    def post(self, request):
        body = s.HostingPlanSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        plan = plans.save_plan(request.user, body.validated_data)
        return Response(s.HostingPlanSerializer(plan).data, status=status.HTTP_201_CREATED)


class PlanDetailView(_Platform):
    @extend_schema(tags=TAGS, summary="Read a hosting plan", responses={200: s.HostingPlanSerializer,
                                                                      **errors(401, 403, 404)})
    def get(self, request, pk):
        return Response(s.HostingPlanSerializer(get_object_or_404(HostingPlan, pk=pk)).data)

    @extend_schema(tags=TAGS, summary="Change a hosting plan", request=s.HostingPlanSerializer,
                   responses={200: s.HostingPlanSerializer, **errors(400, 401, 403, 404)})
    def patch(self, request, pk):
        plan = get_object_or_404(HostingPlan, pk=pk)
        body = s.HostingPlanSerializer(plan, data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        return Response(s.HostingPlanSerializer(plans.save_plan(request.user, body.validated_data, plan)).data)


class SpacePlanView(_Platform):
    @extend_schema(tags=TAGS, summary="Read a space's hosting plan",
                   description="Answers `null` when the space has no plan (the fair-use defaults apply).",
                   responses={200: s.HostingPlanAssignmentSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        get_object_or_404(Makerspace, pk=makerspace_id)
        row = SpacePlanAssignment.objects.select_related("plan").filter(makerspace_id=makerspace_id).first()
        return Response(s.HostingPlanAssignmentSerializer(row).data if row else None)

    @extend_schema(tags=TAGS, summary="Assign a hosting plan (with an optional trial)",
                   request=s.HostingPlanAssignRequestSerializer,
                   responses={200: s.HostingPlanAssignmentSerializer, **errors(400, 401, 403, 404)})
    def put(self, request, makerspace_id):
        get_object_or_404(Makerspace, pk=makerspace_id)
        body = s.HostingPlanAssignRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        row = plans.assign(request.user, makerspace_id, body.validated_data["plan_id"],
                           trial_days=body.validated_data["trial_days"])
        return Response(s.HostingPlanAssignmentSerializer(row).data)

    @extend_schema(tags=TAGS, summary="Remove a space's hosting plan (fair-use defaults apply again)",
                   responses={204: OpenApiResponse(description="Removed."), **errors(401, 403, 404)})
    def delete(self, request, makerspace_id):
        get_object_or_404(Makerspace, pk=makerspace_id)
        plans.unassign(request.user, makerspace_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class InvoiceListCreateView(RecentReauthenticationMixin, GenericAPIView):
    permission_classes = [IsActiveSuperAdmin]
    serializer_class = s.HostingInvoiceSerializer

    def initial(self, request, *args, **kwargs):
        require_plans_enabled()
        super().initial(request, *args, **kwargs)

    @extend_schema(tags=TAGS, summary="List hosting invoices",
                   parameters=[OpenApiParameter("makerspace", int), OpenApiParameter("status", str)],
                   responses={200: s.HostingInvoiceSerializer(many=True), **errors(401, 403, 404)})
    def get(self, request):
        rows = HostingInvoice.objects.select_related("makerspace").prefetch_related("receipts__recorded_by")
        if (request.query_params.get("makerspace") or "").isdigit():
            rows = rows.filter(makerspace_id=int(request.query_params["makerspace"]))
        if request.query_params.get("status") in HostingInvoice.Status.values:
            rows = rows.filter(status=request.query_params["status"])
        page = self.paginate_queryset(rows)
        return self.get_paginated_response(s.HostingInvoiceSerializer(page, many=True).data)

    @extend_schema(tags=TAGS, summary="Record a hosting invoice for a space", request=s.HostingInvoiceCreateSerializer,
                   responses={201: s.HostingInvoiceSerializer, **errors(400, 401, 403, 404)})
    def post(self, request):
        body = s.HostingInvoiceCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        get_object_or_404(Makerspace, pk=body.validated_data["makerspace_id"])
        row = billing.create_invoice(request.user, body.validated_data)
        return Response(s.HostingInvoiceSerializer(row).data, status=status.HTTP_201_CREATED)


class InvoicePaymentView(_Platform):
    @extend_schema(tags=TAGS, summary="Record an offline payment receipt", request=s.HostingInvoicePaymentSerializer,
                   responses={200: s.HostingInvoiceSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, pk):
        get_object_or_404(HostingInvoice, pk=pk)
        body = s.HostingInvoicePaymentSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(s.HostingInvoiceSerializer(billing.record_payment(request.user, pk, **body.validated_data)).data)


class InvoiceVoidView(_Platform):
    @extend_schema(tags=TAGS, summary="Void an open hosting invoice", request=s.HostingInvoiceVoidSerializer,
                   responses={200: s.HostingInvoiceSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, pk):
        get_object_or_404(HostingInvoice, pk=pk)
        body = s.HostingInvoiceVoidSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(s.HostingInvoiceSerializer(billing.void(request.user, pk, body.validated_data["reason"])).data)


class BillingSettingsView(_Platform):
    @extend_schema(tags=TAGS, summary="Read hosting billing settings",
                   responses={200: s.HostingBillingSettingsSerializer, **errors(401, 403, 404)})
    def get(self, request):
        return Response(s.HostingBillingSettingsSerializer(PlatformHostingBillingSettings.load()).data)

    @extend_schema(tags=TAGS, summary="Change hosting billing settings (secrets are write-only)",
                   request=s.HostingBillingSettingsSerializer,
                   responses={200: s.HostingBillingSettingsSerializer, **errors(400, 401, 403, 404)})
    def patch(self, request):
        with transaction.atomic():
            row = PlatformHostingBillingSettings.objects.select_for_update().get(pk=PlatformHostingBillingSettings.load().pk)
            body = s.HostingBillingSettingsSerializer(row, data=request.data, partial=True)
            body.is_valid(raise_exception=True)
            data = dict(body.validated_data)
            for field in PlatformHostingBillingSettings.SECRET_FIELDS:
                if field in data:
                    row.set_secret(field, data.pop(field))
            for name, value in data.items():
                setattr(row, name, value)
            row.updated_by = request.user
            row.save()
            audit.record(request.user, "managed_hosting.billing_settings_updated", makerspace=None, target=row,
                         meta={"fields": sorted(set(request.data) & set(s.HostingBillingSettingsSerializer.Meta.fields))})
        return Response(s.HostingBillingSettingsSerializer(row).data)
