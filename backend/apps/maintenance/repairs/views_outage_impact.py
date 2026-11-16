"""Before a room goes out of service: which bookings and events the outage would meet (read-only).

Nothing is written or sent. The window is the one `service_state` would open now (from now until
`expected_back_at`, open-ended without it) and the bookings are the same `affected_bookings` the
outage would list. Who may ask is who may take the room out of service (`service_state._gate`).

* the booking count is shown to every such caller (the staff summary notice is count-only too);
* booking detail only to staff holding `manage_bookings`, as `ServiceStateView` lists them;
* events through Bookings' one seam, `bookings.event_labels`: a title only for a viewer who may
  see that event, otherwise only counted. Empty while Events is off or tombstoned.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff

from . import areas, service_state
from .room_outages import affected_bookings, open_outage
from .views_common import ERRORS, space_for
from .views_staff import AffectedBookingSerializer

TAGS = ["Repairs maintenance"]
MAX_ROWS = 200


class OutageImpactQuery(serializers.Serializer):
    room_id = serializers.IntegerField(min_value=1)
    expected_back_at = serializers.DateTimeField(required=False, allow_null=True, default=None)


class AffectedEventSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    title = serializers.CharField()
    event_status = serializers.CharField()


class OutageImpactSerializer(serializers.Serializer):
    already_out_of_service = serializers.BooleanField()
    booking_count = serializers.IntegerField(help_text="Pending or confirmed bookings inside the window.")
    bookings = AffectedBookingSerializer(many=True, help_text="Only for staff holding manage_bookings.")
    events = AffectedEventSerializer(many=True, help_text="Linked events you may see, by title.")
    other_event_bookings = serializers.IntegerField(
        help_text="Bookings holding the room for an event you may not see; nothing else about them is shown.")


class RoomOutageImpactView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Preview the bookings and events a room outage would meet",
                   parameters=[OpenApiParameter("room_id", int, required=True),
                               OpenApiParameter("expected_back_at", str, required=False,
                                                description="ISO 8601; open-ended when omitted.")],
                   responses={200: OutageImpactSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        query = OutageImpactQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        room = get_object_or_404(areas.subject_model("bookable_space").objects.filter(makerspace=space),
                                 pk=query.validated_data["room_id"])
        service_state._gate(request.user, space, "bookable_space", room)
        from apps.maintenance.models import RoomOutage
        probe = RoomOutage(makerspace=space, room=room, started_at=timezone.now(),
                           expected_back_at=query.validated_data["expected_back_at"])
        rows = list(affected_bookings(probe)[:MAX_ROWS])
        from apps.bookings.event_labels import event_labels
        labels = event_labels(request.user, space, [row.pk for row in rows])
        events, hidden = {}, 0
        for label in labels.values():
            if label["kind"] == "event":
                events.setdefault(label["event_id"], {key: label[key] for key in ("event_id", "title", "event_status")})
            else:
                hidden += 1
        detail = rbac.can(request.user, rbac.Action.MANAGE_BOOKINGS, space.pk)
        return Response(OutageImpactSerializer({
            "already_out_of_service": open_outage(room) is not None, "booking_count": len(rows),
            "bookings": [{"id": row.pk, "starts_at": row.starts_at, "ends_at": row.ends_at, "status": row.status}
                         for row in rows] if detail else [],
            "events": list(events.values()), "other_event_bookings": hidden,
        }).data)
