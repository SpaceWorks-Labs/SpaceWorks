"""Create a draft event and request or link its room in one call (decision 223 G6)."""

from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer

from . import services
from .serializers_admin import EventAdminSerializer, EventCreateSerializer
from .venue_step import MODES, run_room_step
from .views_admin_event_detail import EVENT_ERROR_400, _visible_makerspace

MAX_SAFE = 9007199254740991
_ID = {"min_value": 1, "max_value": MAX_SAFE}


class RoomStepSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=MODES, help_text=(
        "`request`: book the room for yourself (pending when the room needs approval); `book`: staff book for "
        "`member_id`; `house`: staff-only house booking (no member, no charge, no plan hours); `link`: link "
        "the existing `booking_id` (needs events and bookings roles; it must cover the event)."))
    space_id = serializers.IntegerField(required=False, **_ID)
    member_id = serializers.IntegerField(required=False, **_ID)
    booking_id = serializers.IntegerField(required=False, **_ID)
    price_confirmation = serializers.RegexField(r"^[0-9a-f]{64}$", required=False)
    note = serializers.CharField(max_length=5000, allow_blank=True, required=False)

    def validate(self, attrs):
        mode, errors = attrs["mode"], {}
        if mode == "link":
            needed = ("booking_id",)
        else:
            needed = ("space_id", "member_id") if mode == "book" else ("space_id",)
        for name in needed:
            if name not in attrs:
                errors[name] = gettext("This field is required for this mode.")
        if mode != "book" and "member_id" in attrs:
            errors["member_id"] = gettext("Only the book mode takes a member.")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class EventWithRoomInput(serializers.Serializer):
    event = EventCreateSerializer()
    room = RoomStepSerializer()


class RoomResultSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=MODES)
    status = serializers.ChoiceField(choices=["linked", "failed"])
    booking_id = serializers.IntegerField(allow_null=True)
    booking_status = serializers.CharField(allow_null=True)
    code = serializers.CharField(required=False)
    detail = serializers.CharField(required=False)
    orphan_booking_id = serializers.IntegerField(required=False, allow_null=True)


class EventWithRoomOutput(serializers.Serializer):
    event = EventAdminSerializer()
    room = RoomResultSerializer()


class EventWithRoomView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin events"], summary="Create a draft event with its room step", request=EventWithRoomInput,
        description=("Creates the draft, then requests, books, house-books or links the room (decision 223 G6). "
                     "A failed room step keeps the draft and reports `room.status = failed` with a code so the "
                     "organizer can retry from the venue panel; nothing is published or charged."),
        responses={201: EventWithRoomOutput, 400: EVENT_ERROR_400, **{code: ErrorSerializer for code in (401, 403, 404)}},
    )
    def post(self, request, makerspace_id):
        makerspace = _visible_makerspace(request.user, makerspace_id)
        body = EventWithRoomInput(data=request.data)
        body.is_valid(raise_exception=True)
        values = dict(body.validated_data["event"])
        values.pop("inherit_fields", None)
        if values.pop("host_makerspace_id", makerspace.pk) != makerspace.pk:
            raise serializers.ValidationError({"event": {"host_makerspace_id": gettext(
                "The room step books a room in this space; leave the host as this space.")}})
        event = services.create_event(makerspace=makerspace, actor=request.user, **values)
        room = run_room_step(request.user, makerspace, event, body.validated_data["room"])
        return Response({"event": EventAdminSerializer(event, context={"request": request}).data, "room": room},
                        status=status.HTTP_201_CREATED)
