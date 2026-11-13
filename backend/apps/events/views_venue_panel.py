"""Read-only venue panel for everyone who is told about the venue (decision 223 G6).

Co-organizers, per-event delegates and organizer-organization managers receive linked-booking
notices (`linked_booking_notices`) but hold no MANAGE_BOOKINGS, so they could not open the
manage panel. This GET needs only `publish_schedule` on the event (the audience the notices
already use, re-checked by `event_authority`) and shows the venue state without the booker's
identity, price or any write action.
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.hardware_requests.view_helpers import PUBLIC_ERROR_RESPONSES
from apps.makerspaces.guards import require_module

from . import event_authority
from .event_permissions import PUBLISH_SCHEDULE
from .venue_offers import VenueOfferSerializer, venue_offers
from .venue_publish_check import publish_check
from .venue_state import bookings_apply


class VenueWindow(serializers.Serializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()


class VenueStateSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=["none", "confirmed", "pending", "blocked"])
    reason = serializers.CharField(allow_blank=True)
    booking_id = serializers.IntegerField(allow_null=True)
    booking_status = serializers.CharField(required=False)
    space_id = serializers.IntegerField(required=False)
    space_name = serializers.CharField(required=False)
    coverage = serializers.ChoiceField(choices=["covers", "not_covered"], required=False)
    is_house = serializers.BooleanField(required=False)


class WarningSerializer(serializers.Serializer):
    code = serializers.CharField()
    event_capacity = serializers.IntegerField(required=False)
    room_capacity = serializers.IntegerField(required=False)


class VenuePanelSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    event_status = serializers.CharField()
    event_window = VenueWindow()
    venue = VenueStateSerializer()
    warnings = WarningSerializer(many=True)
    requires_override = serializers.BooleanField(help_text="Publishing needs `publish_without_room: true`.")
    can_publish = serializers.BooleanField()
    venue_fee = serializers.JSONField(allow_null=True)
    offers = VenueOfferSerializer(many=True)
    can_manage_booking = serializers.BooleanField(
        help_text="Whether this viewer may use the manage panel (`booking-link`); false means read-only.")


class EventVenuePanelView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], summary="Read-only venue panel for an event", request=None,
                   responses={200: VenuePanelSerializer, **PUBLIC_ERROR_RESPONSES,
                              404: OpenApiResponse(ErrorSerializer, description="Unknown or invisible event.")})
    def get(self, request, makerspace_id, event_id):
        event = event_authority.get_event(request.user, event_id, PUBLISH_SCHEDULE)
        if event.makerspace_id != makerspace_id:
            raise NotFound()
        require_module(event.makerspace, "events")
        check = publish_check(event)
        from .booking_decision_access import authorized_event
        try:
            can_manage = bookings_apply(event) and bool(authorized_event(request.user, event.makerspace, event.pk))
        except NotFound:
            can_manage = False
        return Response({
            "event_id": event.pk, "event_status": event.status,
            "event_window": {"starts_at": event.starts_at, "ends_at": event.ends_at},
            "venue": check["venue"], "warnings": check["warnings"],
            "requires_override": check["requires_override"], "can_publish": check["can_publish"],
            "venue_fee": check["venue_fee"], "offers": venue_offers(request.user, event),
            "can_manage_booking": can_manage,
        })
