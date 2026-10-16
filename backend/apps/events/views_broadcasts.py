from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from . import event_authority
from .broadcasts import authorize
from .event_permissions import MANAGE_REGISTRATIONS
from .models_broadcasts import EventBroadcast
from .serializers_admin import EmptyActionSerializer
from .serializers_broadcasts import (
    EventBroadcastInputSerializer, EventBroadcastSerializer, EventBroadcastListSerializer,
)
from .services_broadcasts import compose, change
from .views_invites import ERRORS, PAGE_PARAMETERS, paginated


class EventBroadcastListView(APIView):
    permission_classes = [IsActiveStaff]

    def event(self, actor, pk):
        event = event_authority.get_event(actor, pk, MANAGE_REGISTRATIONS)
        authorize(EventBroadcast(event=event, makerspace=event.makerspace), actor)
        return event

    @extend_schema(tags=["Admin events"], description="Requires live event manage_registrations authority and events.broadcasts, notifications and email.", parameters=PAGE_PARAMETERS, responses={200: EventBroadcastListSerializer, **ERRORS})
    def get(self, request, pk):
        event = self.event(request.user, pk)
        return paginated(request, event.broadcasts.filter(makerspace=event.makerspace).order_by("-created_at", "-pk"), EventBroadcastSerializer)

    @extend_schema(tags=["Admin events"], description="Compose an audited draft. Requires manage_registrations and events.broadcasts, notifications and email; placeholders never include credentials.", request=EventBroadcastInputSerializer, responses={201: EventBroadcastSerializer, **ERRORS})
    def post(self, request, pk):
        event = self.event(request.user, pk)
        payload = EventBroadcastInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return Response(EventBroadcastSerializer(compose(event, request.user, **payload.validated_data)).data, status=201)


class EventBroadcastActionView(APIView):
    permission_classes = [IsActiveStaff]
    action = "queue"

    @extend_schema(tags=["Admin events"], description="Queue or cancel under live event authority. Queue limit: ten broadcasts per hour per makerspace. Cancellation stops unclaimed sends.", request=EmptyActionSerializer, responses={200: EventBroadcastSerializer, **ERRORS})
    def post(self, request, pk, campaign_id):
        event = event_authority.get_event(request.user, pk, MANAGE_REGISTRATIONS)
        campaign = get_object_or_404(EventBroadcast, event=event, pk=campaign_id)
        payload = EmptyActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return Response(EventBroadcastSerializer(change(campaign, request.user, self.action)).data)
