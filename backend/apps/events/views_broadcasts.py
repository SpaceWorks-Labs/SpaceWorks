from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, PolymorphicProxySerializer, extend_schema
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
    BroadcastCommandSerializer,
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
        response = paginated(request, event.broadcasts.filter(makerspace=event.makerspace).order_by("-created_at", "-pk"), EventBroadcastSerializer)
        response["Cache-Control"] = "private, no-store"
        return response

    @extend_schema(tags=["Admin events"], description="Compose an audited draft. Version 2 requires a UUID Idempotency-Key. Requires manage_registrations and events.broadcasts, notifications and email; placeholders never include credentials.",
        parameters=[OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER,
                                     description="Required UUID for version 2 composer creation.")],
        request=EventBroadcastInputSerializer, responses={201: EventBroadcastSerializer, **ERRORS})
    def post(self, request, pk):
        event = self.event(request.user, pk)
        payload = EventBroadcastInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        values = payload.validated_data
        if values["render_schema_version"] == 2:
            from rest_framework import serializers
            from .programme.broadcast_preview import create_composer
            operation_id = serializers.UUIDField().run_validation(request.headers.get("Idempotency-Key"))
            campaign = create_composer(event, request.user, values, operation_id)
        else:
            campaign = compose(event, request.user, **values)
        return Response(EventBroadcastSerializer(campaign).data, status=201)


class EventBroadcastActionView(APIView):
    permission_classes = [IsActiveStaff]
    action = "queue"

    @extend_schema(tags=["Admin events"], description="Queue or cancel under live event authority. "
        "Legacy v1 actions use an empty body. Version 2 cancellation requires operation_id and expected_version; "
        "v2 queue uses the separate preview/confirmation schedule command. "
        "Queue limit: ten broadcasts per hour per makerspace. Cancellation stops unclaimed sends.",
        request=PolymorphicProxySerializer(component_name="EventBroadcastActionInput",
            serializers=[EmptyActionSerializer, BroadcastCommandSerializer], resource_type_field_name=None),
        responses={200: EventBroadcastSerializer, **ERRORS})
    def post(self, request, pk, campaign_id):
        event = event_authority.get_event(request.user, pk, MANAGE_REGISTRATIONS)
        campaign = get_object_or_404(EventBroadcast, event=event, pk=campaign_id)
        if self.action == "cancel" and campaign.render_schema_version == 2:
            from .programme.broadcast_schedule import cancel_composer
            payload = BroadcastCommandSerializer(data=request.data)
            payload.is_valid(raise_exception=True)
            changed = cancel_composer(campaign, request.user, payload.validated_data)
            return Response(EventBroadcastSerializer(changed).data)
        payload = EmptyActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return Response(EventBroadcastSerializer(change(campaign, request.user, self.action)).data)
