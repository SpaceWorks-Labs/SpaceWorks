"""``GET member/makerspaces/<id>/allowances`` -- the caller's own allowances (#234 addendum 3(a))."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.guards import require_module
from apps.makerspaces.member_activity_serializers import MemberIncludedHoursSerializer
from apps.makerspaces.member_activity_service import active_membership
from apps.makerspaces.member_allowances import member_allowances
from apps.presence.guard import MemberPresenceRequired

LEVELS = ["ok", "warning", "limit"]


class AllowanceMeterSerializer(serializers.Serializer):
    used = serializers.IntegerField()
    limit = serializers.IntegerField(allow_null=True, help_text="Null means no cap.")
    remaining = serializers.IntegerField(allow_null=True)
    percent = serializers.FloatField(allow_null=True)
    level = serializers.ChoiceField(choices=LEVELS, help_text="`warning` from 80 %, `limit` at 100 %.")


class BorrowingAllowanceSerializer(serializers.Serializer):
    active_loans = AllowanceMeterSerializer()
    items_out = AllowanceMeterSerializer()


class DayPassAvailabilitySerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    name = serializers.CharField()
    available_today = serializers.BooleanField(help_text="False when today's cap is reached. Never a count.")


class MemberAllowancesSerializer(serializers.Serializer):
    makerspace_id = serializers.IntegerField()
    borrowing = BorrowingAllowanceSerializer(allow_null=True, help_text="Null while borrowing limits are off.")
    included_hours = MemberIncludedHoursSerializer(many=True)
    guest_passes = AllowanceMeterSerializer(
        allow_null=True, help_text="Guests you may bring right now (the per-sponsor limit). Null while guest passes are off.")
    day_passes = DayPassAvailabilitySerializer(many=True, allow_null=True, help_text="Null while day passes are off.")


class MemberAllowancesView(APIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    @extend_schema(
        tags=["Member activity"], summary="Read what you have left here",
        description="Your own borrowing limits, included hours, guests you can bring and day-pass availability. "
                    "Needs an active membership and the membership module; each section is empty while its "
                    "feature is off. Filtered to the authenticated user; no member id is accepted.",
        request=None, responses={
            200: MemberAllowancesSerializer,
            401: OpenApiResponse(description="Authentication required."),
            403: OpenApiResponse(ErrorSerializer, description="An active membership is required."),
            404: OpenApiResponse(ErrorSerializer, description="Makerspace not found, or the membership module is off."),
        },
    )
    def get(self, request, makerspace_id):
        membership = active_membership(request.user, makerspace_id)
        if membership is None:
            raise MemberPresenceRequired()
        require_module(membership.makerspace, "membership")
        return Response(MemberAllowancesSerializer(member_allowances(membership)).data)
