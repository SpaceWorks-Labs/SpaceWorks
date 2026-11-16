"""Mentor Desk room choice for help alerts (G9). 404 while `events.mentor_chat_alerts` is off."""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.events.contributions.api_common import AdminView
from apps.events.contributions.serializers import ERRORS
from apps.makerspaces.platform import feature_enabled

from .chat_alerts import FEATURE, ROOM_CHANNELS, routes, set_routes


class AlertRoomSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()
    channel = serializers.ChoiceField(choices=ROOM_CHANNELS)
    is_active = serializers.BooleanField()


class MentorAlertRoutesSerializer(serializers.Serializer):
    rooms = AlertRoomSerializer(many=True, help_text="The space's chat rooms an organiser may choose.")
    destination_ids = serializers.ListField(child=serializers.IntegerField())


class MentorAlertRoutesWriteSerializer(serializers.Serializer):
    destination_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=10)


def _payload(event):
    from apps.integrations.models_destinations import NotificationDestination
    rooms = NotificationDestination.objects.filter(makerspace_id=event.makerspace_id,
                                                   channel__in=ROOM_CHANNELS).order_by("channel", "label", "pk")
    return {"rooms": [{"id": row.pk, "label": row.label, "channel": row.channel, "is_active": row.is_active}
                      for row in rooms],
            "destination_ids": [route.destination_id for route in routes(event)]}


class MentorAlertRoutesView(AdminView):
    permission = "manage_team"

    def alert_event(self, request, pk):
        event = self.event(request, pk)
        if not feature_enabled(event.makerspace, FEATURE):
            raise NotFound()
        return event

    @extend_schema(tags=["Admin events"], responses={200: MentorAlertRoutesSerializer, **ERRORS},
                   description="Rooms that receive new help requests while mentors are on shift. "
                               "Outbound text only: no buttons, no names.")
    def get(self, request, pk):
        return Response(_payload(self.alert_event(request, pk)))

    @extend_schema(tags=["Admin events"], request=MentorAlertRoutesWriteSerializer,
                   responses={200: MentorAlertRoutesSerializer, **ERRORS},
                   description="Replace the chosen rooms (audited as mentor.help_alert_routes_changed).")
    def put(self, request, pk):
        event = self.alert_event(request, pk)
        payload = MentorAlertRoutesWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        set_routes(event, request.user, payload.validated_data["destination_ids"])
        return Response(_payload(event))
