"""Staff views of held captures and disputes. Record-and-decide only (lane L5).

Disputes are always recorded; their screens answer 404 while `billing.disputes` is off.
Held captures stay decidable whatever `billing.capture_flags` says now, because a held
receipt must always be releasable.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.list_options import StaffListPagination
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.payments.capture_flags import resolve_flag
from apps.payments.models import PaymentCaptureFlag, PaymentDispute
from apps.payments.serializers_l5 import (
    CaptureFlagPageSerializer, CaptureFlagSerializer, DisputeDetailSerializer, DisputePageSerializer,
    FlagResolveSerializer,
)
from apps.payments.views_offline import finance_space

ERRORS = {401: OpenApiResponse(ErrorSerializer), 403: OpenApiResponse(ErrorSerializer),
          404: OpenApiResponse(ErrorSerializer)}


class CaptureFlagListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="List late, duplicate and mismatched online captures",
                   description="Requires view_finance. `open=true` (default) lists only flags awaiting a decision.",
                   parameters=[OpenApiParameter("open", OpenApiTypes.BOOL)],
                   responses={200: CaptureFlagPageSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        finance_space(request, makerspace_id, rbac.Action.VIEW_FINANCE)
        rows = rbac.scope_by_action(request.user, rbac.Action.VIEW_FINANCE, PaymentCaptureFlag.objects.all()).filter(
            makerspace_id=makerspace_id).select_related("payment")
        if request.query_params.get("open", "true").lower() != "false":
            rows = rows.filter(resolution="")
        pager = StaffListPagination()
        return pager.get_paginated_response(CaptureFlagSerializer(pager.paginate_queryset(rows, request, view=self),
                                                                  many=True).data)


class CaptureFlagResolveView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Decide a held capture",
                   description="`issue_received` issues the held receipt on the amount actually received "
                               "(record_payment); `refund_case` opens a refund case a staff member must still "
                               "approve (subject authority) -- nothing is refunded here; `acknowledged` closes it "
                               "with a required note. 409 `document_held` when the capture cannot be receipted.",
                   request=FlagResolveSerializer,
                   responses={200: CaptureFlagSerializer, 409: OpenApiResponse(ErrorSerializer), **ERRORS})
    def post(self, request, makerspace_id, flag_id):
        finance_space(request, makerspace_id, rbac.Action.VIEW_FINANCE)
        payload = FlagResolveSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        flag = resolve_flag(actor=request.user, makerspace_id=makerspace_id, flag_id=flag_id,
                            **payload.validated_data)
        return Response(CaptureFlagSerializer(flag).data)


class DisputeListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="List payment disputes (chargebacks)",
                   description="Requires view_finance. A record only: disputes never cancel or refund anything.",
                   parameters=[OpenApiParameter("status", OpenApiTypes.STR, enum=PaymentDispute.Status.values)],
                   responses={200: DisputePageSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        finance_space(request, makerspace_id, rbac.Action.VIEW_FINANCE, "billing.disputes")
        rows = rbac.scope_by_action(request.user, rbac.Action.VIEW_FINANCE, PaymentDispute.objects.all()).filter(
            makerspace_id=makerspace_id).select_related("payment")
        if request.query_params.get("status") in PaymentDispute.Status.values:
            rows = rows.filter(status=request.query_params["status"])
        pager = StaffListPagination()
        from apps.payments.serializers_l5 import DisputeSerializer
        return pager.get_paginated_response(DisputeSerializer(pager.paginate_queryset(rows, request, view=self),
                                                              many=True).data)


class DisputeDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Read one dispute with its status history",
                   responses={200: DisputeDetailSerializer, **ERRORS})
    def get(self, request, makerspace_id, dispute_id):
        finance_space(request, makerspace_id, rbac.Action.VIEW_FINANCE, "billing.disputes")
        disputes = rbac.scope_by_action(request.user, rbac.Action.VIEW_FINANCE, PaymentDispute.objects.all())
        dispute = get_object_or_404(disputes.select_related("payment").prefetch_related("events"),
                                    makerspace_id=makerspace_id, pk=dispute_id)
        return Response(DisputeDetailSerializer(dispute).data)
