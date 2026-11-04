from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication import require_recent_reauth
from apps.audit import services as audit
from .notification_api_errors import REAUTH_403, errors
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
                   responses={200: ChannelSerializer, **errors(400, 401, 403, 404, 409, 423, 503, e403=REAUTH_403)})
    def patch(self, request, makerspace_id, channel):
        space = contract_space(request.user, makerspace_id, manager=True)
        if channel not in NotificationChannel.values:
            raise ValidationError({"channel": "Unknown channel."})
        # Writing or clearing (`{}`) secrets steps up; non-secret toggles do not.
        if "credentials" in request.data:
            require_recent_reauth(request)
        serializer = ChannelPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        from .notification_configuration import configure
        row = configure(space, request.user, channel, data)
        return Response(ChannelSerializer(row).data)
