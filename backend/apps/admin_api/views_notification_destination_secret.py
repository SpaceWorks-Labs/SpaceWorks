"""POST .../notification-destinations/<id>/rotate-secret: replace a signed webhook's signing secret (A10).

`MANAGE_MAKERSPACE`, like every write to a destination. The new secret is in this response and nowhere else, ever;
the old one keeps verifying for `grace_hours` (default 24, 0 retires it at once) so the receiver can switch over.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.admin_api.serializers_notification_destinations import NotificationDestinationSerializer
from apps.audit import services as audit
from apps.integrations.models_destinations import NotificationDestination
from apps.integrations.notification_enums import ChatNotificationChannel
from apps.integrations.webhook_secrets import DEFAULT_GRACE_HOURS, MAX_GRACE_HOURS, rotate_signing_secret
from apps.makerspaces.servability import servable_queryset
from apps.openapi_errors import errors


class RotateSecretRequestSerializer(serializers.Serializer):
    grace_hours = serializers.IntegerField(required=False, min_value=0, max_value=MAX_GRACE_HOURS,
                                           default=DEFAULT_GRACE_HOURS)


class RotateSecretResponseSerializer(serializers.Serializer):
    destination = NotificationDestinationSerializer()
    signing_secret = serializers.CharField(help_text="The new secret. Shown once; it cannot be read again.")
    previous_valid_until = serializers.DateTimeField(allow_null=True)


class NotificationDestinationRotateSecretView(APIView):
    permission_classes = [IsActiveStaff]
    http_method_names = ["post", "options"]

    @extend_schema(
        tags=["Makerspaces"], summary="Rotate a signed webhook's signing secret",
        request=RotateSecretRequestSerializer,
        responses={200: RotateSecretResponseSerializer, **errors(400, 401, 403, 404)},
    )
    def post(self, request, makerspace_id, destination_id):
        require_action(request.user, rbac.Action.MANAGE_MAKERSPACE, makerspace_id)
        makerspace = get_object_or_404(servable_queryset(), pk=makerspace_id)
        body = RotateSecretRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        grace = body.validated_data["grace_hours"]
        with transaction.atomic():
            destination = get_object_or_404(
                NotificationDestination.objects.select_for_update().filter(makerspace=makerspace), pk=destination_id)
            if destination.channel != ChatNotificationChannel.WEBHOOK:
                return Response({"code": "not_a_signed_webhook",
                                "detail": gettext("Only signed-webhook destinations have a signing secret.")},
                                status=status.HTTP_400_BAD_REQUEST)
            fresh = rotate_signing_secret(destination, grace_hours=grace)
            destination.save()
            audit.record(request.user, "notification_destination.secret_rotated", makerspace=makerspace,
                         target=makerspace, meta={"destination_id": destination.pk, "grace_hours": grace})
        destination = NotificationDestination.objects.prefetch_related(
            "machine_scopes", "machine_type_scopes", "category_scopes").get(pk=destination.pk)
        data = NotificationDestinationSerializer(destination).data
        return Response({"destination": data, "signing_secret": fresh,
                         "previous_valid_until": data["signing_secret_grace_until"]},
                        headers={"Cache-Control": "no-store"})
