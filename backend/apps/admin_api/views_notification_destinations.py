"""Staff CRUD for chat destinations (the rooms a makerspace posts into).

Console parity is not optional here: `/control/` is not proxied on the public frontend
port, so without this API a space manager could not create, credential or scope a room at
all. Every write is `MANAGE_MAKERSPACE` — a destination holds a bearer secret and decides
who sees a machine's alerts, which is makerspace configuration rather than machine work.
"""

from django.utils.translation import gettext
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, require_action
from apps.admin_api.serializers_notification_destinations import (
    NotificationDestinationSerializer,
    NotificationDestinationWriteSerializer,
)
from apps.audit import services as audit
from apps.integrations.dispatch_channels import channel_module_blocks
from apps.admin_api.notification_scope import ScopeTargetError, apply_scope
from apps.integrations.models_destinations import NotificationDestination
from apps.integrations.webhook_secrets import clear_previous, rotate_signing_secret
from apps.integrations.notification_enums import ChatNotificationChannel
from apps.makerspaces.servability import servable_queryset
from apps.openapi_errors import errors


def _makerspace(request, makerspace_id):
    require_action(request.user, rbac.Action.MANAGE_MAKERSPACE, makerspace_id)
    return get_object_or_404(
        servable_queryset(), pk=makerspace_id
    )


def _queryset(makerspace):
    return NotificationDestination.objects.filter(makerspace=makerspace).prefetch_related(
        "machine_scopes", "machine_type_scopes", "category_scopes"
    )


@extend_schema(tags=["Makerspaces"], summary="List or create chat notification destinations")
class NotificationDestinationListView(APIView):
    permission_classes = [IsActiveStaff]
    http_method_names = ["get", "post", "head", "options"]

    @extend_schema(
        responses={
            200: NotificationDestinationSerializer(many=True),
            **errors(401, 403, 404),
        }
    )
    def get(self, request, makerspace_id, *args, **kwargs):
        makerspace = _makerspace(request, makerspace_id)
        return Response(
            NotificationDestinationSerializer(_queryset(makerspace), many=True).data
        )

    @extend_schema(
        request=NotificationDestinationWriteSerializer,
        responses={
            201: NotificationDestinationSerializer,
            400: OpenApiResponse(description="Invalid destination."),
        },
    )
    def post(self, request, makerspace_id, *args, **kwargs):
        makerspace = _makerspace(request, makerspace_id)
        payload = NotificationDestinationWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        # A room on a channel whose module is uninstalled would accept the credential and
        # then SKIP every send — the same reason the matrix omits that column entirely.
        if channel_module_blocks(makerspace, data["channel"]):
            return Response(
                {"detail": gettext('The {value} module is not installed.').format(value=data['channel'])},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            if data["channel"] == ChatNotificationChannel.WEBHOOK:
                # LM-3 (decision 284): the NUMBER of outbound webhook endpoints is a limit key; serialise
                # concurrent creators on the makerspace row, then refuse with the typed 409.
                from apps.makerspaces.models import Makerspace
                from apps.managed_hosting.extra_quotas import check_extra_quota
                check_extra_quota(Makerspace.objects.select_for_update().get(pk=makerspace.pk), "webhook_endpoints")
            destination = NotificationDestination(
                makerspace=makerspace,
                channel=data["channel"],
                label=data["label"],
                telegram_chat_id=(data.get("telegram_chat_id") or "").strip(),
                is_active=data.get("is_active", True),
                payload_version=data["payload_version"],
            )
            raw = (data.get("webhook_url") or "").strip()
            if raw:
                destination.set_webhook_url(raw)
            secret = data.get("signing_secret") or ""
            generated = ""
            if secret:
                destination.set_signing_secret(secret)
            elif data["channel"] == ChatNotificationChannel.WEBHOOK:
                # Parity E-B8: the server makes the secret; it is returned below, once, and never readable again.
                generated = rotate_signing_secret(destination)
            destination.save()
            try:
                apply_scope(destination, data.get("scope"), makerspace)
            except ScopeTargetError as exc:
                return Response(
                    {"detail": gettext("Unknown scope target."), "unknown": exc.missing},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            audit.record(
                request.user,
                "notification.destination_created",
                makerspace=makerspace,
                target=makerspace,
                meta={"channel": destination.channel, "label": destination.label,
                      "secret_generated": bool(generated)},
            )
        body = NotificationDestinationSerializer(destination).data
        if generated:
            body = {**body, "signing_secret": generated}
        return Response(body, status=status.HTTP_201_CREATED, headers={"Cache-Control": "no-store"})


@extend_schema(tags=["Makerspaces"], summary="Update or delete a chat notification destination")
class NotificationDestinationDetailView(APIView):
    permission_classes = [IsActiveStaff]
    http_method_names = ["put", "delete", "head", "options"]

    def _destination(self, request, makerspace_id, destination_id):
        makerspace = _makerspace(request, makerspace_id)
        return makerspace, get_object_or_404(_queryset(makerspace), pk=destination_id)

    @extend_schema(
        request=NotificationDestinationWriteSerializer,
        responses={
            200: NotificationDestinationSerializer,
            400: OpenApiResponse(description="Invalid destination."),
        },
    )
    def put(self, request, makerspace_id, destination_id, *args, **kwargs):
        makerspace, destination = self._destination(request, makerspace_id, destination_id)
        payload = NotificationDestinationWriteSerializer(
            data=request.data, context={"instance": destination}
        )
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        with transaction.atomic():
            destination.label = data["label"]
            destination.telegram_chat_id = (data.get("telegram_chat_id") or "").strip()
            destination.is_active = data.get("is_active", True)
            destination.payload_version = data["payload_version"]
            raw = (data.get("webhook_url") or "").strip()
            if raw:
                # Blank means "keep the stored credential": the caller cannot read it back,
                # so requiring it on every edit would force a re-entry to rename a room.
                destination.set_webhook_url(raw)
            secret = data.get("signing_secret") or ""
            if secret:
                destination.set_signing_secret(secret)
                clear_previous(destination)
            destination.save()
            try:
                apply_scope(destination, data.get("scope"), makerspace)
            except ScopeTargetError as exc:
                return Response(
                    {"detail": gettext("Unknown scope target."), "unknown": exc.missing},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            audit.record(
                request.user,
                "notification.destination_updated",
                makerspace=makerspace,
                target=makerspace,
                meta={
                    "destination_id": destination.pk,
                    "channel": destination.channel,
                    "credential_changed": bool(raw),
                },
            )
        destination = _queryset(makerspace).get(pk=destination.pk)
        return Response(NotificationDestinationSerializer(destination).data)

    @extend_schema(
        responses={
            204: OpenApiResponse(description="Destination removed."),
            **errors(401, 403, 404),
        }
    )
    def delete(self, request, makerspace_id, destination_id, *args, **kwargs):
        makerspace, destination = self._destination(request, makerspace_id, destination_id)
        label, channel = destination.label, destination.channel
        with transaction.atomic():
            # Delivery history survives: NotificationDeliveryLog.destination is SET_NULL
            # and the label snapshot keeps past failures attributable to this room.
            destination.delete()
            audit.record(
                request.user,
                "notification.destination_deleted",
                makerspace=makerspace,
                target=makerspace,
                meta={"channel": channel, "label": label},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
