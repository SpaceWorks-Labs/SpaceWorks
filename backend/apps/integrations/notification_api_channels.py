from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from .notification_api_errors import errors
from apps.tenant_migration.gate_runtime import tenant_write
from .models_endpoints import ChannelConfiguration, WhatsAppTemplate
from .notification_api_access import contract_space
from .notification_api_serializers import ChannelPageSerializer, ChannelPatchSerializer, ChannelSerializer
from .notification_enums import NotificationChannel
from .notification_resolution import policy_rows


class ChannelListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Notification contract"], parameters=[OpenApiParameter("page", int)],
                   responses={200: ChannelPageSerializer, **errors(400, 401, 403, 404)})
    def get(self, request, makerspace_id):
        space = contract_space(request.user, makerspace_id, manager=True)
        paginator = PageNumberPagination()
        paginator.page_size = 24
        page = paginator.paginate_queryset(policy_rows(ChannelConfiguration, space).order_by("channel"), request, view=self)
        return paginator.get_paginated_response(ChannelSerializer(page, many=True).data)


class ChannelSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Notification contract"], responses={200: ChannelSerializer, **errors(400, 401, 403, 404)})
    def get(self, request, makerspace_id, channel):
        space = contract_space(request.user, makerspace_id, manager=True)
        row = get_object_or_404(policy_rows(ChannelConfiguration, space), channel=channel)
        return Response(ChannelSerializer(row).data)

    @extend_schema(tags=["Notification contract"], request=ChannelPatchSerializer,
                   responses={200: ChannelSerializer, **errors(400, 401, 403, 404, 423, 503)})
    def patch(self, request, makerspace_id, channel):
        space = contract_space(request.user, makerspace_id, manager=True)
        if channel not in NotificationChannel.values:
            raise ValidationError({"channel": "Unknown channel."})
        serializer = ChannelPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with tenant_write(space.pk), transaction.atomic():
            # Serialize first-install races using the parent, then configuration.
            type(space).objects.select_for_update(no_key=True).get(pk=space.pk)
            row, _ = policy_rows(ChannelConfiguration, space).get_or_create(channel=channel, makerspace=space,
                defaults={"provider": "twilio" if channel == "whatsapp" else channel if channel in {"telegram", "slack", "mattermost", "discord", "webhook"} else "builtin"})
            provider = data.get("provider", row.provider)
            expected = {"twilio", "meta"} if channel == "whatsapp" else {channel} if channel in {"telegram", "slack", "mattermost", "discord", "webhook"} else {"builtin"}
            if provider not in expected:
                raise ValidationError({"provider": "Provider does not match this channel."})
            if data.get("room_enabled") and channel not in {"telegram", "slack", "mattermost", "discord", "webhook"}:
                raise ValidationError({"room_enabled": "This channel has no staff rooms."})
            if data.get("personal_enabled") and channel == "webhook":
                raise ValidationError({"personal_enabled": "Webhooks are staff destinations."})
            rotate = any(key in data for key in ("credentials", "integration_identity", "provider"))
            for key, value in data.items():
                if key not in {"credentials", "templates"}:
                    setattr(row, key, value)
            if "credentials" in data:
                row.set_credentials(data["credentials"])
            if rotate:
                row.generation += 1
            if row.personal_enabled and channel in {"telegram", "slack", "mattermost", "discord", "whatsapp"} and not row.integration_identity:
                raise ValidationError({"integration_identity": "Install the integration before enabling personal delivery."})
            row.save()
            if "templates" in data:
                if channel != "whatsapp":
                    raise ValidationError({"templates": "Templates apply to WhatsApp only."})
                row.templates.all().delete()
                for template in data["templates"]:
                    WhatsAppTemplate.objects.create(configuration=row, **template)
            audit.record(request.user, "notification.channel_configured", makerspace=space, target=row,
                         meta={"channel": channel, "fields": sorted(data), "generation": row.generation})
        return Response(ChannelSerializer(row).data)
