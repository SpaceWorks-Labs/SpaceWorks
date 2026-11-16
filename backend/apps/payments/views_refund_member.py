"""The payer's side of a refund: ask for one, or take the request back. Core ledger."""

from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.hardware_requests.exceptions import ErrorSerializer
from apps.payments.member_access import member_may_see_own_charges
from apps.payments.member_scope import member_payment_queryset
from apps.payments.models import RefundCase
from apps.payments.serializers_refund_cases import MemberRefundCaseSerializer, MemberRefundRequestSerializer
from apps.payments.services_refund_cases import request_refund, withdraw_request

ERRORS = {
    400: OpenApiResponse(ErrorSerializer, description="Missing reason, unpaid charge, deposit, or nothing left."),
    401: OpenApiResponse(ErrorSerializer, description="Authentication required."),
    403: OpenApiResponse(ErrorSerializer, description="No active membership and no charge here."),
    404: OpenApiResponse(ErrorSerializer, description="Not one of your charges here."),
}


def _require_member(user, makerspace_id):
    if not member_may_see_own_charges(user, makerspace_id):
        raise PermissionDenied(gettext("An active membership or an existing charge is required."))


class MemberRefundRequestView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Payments"], summary="Ask for a refund on one of your paid charges",
        description=(
            "Same access as your payment history. Opens a refund case for staff to decide; no money moves "
            "until staff approve it. If the space already owes you something on this charge under its "
            "cancellation policy, your reason is added to that case. Loan deposits are released by staff "
            "when the loan closes and cannot be requested here."
        ),
        request=MemberRefundRequestSerializer,
        responses={201: MemberRefundCaseSerializer, **ERRORS,
                   409: OpenApiResponse(ErrorSerializer, description="refund_request_exists.")},
    )
    def post(self, request, makerspace_id, payment_id):
        payload = MemberRefundRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        _require_member(request.user, makerspace_id)
        payment = member_payment_queryset(request.user, makerspace_id).filter(pk=payment_id).first()
        if payment is None:
            raise NotFound(gettext("Payment not found."))
        case = request_refund(payment, member=request.user, reason=payload.validated_data["reason"])
        return Response(MemberRefundCaseSerializer(case).data, status=201)


class MemberRefundWithdrawView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Payments"], summary="Withdraw your own open refund request",
        description="Only an open request you made can be withdrawn; a refund the space owes under its "
                    "policy cannot. Audited.",
        request=None,
        responses={200: MemberRefundCaseSerializer, **ERRORS,
                   409: OpenApiResponse(ErrorSerializer, description="refund_case_not_withdrawable.")},
    )
    def post(self, request, makerspace_id, case_id):
        _require_member(request.user, makerspace_id)
        payments = member_payment_queryset(request.user, makerspace_id)
        case = RefundCase.objects.filter(pk=case_id, payment__in=payments.values("pk")).first()
        if case is None:
            raise NotFound(gettext("Refund request not found."))
        return Response(MemberRefundCaseSerializer(withdraw_request(case, member=request.user)).data)
