"""Exact-authority status and separate, closed composer commands."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.events import event_authority
from apps.events.broadcasts import authorize
from apps.events.event_permissions import MANAGE_REGISTRATIONS
from apps.events.models_broadcasts import EventBroadcast
from apps.events.serializers_broadcasts import (
    BroadcastCommandSerializer, BroadcastPreviewSerializer, BroadcastScheduleSerializer,
    BroadcastTestResultSerializer, BroadcastTestSerializer, EventBroadcastSerializer,
)
from apps.events.views_invites import ERRORS

from .broadcast_preview import create_preview
from .broadcast_schedule import schedule
from .broadcast_test import test_self


def get_campaign(actor, pk, campaign_id):
    event = event_authority.get_event(actor, pk, MANAGE_REGISTRATIONS)
    campaign = get_object_or_404(EventBroadcast, event=event, pk=campaign_id)
    campaign.event = event
    authorize(campaign, actor)
    return campaign


class BroadcastDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], responses={200: EventBroadcastSerializer, **ERRORS},
        description="Read one campaign under live event manage_registrations authority and broadcast gates.")
    def get(self, request, pk, campaign_id):
        response = Response(EventBroadcastSerializer(get_campaign(request.user, pk, campaign_id)).data)
        response["Cache-Control"] = "private, no-store"
        return response


class BroadcastPreviewView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], request=BroadcastCommandSerializer,
        responses={200: BroadcastPreviewSerializer, **ERRORS},
        description="Create an immutable, sender-owned audience revision/count and safe desktop/mobile preview.")
    def post(self, request, pk, campaign_id):
        campaign = get_campaign(request.user, pk, campaign_id)
        payload = BroadcastCommandSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        response = Response(create_preview(campaign, request.user, payload.validated_data))
        response["Cache-Control"] = "private, no-store"
        return response


class BroadcastTestView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], request=BroadcastTestSerializer,
        responses={200: BroadcastTestResultSerializer, **ERRORS},
        description="Queue a test solely to the authenticated sender's own verified email. No address input.")
    def post(self, request, pk, campaign_id):
        campaign = get_campaign(request.user, pk, campaign_id)
        payload = BroadcastTestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return Response(test_self(campaign, request.user, payload.validated_data))


class BroadcastScheduleView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], request=BroadcastScheduleSerializer,
        responses={200: EventBroadcastSerializer, **ERRORS},
        description="Confirm exactly the preview revision/count and checkbox; deadline is at least now+5 seconds. "
                    "Cancel stops unclaimed sends; provider-accepted mail cannot be recalled.")
    def post(self, request, pk, campaign_id):
        campaign = get_campaign(request.user, pk, campaign_id)
        payload = BroadcastScheduleSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return Response(EventBroadcastSerializer(schedule(campaign, request.user, payload.validated_data)).data)
