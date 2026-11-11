"""Member "I've paid" claims, the staff claim queue and maker-checker confirmations (L5).

Claims answer 404 while `billing.offline_claims` is off. The confirmation queue is not
switch-gated: it only ever holds rows proposed while `billing.maker_checker` was on, and
those must still be decidable after the switch is turned off (data kept, #95).
"""

from django.utils.translation import gettext
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.list_options import StaffListPagination
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.payments import maker_checker, offline_claims
from apps.payments.member_scope import member_payment_queryset
from apps.payments.models import PaymentClaim, SettlementConfirmation
from apps.payments.serializers_l5 import (
    ClaimPageSerializer, ClaimSubmitSerializer, ConfirmationPageSerializer, ConfirmationSerializer,
    DecisionNoteSerializer, OwnClaimSerializer, StaffClaimSerializer,
)
from apps.payments.throttles_l5 import PaymentClaimThrottle

ERRORS = {401: OpenApiResponse(ErrorSerializer), 403: OpenApiResponse(ErrorSerializer),
          404: OpenApiResponse(ErrorSerializer)}
CONFLICT = OpenApiResponse(ErrorSerializer, description="`claim_exists`, `claim_decided`, `payment_terminal`, "
                                                        "`self_confirmation` or `settlement_decided`.")


def finance_space(request, makerspace_id, action=rbac.Action.RECORD_PAYMENT, feature=None):
    from apps.payments.l5_gates import action_space

    return action_space(request, makerspace_id, action, feature)


class MemberPaidClaimView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PaymentClaimThrottle]

    @extend_schema(tags=["Payments"], summary="Tell the space you paid a pending charge offline",
                   description="The caller's own pending charge. One open claim per charge and one claim per "
                               "reference per space. Rate-limited. Staff confirm or reject; nothing is settled here.",
                   request=ClaimSubmitSerializer,
                   responses={201: OwnClaimSerializer, 409: CONFLICT, 429: OpenApiResponse(ErrorSerializer), **ERRORS})
    def post(self, request, makerspace_id, payment_id):
        payment = member_payment_queryset(request.user, makerspace_id).filter(pk=payment_id).first()
        if payment is None:
            return Response({"detail": gettext("Not found.")}, status=404)
        from apps.payments.l5_gates import require_capability
        require_capability(payment.makerspace, "billing.offline_claims")
        payload = ClaimSubmitSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        claim = offline_claims.submit_claim(payment, claimant=request.user, **payload.validated_data)
        return Response(OwnClaimSerializer(claim).data, status=201)


class StaffClaimListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="List payers' offline payment claims",
                   description="Requires record_payment. Newest first; filter by status.",
                   parameters=[OpenApiParameter("status", OpenApiTypes.STR, enum=PaymentClaim.Status.values)],
                   responses={200: ClaimPageSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        finance_space(request, makerspace_id, feature="billing.offline_claims")
        rows = rbac.scope_by_action(request.user, rbac.Action.RECORD_PAYMENT, PaymentClaim.objects.all()).filter(
            makerspace_id=makerspace_id).select_related("payment")
        if request.query_params.get("status") in PaymentClaim.Status.values:
            rows = rows.filter(status=request.query_params["status"])
        pager = StaffListPagination()
        page = pager.paginate_queryset(rows, request, view=self)
        return pager.get_paginated_response(StaffClaimSerializer(page, many=True).data)


class StaffClaimConfirmView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Confirm a claim: record the offline settlement",
                   description="Requires record_payment. Writes the ManualSettlement receipt (method, the claimed "
                               "reference and date) in the same transaction that marks the charge paid -- or, with "
                               "maker-checker on, proposes it for a second person.",
                   request=None, responses={200: StaffClaimSerializer, 409: CONFLICT, **ERRORS})
    def post(self, request, makerspace_id, claim_id):
        finance_space(request, makerspace_id, feature="billing.offline_claims")
        claim = offline_claims.confirm_claim(actor=request.user, makerspace_id=makerspace_id, claim_id=claim_id)
        return Response(StaffClaimSerializer(claim).data)


class StaffClaimRejectView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Reject a claim (the charge stays pending)",
                   request=DecisionNoteSerializer, responses={200: StaffClaimSerializer, 409: CONFLICT, **ERRORS})
    def post(self, request, makerspace_id, claim_id):
        finance_space(request, makerspace_id, feature="billing.offline_claims")
        payload = DecisionNoteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        claim = offline_claims.reject_claim(actor=request.user, makerspace_id=makerspace_id, claim_id=claim_id,
                                            note=payload.validated_data["note"])
        return Response(StaffClaimSerializer(claim).data)


class SettlementConfirmationListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="List offline settlements awaiting a second confirmation",
                   parameters=[OpenApiParameter("status", OpenApiTypes.STR,
                                                enum=SettlementConfirmation.Status.values)],
                   responses={200: ConfirmationPageSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        finance_space(request, makerspace_id)
        rows = rbac.scope_by_action(request.user, rbac.Action.RECORD_PAYMENT, SettlementConfirmation.objects.all(),
                                    field="payment__makerspace_id").filter(
            payment__makerspace_id=makerspace_id).select_related("payment")
        from apps.payments.unit_payer_scope import payer_user_ids

        payers = payer_user_ids(request.user, makerspace_id, rbac.Action.RECORD_PAYMENT)
        if payers is not None:  # parity O-B3 (rule 261): a unit-scoped checker sees only their members' proposals
            rows = rows.filter(payment__member_id__in=payers)
        status = request.query_params.get("status") or SettlementConfirmation.Status.AWAITING
        rows = rows.filter(status=status) if status in SettlementConfirmation.Status.values else rows
        pager = StaffListPagination()
        page = pager.paginate_queryset(rows, request, view=self)
        return pager.get_paginated_response(ConfirmationSerializer(page, many=True, context={"request": request}).data)


class SettlementConfirmView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Confirm an offline settlement someone else recorded",
                   description="Requires record_payment. 409 `self_confirmation` for the person who recorded it.",
                   request=None, responses={200: ConfirmationSerializer, 409: CONFLICT, **ERRORS})
    def post(self, request, makerspace_id, confirmation_id):
        finance_space(request, makerspace_id)
        row = maker_checker.confirm(actor=request.user, makerspace_id=makerspace_id, confirmation_id=confirmation_id)
        return Response(ConfirmationSerializer(row, context={"request": request}).data)


class SettlementRejectView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Payments"], summary="Reject an offline settlement awaiting confirmation",
                   request=DecisionNoteSerializer, responses={200: ConfirmationSerializer, 409: CONFLICT, **ERRORS})
    def post(self, request, makerspace_id, confirmation_id):
        finance_space(request, makerspace_id)
        payload = DecisionNoteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = maker_checker.reject(actor=request.user, makerspace_id=makerspace_id, confirmation_id=confirmation_id,
                                   note=payload.validated_data["note"])
        return Response(ConfirmationSerializer(row, context={"request": request}).data)

