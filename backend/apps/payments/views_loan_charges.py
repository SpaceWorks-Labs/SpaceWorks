"""A loan's charges, its fee waivers, and damage/lost charges (lane L15, A5/A14).

Authority is `return_request` in the loan's space (the loan-charge subject action);
finance staff and issuers may read. Waivers need `loans.fee_waivers`; damage/lost
charges need `charges.pricing`. Waiving never reverses a paid charge: it opens a staff-
approved refund case instead.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.makerspaces.platform import feature_enabled
from apps.openapi_errors import errors
from apps.payments.models_pricing_rules import LoanFeeWaiver
from apps.payments.pricing.errors import PricingDisabled
from apps.payments.pricing.loan_charges_payload import charge_row, loan_charges_payload
from apps.payments.pricing.serializers_rules import (
    LoanAccountabilityChargeResultSerializer, LoanAccountabilityChargeSerializer, LoanChargesSerializer, LoanFeeWaiverCreateSerializer,
    LoanFeeWaiverResultSerializer, LoanFeeWaiverRevokeSerializer, LoanFeeWaiverSerializer,
)

TAGS = ["Pricing"]
READ_ACTIONS = (rbac.Action.RETURN_REQUEST, rbac.Action.ISSUE_REQUEST, rbac.Action.VIEW_FINANCE)


def _request(actor, makerspace_id, request_id, *actions):
    from apps.hardware_requests.models import HardwareRequest

    scope = rbac.makerspaces_for_actions(actor, *(actions or READ_ACTIONS))
    rows = HardwareRequest.objects.select_related("makerspace").filter(makerspace_id=makerspace_id)
    if scope is not rbac.ALL:
        rows = rows.filter(makerspace_id__in=scope)
    return get_object_or_404(rows, pk=request_id)


def _waivers_on(loan):
    if not feature_enabled(loan.makerspace, "loans.fee_waivers"):
        raise PricingDisabled("Loan fee waivers are switched off for this space.")


class LoanChargesView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="A loan's charges, fee waivers and damage/lost rows",
                   description="return_request, issue_request or view_finance in the loan's space. Each "
                               "damage/lost row carries the suggested charge and whether its return photo exists.",
                   responses={200: LoanChargesSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id, request_id):
        loan = _request(request.user, makerspace_id, request_id)
        return Response(LoanChargesSerializer(loan_charges_payload(loan, request.user),
                                              context={"request": request}).data)


class LoanFeeWaiverView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="List a loan's fee waivers (and revocations)",
                   responses={200: LoanFeeWaiverSerializer(many=True), **errors(401, 403, 404)})
    def get(self, request, makerspace_id, request_id):
        loan = _request(request.user, makerspace_id, request_id)
        _waivers_on(loan)
        rows = LoanFeeWaiver.objects.filter(request=loan).select_related("created_by")
        return Response(LoanFeeWaiverSerializer(rows, many=True, context={"request": request}).data)

    @extend_schema(tags=TAGS, summary="Waive a loan's fees (all, or the named ones), with a reason",
                   description="return_request. Pending charges become waived; a charge already paid opens a "
                               "refund case for staff approval (no money moves). The deposit is never waived. "
                               "Charges raised later resolve to 0. 400 `waiver_reason_required`; 409 "
                               "`waiver_exists` when a named fee is already waived.",
                   request=LoanFeeWaiverCreateSerializer,
                   responses={201: LoanFeeWaiverResultSerializer, **errors(400, 401, 403, 404, 409, 423)})
    def post(self, request, makerspace_id, request_id):
        from apps.payments.pricing.waivers import waive_loan

        loan = _request(request.user, makerspace_id, request_id, rbac.Action.RETURN_REQUEST)
        _waivers_on(loan)
        body = LoanFeeWaiverCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        result = waive_loan(loan, request.user, components=body.validated_data.get("components") or (),
                            reason=body.validated_data["reason"])
        return Response(LoanFeeWaiverResultSerializer(result, context={"request": request}).data, status=201)


class LoanFeeWaiverRevokeView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Revoke a loan fee waiver, with a reason",
                   description="return_request. Affects only charges not yet raised; nothing already waived "
                               "or refunded is reopened. Written as a new append-only row.",
                   request=LoanFeeWaiverRevokeSerializer,
                   responses={201: LoanFeeWaiverSerializer, **errors(400, 401, 403, 404, 409, 423)})
    def post(self, request, makerspace_id, request_id, waiver_id):
        from apps.payments.pricing.waivers import revoke_waiver

        loan = _request(request.user, makerspace_id, request_id, rbac.Action.RETURN_REQUEST)
        _waivers_on(loan)
        waiver = get_object_or_404(LoanFeeWaiver, pk=waiver_id, request=loan, revokes__isnull=True)
        body = LoanFeeWaiverRevokeSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        revocation = revoke_waiver(waiver, request.user, reason=body.validated_data["reason"])
        return Response(LoanFeeWaiverSerializer(revocation, context={"request": request}).data, status=201)


class AccountabilityChargeView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Charge for a damaged or lost item (staff-set amount)",
                   description="return_request (handover roles included). One charge per damage/lost row; a "
                               "second is 409 `charge_exists`. An amount above 0 needs the return photo that "
                               "recorded the item (409 `return_photo_required`). 0 means no charge. A waived "
                               "loan raises nothing.",
                   request=LoanAccountabilityChargeSerializer,
                   responses={200: LoanAccountabilityChargeResultSerializer, **errors(400, 401, 403, 404, 409, 423)})
    def post(self, request, makerspace_id, request_id, accountability_id):
        from apps.hardware_requests.loan_payments import charge_accountability
        from apps.hardware_requests.models import RequesterAccountability

        loan = _request(request.user, makerspace_id, request_id, rbac.Action.RETURN_REQUEST)
        if not feature_enabled(loan.makerspace, "charges.pricing"):
            raise PricingDisabled()
        row = get_object_or_404(RequesterAccountability.objects.select_related("request_item__product", "makerspace"),
                                pk=accountability_id, request=loan)
        body = LoanAccountabilityChargeSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        payment = charge_accountability(row, request.user, amount=body.validated_data["amount"],
                                        note=body.validated_data.get("note", ""))
        reason = None if payment is not None else ("no_charge" if body.validated_data["amount"] <= 0 else "waived")
        return Response(LoanAccountabilityChargeResultSerializer(
            {"charge": charge_row(payment) if payment else None, "free_reason": reason}).data)
