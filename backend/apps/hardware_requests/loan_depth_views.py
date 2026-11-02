"""Loan depth routes (L12): withdraw/cancel a request, the waitlist, and pickup timing."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests import waitlist, workflow
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.models_loans import LoanReservationPolicy, LoanWaitlistEntry
from apps.inventory.models import InventoryProduct
from apps.makerspaces.guards import require_feature, require_module
from apps.makerspaces.models import Makerspace

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409)}


class CancelRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")


class ClosedRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    closed_at = serializers.DateTimeField(allow_null=True)


class WaitlistEntrySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    position = serializers.SerializerMethodField()

    class Meta:
        model = LoanWaitlistEntry
        fields = ["id", "product", "product_name", "quantity", "status", "position", "offered_at",
                  "offer_expires_at", "created_at"]
        read_only_fields = fields

    def get_position(self, entry) -> int | None:
        return waitlist.position(entry) if entry.status == LoanWaitlistEntry.Status.WAITING else None


class StaffWaitlistEntrySerializer(WaitlistEntrySerializer):
    # Staff need to know who is waiting; the member's own view never carries this.
    member_name = serializers.SerializerMethodField()

    class Meta(WaitlistEntrySerializer.Meta):
        fields = [*WaitlistEntrySerializer.Meta.fields, "member_name"]
        read_only_fields = fields

    def get_member_name(self, entry) -> str:
        return entry.user.display_name or entry.user.username


class WaitlistJoinSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=99, default=1)


class ReservationPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanReservationPolicy
        fields = ["pickup_window_hours", "reservation_max_days_ahead", "waitlist_offer_hours"]


def _member_space(request, makerspace_id):
    space = get_object_or_404(rbac.scope_by_makerspace(request.user, Makerspace.objects.all(),
                                                       makerspace_field="pk"), pk=makerspace_id)
    require_module(space, "request_workflow")
    require_feature(space, "loans.enabled")
    return space


def _staff_space(request, makerspace_id, action=rbac.Action.ACCEPT_REQUEST):
    space = get_object_or_404(rbac.scope_by_action(request.user, action, Makerspace.objects.all(), field="pk"),
                              pk=makerspace_id)
    require_module(space, "request_workflow")
    return space


class MemberRequestWithdrawView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Loans"], summary="Withdraw my own request before it is handed over",
                   request=CancelRequestSerializer, responses={200: ClosedRequestSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        space = _member_space(request, makerspace_id)
        require_feature(space, "loans.withdrawals")
        payload = CancelRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = get_object_or_404(HardwareRequest.objects.filter(makerspace=space, requester=request.user), pk=pk)
        row = workflow.cancel_request(request.user, row, by_owner=True, reason=payload.validated_data["reason"])
        return Response(ClosedRequestSerializer(row).data)


class StaffRequestCancelView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Loans"], summary="Cancel a pending or accepted request (releases its reservation)",
                   request=CancelRequestSerializer, responses={200: ClosedRequestSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        space = _staff_space(request, makerspace_id)
        payload = CancelRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        rows = rbac.scope_by_action(request.user, rbac.Action.ACCEPT_REQUEST, HardwareRequest.objects.all())
        row = get_object_or_404(rows.filter(makerspace=space), pk=pk)
        row = workflow.cancel_request(request.user, row, by_owner=False, reason=payload.validated_data["reason"])
        return Response(ClosedRequestSerializer(row).data)


class MemberWaitlistView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Loans"], summary="My waitlist places", responses={200: WaitlistEntrySerializer(many=True),
                                                                            **ERRORS})
    def get(self, request, makerspace_id):
        space = _member_space(request, makerspace_id)
        require_feature(space, waitlist.FEATURE)
        rows = LoanWaitlistEntry.objects.filter(makerspace=space, user=request.user,
                                                status__in=LoanWaitlistEntry.ACTIVE).select_related("product")
        return Response(WaitlistEntrySerializer(rows, many=True).data)

    @extend_schema(tags=["Loans"], summary="Join the waitlist for an item that is out",
                   request=WaitlistJoinSerializer, responses={201: WaitlistEntrySerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = _member_space(request, makerspace_id)
        require_feature(space, waitlist.FEATURE)
        payload = WaitlistJoinSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        product = get_object_or_404(InventoryProduct.objects.filter(makerspace=space, is_public=True,
                                                                    is_archived=False),
                                    pk=payload.validated_data["product_id"])
        entry = waitlist.join(request.user, product, payload.validated_data["quantity"])
        return Response(WaitlistEntrySerializer(entry).data, status=201)


class MemberWaitlistLeaveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Loans"], summary="Leave a waitlist (an offer's held items go to the next in line)",
                   request=None, responses={200: WaitlistEntrySerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        space = _member_space(request, makerspace_id)
        entry = get_object_or_404(LoanWaitlistEntry.objects.filter(makerspace=space, user=request.user), pk=pk)
        return Response(WaitlistEntrySerializer(waitlist.leave(request.user, entry)).data)


class StaffWaitlistView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Loans"], summary="Who is waiting for which item, in order",
                   responses={200: StaffWaitlistEntrySerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = _staff_space(request, makerspace_id)
        require_feature(space, waitlist.FEATURE)
        rows = LoanWaitlistEntry.objects.filter(makerspace=space, status__in=LoanWaitlistEntry.ACTIVE)
        if product := request.query_params.get("product"):
            rows = rows.filter(product_id=int(product) if str(product).isdigit() else 0)
        return Response(StaffWaitlistEntrySerializer(rows.select_related("product", "user")[:500], many=True).data)


class LoanReservationPolicyView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Loans"], summary="Pickup and waitlist timing",
                   responses={200: ReservationPolicySerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space = _staff_space(request, makerspace_id, rbac.Action.EDIT_INVENTORY)
        return Response(ReservationPolicySerializer(LoanReservationPolicy.for_makerspace(space)).data)

    @extend_schema(tags=["Loans"], summary="Set pickup and waitlist timing (settings authority)",
                   request=ReservationPolicySerializer, responses={200: ReservationPolicySerializer, **ERRORS})
    @transaction.atomic
    def put(self, request, makerspace_id):
        from apps.makerspaces.settings_authority import assert_setting_write, record_change
        space = _staff_space(request, makerspace_id, rbac.Action.EDIT_INVENTORY)
        policy = LoanReservationPolicy.for_makerspace(space)
        before = ReservationPolicySerializer(policy).data
        payload = ReservationPolicySerializer(policy, data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        changed = [key for key, value in payload.validated_data.items() if getattr(policy, key) != value]
        decisions = {key: assert_setting_write(request.user, space, "inventory", key) for key in changed}
        policy = payload.save(makerspace=space)
        after = ReservationPolicySerializer(policy).data
        for key, decision in decisions.items():
            record_change(request.user, space, "inventory", key, before.get(key), after.get(key), decision)
        return Response(after)
