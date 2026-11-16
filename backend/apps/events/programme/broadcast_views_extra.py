"""Send-with-undo, delivery tallies and starter templates for the broadcast composer."""

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.events import event_authority
from apps.events.broadcasts import authorize
from apps.events.event_permissions import MANAGE_REGISTRATIONS
from apps.events.models_broadcasts import EventBroadcast
from apps.events.serializers_broadcasts import (
    BroadcastSendSerializer, BroadcastTalliesSerializer, BroadcastTemplateSerializer, EventBroadcastSerializer,
)
from apps.events.views_invites import ERRORS
from apps.integrations.broadcasts_templates import EVENT_STARTER_TEMPLATES
from apps.makerspaces.platform import feature_enabled

from .broadcast_schedule import send_now
from .broadcast_tallies import tallies
from .broadcast_views import get_campaign


class BroadcastSendView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], request=BroadcastSendSerializer,
        responses={200: EventBroadcastSerializer, **ERRORS},
        description="Confirm exactly the preview revision/count and send. The campaign is held for five "
                    "seconds (available_at = now + 5 s, undo_hold = true); cancelling inside the hold is the "
                    "undo. After the hold the ordinary rule applies: cancel stops unclaimed sends and "
                    "provider-accepted mail cannot be recalled.")
    def post(self, request, pk, campaign_id):
        campaign = get_campaign(request.user, pk, campaign_id)
        payload = BroadcastSendSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return Response(EventBroadcastSerializer(send_now(campaign, request.user, payload.validated_data)).data)


class BroadcastTalliesView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], responses={200: BroadcastTalliesSerializer, **ERRORS},
        description="Counts of recipients by best delivery outcome (delivered, waiting, failed, skipped) "
                    "from the delivery ledger. Never lists recipients.")
    def get(self, request, pk, campaign_id):
        campaign = get_campaign(request.user, pk, campaign_id)
        response = Response(BroadcastTalliesSerializer(tallies(campaign)).data)
        response["Cache-Control"] = "private, no-store"
        return response


class BroadcastTemplateListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], responses={200: BroadcastTemplateSerializer(many=True), **ERRORS},
        description="Thirteen starter templates that prefill subject, body, audience and design. "
                    "Requires live event manage_registrations authority, the broadcast gates and "
                    "events.broadcast_templates (404 while it is off).")
    def get(self, request, pk):
        event = event_authority.get_event(request.user, pk, MANAGE_REGISTRATIONS)
        authorize(EventBroadcast(event=event, makerspace=event.makerspace), request.user)
        if not feature_enabled(event.makerspace, "events.broadcast_templates"):
            raise NotFound()
        return Response(BroadcastTemplateSerializer(EVENT_STARTER_TEMPLATES, many=True).data)
