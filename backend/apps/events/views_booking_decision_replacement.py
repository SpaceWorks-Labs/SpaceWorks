"""Session-only staff route: replace the rejected or cancelled reservation of a linked event."""

from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.hardware_requests.view_helpers import PUBLIC_ERROR_RESPONSES
from .booking_decision_replacement import replace_linked
from .views_booking_decision import MAX_SAFE, _maker


class ReplacementInput(serializers.Serializer):
    def to_internal_value(self, data):
        if not hasattr(data, "keys") or set(data.keys()) - set(self.fields):
            raise serializers.ValidationError(gettext("Unexpected fields."))
        return super().to_internal_value(data)

    expected_booking_id = serializers.IntegerField(
        min_value=1, max_value=MAX_SAFE, help_text="The current reservation shown by GET booking-link.")
    space_id = serializers.IntegerField(min_value=1, max_value=MAX_SAFE)
    member_id = serializers.IntegerField(min_value=1, max_value=MAX_SAFE,
                                         help_text="Chosen explicitly; never inferred from the event.")
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    note = serializers.CharField(max_length=5000, allow_blank=True, required=False)
    price_confirmation = serializers.RegexField(
        r"^[0-9a-f]{64}$", help_text="Digest from the staff booking price preview for this room, member and window.")


class ReplacementOutput(serializers.Serializer):
    booking_id = serializers.IntegerField(min_value=1, max_value=MAX_SAFE)
    replaces_booking_id = serializers.IntegerField(min_value=1, max_value=MAX_SAFE)
    status = serializers.ChoiceField(choices=["pending", "confirmed"])


class EventBookingReplacementView(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsActiveStaff]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if getattr(request, "api_client", None) or getattr(request, "person_credential", None):
            raise PermissionDenied(gettext("This endpoint requires a staff session."))

    @extend_schema(
        request=ReplacementInput, auth=[{"jwtAuth": []}],
        summary="Replace the rejected or cancelled reservation of a linked event",
        description="Creates a new booking through ordinary booking admission, availability, "
                    "pricing and approval. The event's retained link and every earlier booking, "
                    "with its debt and receipts, are kept. 409 codes: `stale_context`, "
                    "`replacement_not_allowed`, `price_changed`, booking conflicts.",
        responses={201: ReplacementOutput, **PUBLIC_ERROR_RESPONSES,
                   423: OpenApiResponse(ErrorSerializer, description="Tenant write fence is closed.")},
    )
    def post(self, request, makerspace_id, event_id):
        body = ReplacementInput(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        if data["ends_at"] <= data["starts_at"]:
            raise serializers.ValidationError({"ends_at": gettext("End time must be after start time.")})
        booking = replace_linked(
            request.user, _maker(makerspace_id), event_id,
            expected_booking_id=data["expected_booking_id"], space_id=data["space_id"],
            member_id=data["member_id"], starts_at=data["starts_at"], ends_at=data["ends_at"],
            price_confirmation=data["price_confirmation"], note=data.get("note", ""),
        )
        return Response({"booking_id": booking.pk, "replaces_booking_id": booking.replaces_id,
                         "status": booking.status}, status=201)
