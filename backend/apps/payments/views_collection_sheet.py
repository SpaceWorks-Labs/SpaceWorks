"""Collection sheet and cash hand-over routes (parity O-B3). Both answer 404 while `billing.collection_sheet`
is off and across tenants; both need `record_payment` in the space. Every row of a sheet goes through the
ordinary offline-settlement service, so the two-person confirmation stays in force (see `collection_sheet`)."""

from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.models import User
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.payments import cash_handover, collection_sheet
from apps.payments.l5_gates import action_space
from apps.payments.serializers_collection_sheet import (
    CashHandoverResultSerializer, CashHandoverSerializer, CollectionSheetResponseSerializer,
    CollectionSheetSerializer,
)

ERRORS = {code: OpenApiResponse(ErrorSerializer) for code in (400, 401, 403, 404, 409)}
FEATURE = "billing.collection_sheet"


class CollectionSheetView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Payments"], summary="Record up to 200 offline payments from one collection sheet",
        description=(
            "Requires record_payment and `billing.collection_sheet`. Each row settles one pending charge as an "
            "ordinary offline settlement (method, reference, received_at; the receipt document is issued as "
            "usual). With maker-checker on a row is filed for a second person (`awaiting_confirmation`); the "
            "sheet never confirms anything. Rows are independent: a failed row carries a typed `code` and the "
            "rest still land; a unit-scoped actor's out-of-scope charge fails its row with `not_found`. Refused up front with 409 `collection_sheet_rows_monthly_quota_reached` when the "
            "space's monthly sheet allowance would be passed."),
        request=CollectionSheetSerializer, responses={200: CollectionSheetResponseSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = action_space(request, makerspace_id, rbac.Action.RECORD_PAYMENT, FEATURE)
        payload = CollectionSheetSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return Response(collection_sheet.record_sheet(
            actor=request.user, space=space, rows=payload.validated_data["rows"]))


class CashHandoverView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Payments"], summary="Record cash a collector handed over",
        description=("Requires record_payment and `billing.collection_sheet`. Lowers that collector's `cash-in-hand` "
                     "report figure; it is a transfer and never counts as spending. A unit-scoped actor may record only "
                     "their own hand-over (404 for another collector)."),
        request=CashHandoverSerializer, responses={201: CashHandoverResultSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = action_space(request, makerspace_id, rbac.Action.RECORD_PAYMENT, FEATURE)
        payload = CashHandoverSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        collector = get_object_or_404(User, pk=data["collector_id"], is_active=True)
        from apps.makerspaces.member_unit_scope import unit_paths_for

        if collector.pk != request.user.pk and unit_paths_for(
                request.user, space.pk, rbac.Action.RECORD_PAYMENT) is not None:
            raise Http404()  # parity O-B3: a unit-scoped collector records only their own hand-overs
        entry = cash_handover.record_cash_handover(
            actor=request.user, space=space, collector=collector, amount=data["amount"],
            currency=data["currency"], entry_date=data.get("entry_date"), note=data["note"])
        return Response({"entry_id": entry.pk, "collector_id": collector.pk, "amount": entry.amount,
                         "currency": entry.currency}, status=201)
