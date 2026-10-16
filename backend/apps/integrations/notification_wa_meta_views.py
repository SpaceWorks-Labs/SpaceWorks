"""Provider-authenticated Meta ingress. No JWT, browser cookies or chat decisions."""
import hmac
import logging

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.makerspaces.servability import servable_queryset
from .models_endpoints import ChannelConfiguration
from .notification_api_errors import errors
from .notification_wa_meta_callbacks import items, verified_payload
from .notification_wa_meta_http import ID, credentials
from .notification_wa_meta_ingress import apply_item
from .notification_wa_meta_schema import MetaWebhookSerializer

logger = logging.getLogger(__name__)


class MetaWebhookThrottle(SimpleRateThrottle):
    scope = "whatsapp_meta_webhook"
    rate = "120/min"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope,
            "ident": f"{view.kwargs.get('makerspace_id')}:{self.get_ident(request)}"}


class MetaWebhookResultSerializer(serializers.Serializer):
    accepted = serializers.BooleanField()


class MetaWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [MetaWebhookThrottle]

    def configuration(self, makerspace_id, generation, phone_number_id):
        if type(makerspace_id) is not int or makerspace_id < 1 or not ID.fullmatch(phone_number_id):
            return None
        rows = rbac.scope_notification_policy(ChannelConfiguration.objects.select_related("makerspace"),
            makerspace_id=makerspace_id)
        return get_object_or_404(servable_queryset(rows, relation="makerspace"), channel="whatsapp",
                                 provider="meta", generation=generation)

    @extend_schema(tags=["Notification contract"], auth=[], parameters=[
        OpenApiParameter("hub.mode", str, required=True, description="Must equal subscribe."),
        OpenApiParameter("hub.verify_token", str, required=True, description="Configured webhook verify token."),
        OpenApiParameter("hub.challenge", str, required=True, description="Opaque challenge echoed as text/plain."),
    ], responses={(200, "text/plain"): OpenApiResponse(str, description="Unmodified challenge."),
                  **errors(400, 403, 404, 429, 503)})
    def get(self, request, makerspace_id, generation, phone_number_id):
        try:
            config = self.configuration(makerspace_id, generation, phone_number_id)
            values = credentials(config) if config else {}
            token = request.query_params.get("hub.verify_token", "")
            challenge = request.query_params.get("hub.challenge", "")
            valid = bool(values and phone_number_id == values["phone_number_id"]
                and request.query_params.get("hub.mode") == "subscribe"
                and len(token) <= 8000 and hmac.compare_digest(token.encode(), values["webhook_verify_token"].encode()))
            if not valid:
                return Response({"detail": "Webhook verification failed.", "code": "invalid_webhook"}, status=403)
            if not challenge or len(challenge) > 4096:
                return Response({"detail": "Invalid challenge.", "code": "invalid_challenge"}, status=400)
            return HttpResponse(challenge, content_type="text/plain")
        except (KeyError, TypeError, ValueError):
            return Response({"detail": "Webhook verification failed.", "code": "invalid_webhook"}, status=403)

    @extend_schema(tags=["Notification contract"], auth=[],
        parameters=[OpenApiParameter("X-Hub-Signature-256", str, location="header", required=True,
            description="sha256= + HMAC-SHA256 of the raw request body using the app secret.")],
        request=MetaWebhookSerializer, responses={200: MetaWebhookResultSerializer, **errors(400, 403, 404, 423, 429, 503)},
        description="Signed batch of messages/statuses/user_preferences. WABA and phone number must match the configured installation and URL generation.")
    def post(self, request, makerspace_id, generation, phone_number_id):
        config = self.configuration(makerspace_id, generation, phone_number_id)
        if config is None:
            return Response({"detail": "Webhook verification failed.", "code": "invalid_webhook"}, status=403)
        payload = verified_payload(config, request)
        if payload is None:
            return Response({"detail": "Webhook verification failed.", "code": "invalid_webhook"}, status=403)
        try:
            batch = items(config, payload)
        except ValueError:
            return Response({"detail": "Invalid webhook payload.", "code": "invalid_payload"}, status=400)
        try:
            for index, item in enumerate(batch):
                apply_item(config, request, index, item)
        except Exception as exc:
            # No payload, exception text, destination, provider id or token is logged.
            from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
            if isinstance(exc, SourceMigrationGateClosed):
                return Response({"detail": "Makerspace writes are frozen.", "code": "tenant_migration_quiesced"}, status=423)
            logger.warning("notification.meta_callback_unavailable", extra={"configuration_id": config.pk})
            return Response({"detail": "Webhook processing is temporarily unavailable.", "code": "unavailable"}, status=503)
        return Response({"accepted": True})
