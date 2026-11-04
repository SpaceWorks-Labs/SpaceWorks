"""Staff refund queue: read cases, approve or decline them. Core ledger, always mounted."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.list_options import StaffListPagination
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.payments.models import RefundCase
from apps.payments.refund_case_access import get_visible_case, require_queue, visible_cases, with_case_rows
from apps.payments.serializers_refund_cases import (
    RefundCaseApproveSerializer,
    RefundCaseDeclineSerializer,
    RefundCaseFilterSerializer,
    RefundCaseListResponseSerializer,
    RefundCaseSerializer,
)
from apps.payments.services_refund_decisions import approve_case, decline_case
from apps.payments.subjects import resolve_subject_labels

ERRORS = {
    400: OpenApiResponse(ErrorSerializer, description="Invalid filter, amount, receipt or note."),
    401: OpenApiResponse(ErrorSerializer, description="Authentication required."),
    403: OpenApiResponse(ErrorSerializer, description="Subject authority (or record_payment for cash) required."),
    404: OpenApiResponse(ErrorSerializer, description="Makerspace or refund case not found in your scope."),
}
DECIDE_ERRORS = {**ERRORS, 409: OpenApiResponse(ErrorSerializer, description=(
    "refund_case_closed, refund_exceeds_balance (the case is voided when nothing is left), or "
    "refund_rail_unavailable (online charge with the payments rail removed: decline instead)."))}
SCOPE = (
    "Visible to view_finance (read-only) and to the staff whose action owns the charge's subject: "
    "manage_events, manage_bookings, manage_machines (role-scoped), manage_members/manage_makerspace "
    "for membership money, issue_request/return_request for loan charges."
)


def _render(case):
    labels = resolve_subject_labels([case.payment])
    return RefundCaseSerializer(case, context={"payment_subject_labels": labels}).data


class RefundCaseListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Payments"], operation_id="api_v1_admin_makerspace_refund_cases_list",
        summary="List refund cases awaiting or past a staff decision",
        description=f"{SCOPE} Newest first, paginated (24). A case records an entitlement; no money "
                    "moves until a staff member approves it.",
        parameters=[OpenApiParameter("page", OpenApiTypes.INT),
                    OpenApiParameter("status", OpenApiTypes.STR, enum=RefundCase.Status.values),
                    OpenApiParameter("area", OpenApiTypes.STR, enum=RefundCase.Area.values),
                    OpenApiParameter("kind", OpenApiTypes.STR, enum=RefundCase.Kind.values)],
        request=None, responses={200: RefundCaseListResponseSerializer, **ERRORS},
    )
    def get(self, request, makerspace_id):
        filters = RefundCaseFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        require_queue(request.user, makerspace_id)
        rows = with_case_rows(visible_cases(request.user, makerspace_id).filter(**filters.validated_data))
        pager = StaffListPagination()
        page = pager.paginate_queryset(rows.order_by("-created_at", "-pk"), request, view=self)
        labels = resolve_subject_labels([case.payment for case in page])
        return pager.get_paginated_response(
            RefundCaseSerializer(page, many=True, context={"payment_subject_labels": labels}).data)


class RefundCaseDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Read one refund case", description=SCOPE,
                   request=None, responses={200: RefundCaseSerializer, **ERRORS})
    def get(self, request, makerspace_id, case_id):
        require_queue(request.user, makerspace_id)
        return Response(_render(get_visible_case(request.user, makerspace_id, case_id)))


class RefundCaseApproveView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Payments"], summary="Approve a refund case and send the money back",
        description=(
            "Requires subject authority for the charge (view_finance alone is read-only). `amount` "
            "defaults to the due amount, re-clamped to the refundable balance. An online charge raises "
            "a provider refund after commit; if the provider refuses it the case becomes "
            "`approval_failed` (retry or decline). An offline charge requires record_payment and a "
            "`receipt` (method, reference, refunded_at) and is recorded as a manual refund. Audited."
        ),
        request=RefundCaseApproveSerializer, responses={200: RefundCaseSerializer, **DECIDE_ERRORS},
    )
    def post(self, request, makerspace_id, case_id):
        payload = RefundCaseApproveSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        require_queue(request.user, makerspace_id)
        case = get_visible_case(request.user, makerspace_id, case_id)
        approve_case(case, actor=request.user, **payload.validated_data)
        return Response(_render(get_visible_case(request.user, makerspace_id, case_id)))


class RefundCaseDeclineView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Payments"], summary="Decline a refund case",
        description="Requires subject authority for the charge. The note is shown to the member. "
                    "Nothing is refunded; the charge is unchanged. Audited.",
        request=RefundCaseDeclineSerializer, responses={200: RefundCaseSerializer, **DECIDE_ERRORS},
    )
    def post(self, request, makerspace_id, case_id):
        payload = RefundCaseDeclineSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        require_queue(request.user, makerspace_id)
        case = get_visible_case(request.user, makerspace_id, case_id)
        decline_case(case, actor=request.user, note=payload.validated_data["note"])
        return Response(_render(get_visible_case(request.user, makerspace_id, case_id)))
