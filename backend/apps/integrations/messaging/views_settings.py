"""Space-Manager messaging settings, scoped through RBAC."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.reauthentication import require_recent_reauth
from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import module_enabled
from apps.openapi_errors import errors
from .serializers import MessagingSettingsSerializer
from .settings_service import save_settings, settings_payload


def staff_space(actor, makerspace_id):
    return get_object_or_404(rbac.scope_by_action(actor, rbac.Action.MANAGE_MAKERSPACE,
                            Makerspace.objects.all(), field="pk"), pk=makerspace_id)


def settings_space(actor, makerspace_id):
    space = staff_space(actor, makerspace_id)
    # This shared configuration surface belongs to either addressed channel.
    if not any(module_enabled(space, channel) for channel in ("sms", "whatsapp")):
        from apps.makerspaces.guards import module_off
        raise module_off("sms", "SMS and WhatsApp are turned off for this makerspace.")
    return space


class MessagingSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Messaging"], responses={200: MessagingSettingsSerializer, **errors(400, 401, 403, 404)})
    def get(self, request, makerspace_id):
        space = settings_space(request.user, makerspace_id)
        return Response(MessagingSettingsSerializer(settings_payload(space)).data)

    @extend_schema(tags=["Messaging"], request=MessagingSettingsSerializer,
                   responses={200: MessagingSettingsSerializer, **errors(400, 401, 403, 404, 409, 410, 423, 503)})
    def patch(self, request, makerspace_id):
        space = settings_space(request.user, makerspace_id)
        require_recent_reauth(request)
        serializer = MessagingSettingsSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        save_settings(request.user, space, serializer.validated_data)
        return Response(MessagingSettingsSerializer(settings_payload(space)).data)
