"""Signature-only ingress plus Space Manager approval refresh; no message bodies out."""
from django.utils.translation import gettext
import hashlib
import logging
from dataclasses import replace

from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.audit import services as audit
from apps.makerspaces.servability import servable_queryset
from apps.openapi_errors import errors
from apps.tenant_migration.gate_runtime import tenant_write
from .models_endpoints import ChannelConfiguration
from .notification_api_access import contract_space
from .notification_api_serializers import StrictSerializer
from .notification_proofs import verified_callback
from .notification_wa_twilio import TwilioWhatsAppProvider
from .notification_wa_twilio_config import ConfigurationError
from .notification_wa_twilio_templates import refresh_approvals

logger = logging.getLogger(__name__)


class CallbackDependencyUnavailable(APIException):
    status_code = 503
    default_detail = "Callback processing is temporarily unavailable."
    default_code = "unavailable"


class CallbackThrottle(SimpleRateThrottle):
    scope = "whatsapp_twilio_callback"
    rate = "600/minute"

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except Exception:
            raise CallbackDependencyUnavailable() from None

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope,
            "ident": f"{view.kwargs.get('makerspace_id')}:{self.get_ident(request)}"}


class ApprovalThrottle(UserRateThrottle):
    scope = "whatsapp_twilio_approvals"
    rate = "5/hour"


class TwilioCallbackSerializer(serializers.Serializer):
    AccountSid = serializers.CharField()
    MessageSid = serializers.CharField()
    From = serializers.CharField()
    To = serializers.CharField()
    Body = serializers.CharField(required=False, allow_blank=True, write_only=True)
    MessageStatus = serializers.ChoiceField(choices=["accepted", "queued", "sending", "sent", "delivered", "read",
                                                     "failed", "undelivered", "canceled"], required=False)
    SmsStatus = serializers.CharField(required=False)
    MessagingServiceSid = serializers.CharField(required=False)


class ApprovalResultSerializer(serializers.Serializer):
    checked = serializers.IntegerField()
    approved = serializers.IntegerField()
    unavailable = serializers.IntegerField()


class ApprovalRequestSerializer(StrictSerializer):
    content_sids = serializers.ListField(child=serializers.RegexField(r"^HX[0-9a-fA-F]{32}$"),
                                        min_length=1, max_length=5, required=False)


class TwilioWhatsAppWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [FormParser]
    throttle_classes = [CallbackThrottle]

    @extend_schema(tags=["WhatsApp Twilio"], auth=[], request=TwilioCallbackSerializer,
        parameters=[OpenApiParameter("X-Twilio-Signature", str, location="header", required=True)],
        responses={200: OpenApiResponse(description="Empty TwiML response; no outbound reply."),
                   **errors(400, 403, 404, 415, 423, 429, 500, 503)},
        description="Signed form callbacks; URL generation must match the current integration. Extra Twilio fields are signed too.")
    def post(self, request, makerspace_id, generation, kind, delivery_id=None):
        from .notification_sender import callback_configurations
        from .notification_ingress import accept_callback
        from .messaging.webhook_payloads import phone_hash, timestamp
        from .notification_cutover import boundary
        with boundary():
            config = None
            for candidate in callback_configurations(makerspace_id, "twilio", generation):
                event = TwilioWhatsAppProvider(candidate).verify_callback(request)
                if event is not None:
                    config = candidate
                    break
            if config is None:
                raise PermissionDenied(gettext("Invalid provider callback."))
            params = request.POST
            protection = {"stop": event.opt_out,
                "phone_hash": phone_hash(params.get("From") if kind == "inbound" else params.get("To")),
                "error_code": params.get("ErrorCode", ""),
                "timestamp": timestamp(params.get("Timestamp") or params.get("DateSent"))}
            # The provider MessageSid and event state identify a retry, not receipt time.
            identity = [params["MessageSid"], kind, event.state, params.get("ErrorCode", ""), event.opt_out, event.opt_in]
            moment = None
            if kind == "inbound":
                from .notification_wa_window import inbound_time
                from django.utils import timezone
                moment = inbound_time(timestamp(params.get("Timestamp"))) if params.get("Timestamp") else timezone.now()
                if event.proof:
                    from django.utils.crypto import salted_hmac
                    event = replace(event, identity_digest=salted_hmac("notification.endpoint.identity.v1",
                        f"{config.pk}:{config.generation}:{event.proof.subject}", algorithm="sha256").hexdigest())
                event = replace(event, inbound=False)
            accept_callback(config, event, identity=identity, protection=protection,
                inbound_at=moment.isoformat() if moment else None)
        return HttpResponse("<Response/>", content_type="application/xml")


class TwilioWhatsAppTemplateRefreshView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ApprovalThrottle]

    @extend_schema(tags=["WhatsApp Twilio"], request=ApprovalRequestSerializer,
        responses={200: ApprovalResultSerializer, **errors(400, 401, 403, 404, 423, 429, 503)},
        description="Space Manager only. Confirm each bound Content SID's WhatsApp approval with Twilio.")
    def post(self, request, makerspace_id):
        space = contract_space(request.user, makerspace_id, manager=True)
        config = get_object_or_404(rbac.scope_notification_policy(ChannelConfiguration.objects.all(),
            makerspace_id=space.pk), channel="whatsapp", provider="twilio")
        serializer = ApprovalRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            credentials = TwilioWhatsAppProvider(config).credentials()
        except ConfigurationError:
            raise ValidationError({"credentials": gettext("Twilio configuration is incomplete or invalid.")}) from None
        return Response(refresh_approvals(config, credentials, request.user,
            content_sids=serializer.validated_data.get("content_sids")))
