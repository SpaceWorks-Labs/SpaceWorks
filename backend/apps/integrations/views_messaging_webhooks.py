"""Signed provider callbacks; no browser session or tenant-module gate is needed."""
import hmac
import json
import logging

from django.db import DatabaseError
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.parsers import FormParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.openapi_errors import errors
from .messaging.senders import callback_credentials
from .messaging.webhook_payloads import meta_payloads, twilio_payload
from .messaging.webhook_processing import accept_event
from .messaging.webhook_signatures import verify_meta, verify_twilio

logger = logging.getLogger(__name__)


def credentials(channel, makerspace_id):
    return callback_credentials(channel=channel, owner="makerspace" if makerspace_id else "platform",
                                makerspace_id=makerspace_id)


def verification_secret(credential):
    try:
        return credential.get_secret("webhook_secret")
    except DatabaseError:
        raise
    except Exception:
        logger.warning("messaging_callback_credential_unreadable", extra={"credential_id": credential.pk})
        return ""


def _db_failure():
    logger.exception("messaging_webhook_database_failure")
    return Response({"code": "webhook_unavailable", "detail": "Callback storage unavailable."}, status=500)


class TwilioMessagingWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [FormParser]

    @extend_schema(tags=["Messaging webhooks"], auth=[], request={"application/x-www-form-urlencoded": OpenApiTypes.OBJECT},
        description="Twilio form callback. Requires X-Twilio-Signature, AccountSid and bound sender number.",
        parameters=[OpenApiParameter("X-Twilio-Signature", str, OpenApiParameter.HEADER, required=True)],
        responses={(200, "application/json"): OpenApiTypes.OBJECT,
                   (200, "text/xml"): OpenApiTypes.STR, **errors(400, 403, 415, 500)})
    def post(self, request, kind, makerspace_id=None):
        if request.content_type != "application/x-www-form-urlencoded":
            return Response({"detail": "Form encoding required."}, status=415)
        try:
            credential = None
            for candidate in credentials("sms", makerspace_id):
                _, sid, number = candidate.identity.sender_key.split(":", 2)
                binding = "To" if kind == "inbound" else "From"
                # Refuse ambiguous identity fields even if the signature is otherwise valid.
                if request.data.getlist("AccountSid") != [sid] or request.data.getlist(binding) != [number]:
                    continue
                secret = verification_secret(candidate)
                if secret and verify_twilio(request, secret):
                    credential = candidate
                    break
            if credential is None:
                logger.warning("messaging_webhook_signature_rejected", extra={"channel": "sms", "makerspace_id": makerspace_id})
                return Response({"detail": "Invalid callback signature or sender."}, status=403)
            normalized = twilio_payload(request.data, kind)
            if normalized is None:
                return Response({"detail": "Invalid callback fields."}, status=400)
            dedupe, payload = normalized
            accept_event(provider="twilio", channel="sms", sender_key=credential.identity.sender_key,
                         makerspace_id=makerspace_id, credential_version=credential.version, dedupe_id=dedupe, kind=kind, payload=payload)
        except DatabaseError:
            return _db_failure()
        if kind == "inbound":
            return HttpResponse('<?xml version="1.0" encoding="UTF-8"?><Response/>', content_type="text/xml")
        return Response({"accepted": True})


class MetaMessagingWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(tags=["Messaging webhooks"], auth=[], parameters=[
        OpenApiParameter("hub.mode", str, required=True), OpenApiParameter("hub.verify_token", str, required=True),
        OpenApiParameter("hub.challenge", str, required=True)],
        responses={(200, "text/plain"): OpenApiTypes.STR, **errors(400, 403, 500)})
    def get(self, request, makerspace_id=None):
        if request.query_params.get("hub.mode") != "subscribe":
            return Response({"detail": "Invalid subscription mode."}, status=403)
        supplied = request.query_params.get("hub.verify_token", "")
        try:
            if supplied and any(c.verify_token and hmac.compare_digest(c.verify_token.encode(), supplied.encode())
                                for c in credentials("whatsapp", makerspace_id)):
                challenge = request.query_params.get("hub.challenge", "")
                if not challenge:
                    return Response({"detail": "Subscription challenge required."}, status=400)
                return HttpResponse(challenge, content_type="text/plain")
        except DatabaseError:
            return _db_failure()
        return Response({"detail": "Invalid verification token."}, status=403)

    @extend_schema(tags=["Messaging webhooks"], auth=[], request=OpenApiTypes.OBJECT,
        description="Meta messages webhook; X-Hub-Signature-256 covers the exact raw JSON body.",
        parameters=[OpenApiParameter("X-Hub-Signature-256", str, OpenApiParameter.HEADER, required=True)],
        responses={200: OpenApiTypes.OBJECT, **errors(400, 403, 415, 500)})
    def post(self, request, makerspace_id=None):
        if request.content_type != "application/json":
            return Response({"detail": "JSON encoding required."}, status=415)
        raw = request.body
        signature = request.headers.get("X-Hub-Signature-256", "")
        try:
            verified = []
            for candidate in credentials("whatsapp", makerspace_id):
                secret = verification_secret(candidate)
                if secret and verify_meta(raw, secret, signature):
                    verified.append(candidate)
            if not verified:
                logger.warning("messaging_webhook_signature_rejected", extra={"channel": "whatsapp", "makerspace_id": makerspace_id})
                return Response({"detail": "Invalid callback signature."}, status=403)
            try:
                document = json.loads(raw)
            except (ValueError, UnicodeError):
                return Response({"detail": "Invalid JSON body."}, status=400)
            # A rotated app secret may cover statuses for both old and new senders.
            seen = set()
            for credential in verified:
                identity = credential.identity
                if identity.pk in seen:
                    continue
                seen.add(identity.pk)
                _, business_account_id, phone_number_id = identity.sender_key.split(":", 2)
                for kind, dedupe, payload in meta_payloads(document, phone_number_id, business_account_id):
                    accept_event(provider="meta", channel="whatsapp", sender_key=identity.sender_key,
                        makerspace_id=makerspace_id, credential_version=credential.version, dedupe_id=dedupe, kind=kind, payload=payload)
        except DatabaseError:
            return _db_failure()
        return Response({"accepted": True})
