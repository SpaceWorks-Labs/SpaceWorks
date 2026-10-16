"""Signature-only ingress plus Space Manager approval refresh; no message bodies out."""
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
                   **errors(400, 403, 404, 415, 423, 429, 503)},
        description="Signed form callbacks; URL generation must match the current integration. Extra Twilio fields are signed too.")
    def post(self, request, makerspace_id, generation, kind, delivery_id=None):
        rows = rbac.scope_notification_policy(servable_queryset(ChannelConfiguration.objects.all(), relation="makerspace"),
            makerspace_id=makerspace_id)
        config = get_object_or_404(rows, channel="whatsapp", provider="twilio", generation=generation,
                                  enabled=True, personal_enabled=True)
        provider = TwilioWhatsAppProvider(config)
        if not provider.active() or provider.verify_callback(request) is None:
            raise PermissionDenied("Invalid provider callback.")
        # Twilio retries the same inbound MessageSid. A short cache reservation
        # prevents those retries from extending the 24h session window repeatedly.
        key = ""
        if kind == "inbound":
            digest = hashlib.sha256(f"{config.pk}:{generation}:{request.POST['MessageSid']}".encode()).hexdigest()
            key = "whatsapp:twilio:inbound:" + digest
            try:
                reserved = cache.add(key, True, timeout=86400)
            except Exception:
                raise CallbackDependencyUnavailable() from None
            if not reserved:
                return HttpResponse("<Response/>", content_type="application/xml")
        try:
            proof_error = None
            with tenant_write(makerspace_id), transaction.atomic():
                from apps.encryption.write_fence import assert_mapped_write_allowed
                assert_mapped_write_allowed(makerspace_id)
                # Rotation and proof consumption use this same lock. Reverify after
                # acquiring it so a rotated installation cannot win a callback race.
                config = rows.select_for_update(of=("self",)).get(pk=config.pk)
                provider = TwilioWhatsAppProvider(config)
                event = provider.verify_callback(request) if provider.active() else None
                if event is None:
                    raise PermissionDenied("Invalid provider callback.")
                if event.state == "failed":
                    # A fast failure can arrive before the REST response marks
                    # acceptance. Failure proves Twilio accepted the message first;
                    # bridge that acknowledgement through the same monotonic seam.
                    from .notification_delivery import apply_callback
                    apply_callback(config, replace(event, state="accepted"))
                try:
                    result = verified_callback(config, request)
                except ValidationError as exc:
                    # consume() deliberately raises AFTER saving a failed attempt.
                    # Preserve it when our wider rotation lock transaction commits.
                    proof_error, result = exc, False
                    audit.record(None, "notification.whatsapp_proof_rejected", makerspace=config.makerspace,
                                 target=config)
                if not proof_error and (result or (event.inbound and event.endpoint_id and not event.opt_out)):
                    audit.record(None, "notification.whatsapp_callback_applied", makerspace=config.makerspace,
                        target=config, meta={"kind": kind, "state": event.state or "inbound"})
            if proof_error:
                raise proof_error
        except Exception:
            if key:
                try:
                    cache.delete(key)
                except Exception:
                    logger.warning("whatsapp_twilio_replay_release_failed")
            raise
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
            raise ValidationError({"credentials": "Twilio configuration is incomplete or invalid."}) from None
        return Response(refresh_approvals(config, credentials, request.user,
            content_sids=serializer.validated_data.get("content_sids")))
