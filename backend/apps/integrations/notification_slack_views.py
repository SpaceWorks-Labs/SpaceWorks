"""Chat OAuth callbacks and signed, acknowledge-only inbound endpoints."""
from django.utils.translation import gettext
import json

from django.shortcuts import get_object_or_404
from django.core import signing
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.reauthentication import require_recent_reauth
from apps.makerspaces.guards import require_module
from apps.makerspaces.servability import servable_queryset
from .models_endpoints import ChannelConfiguration
from .notification_api_access import contract_space
from .notification_api_errors import REAUTH_403, errors
from .notification_slack_http import ProviderFailure
from .notification_slack_installation import (
    CallbackStatusSerializer, OAuthStartSerializer, InstallationStatusSerializer,
    OAuthCallbackSerializer, install_mattermost, install_discord,
)


class ChatAnonThrottle(AnonRateThrottle):
    rate = "60/min"
    scope = "notification_chat_callback"


class ChatUserThrottle(UserRateThrottle):
    rate = "20/hour"
    scope = "notification_chat_install"


def configuration(makerspace_id, channel):
    from apps.makerspaces.models import Makerspace
    space = get_object_or_404(rbac.scope_notification_policy(servable_queryset(Makerspace.objects.all()),
                             makerspace_id=makerspace_id, field="pk"))
    require_module(space, "notifications")
    require_module(space, channel)
    return get_object_or_404(rbac.scope_notification_policy(ChannelConfiguration.objects.all(),
                            makerspace_id=space.pk), channel=channel, provider=channel)


def provider_error():
    return Response({"detail": gettext("Provider operation failed. Restart the connection."),
                     "code": "provider_error"}, status=400)


class ChatOAuthCallbackView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ChatUserThrottle]
    channel = ""
    http_method_names = ["get", "post", "options"]

    @extend_schema(tags=["Chat notifications"], parameters=[OpenApiParameter("state", str, required=True),
        OpenApiParameter("code", str, required=True)],
        responses={200: CallbackStatusSerializer, **errors(400, 401, 403, 404, 429, 423, 503)})
    def get(self, request, makerspace_id):
        return self.complete(request, makerspace_id, request.query_params)

    @extend_schema(tags=["Chat notifications"], request=OAuthCallbackSerializer,
        responses={200: CallbackStatusSerializer, **errors(400, 401, 403, 404, 429, 423, 503)},
        description="Authenticated Slack installation completion only. Personal OAuth uses the personal challenge verify route.")
    def post(self, request, makerspace_id):
        return self.complete(request, makerspace_id, request.data)

    def complete(self, request, makerspace_id, data):
        config = configuration(makerspace_id, self.channel)
        if (not hasattr(data, "get") or not isinstance(data.get("code"), str)
                or not isinstance(data.get("state"), str)
                or not 1 <= len(data["code"]) <= 2048 or not 1 <= len(data["state"]) <= 512):
            raise ValidationError({"proof": gettext("OAuth code and state are required.")})
        try:
            if self.channel == "slack":
                from .notification_slack_oauth import SALT
                from .notification_slack_oauth import read_state
                value = signing.loads(data["state"], salt=SALT, max_age=600)
                if value.get("purpose") == "install":
                    read_state(config, data["state"], purpose="install", user_id=request.user.pk)
                    from .notification_slack import complete_install
                    complete_install(config, data)
                    return self.success()
            raise ValidationError({"proof": gettext("Complete personal linking through the authenticated challenge verify route.")})
        except (ProviderFailure, KeyError, TypeError, ValueError, AttributeError):
            return provider_error()
        except signing.BadSignature:
            raise ValidationError({"proof": gettext("Invalid or expired OAuth state.")}) from None
        return self.success()

    def success(self):
        response = Response({"verified": True})
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response


class ChatInboundView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ChatAnonThrottle]
    channel = ""

    @extend_schema(tags=["Chat notifications"], request=OpenApiTypes.OBJECT, auth=[], parameters=[
        OpenApiParameter("X-Slack-Request-Timestamp", str, OpenApiParameter.HEADER),
        OpenApiParameter("X-Slack-Signature", str, OpenApiParameter.HEADER),
        OpenApiParameter("X-Signature-Timestamp", str, OpenApiParameter.HEADER),
        OpenApiParameter("X-Signature-Ed25519", str, OpenApiParameter.HEADER)],
        responses={200: OpenApiTypes.OBJECT, **errors(400, 403, 404, 429)},
        description="Acknowledge-only callback. Slack v0 HMAC, Mattermost shared token, or Discord Ed25519 required.")
    def post(self, request, makerspace_id):
        config = configuration(makerspace_id, self.channel)
        try:
            creds = config.get_credentials()
        except Exception:
            return provider_error()
        if len(request.body) > 1024 * 1024:
            return Response({"code": "invalid_payload"}, status=400)
        if self.channel == "slack":
            from .notification_slack import signed_request
            valid = signed_request(request, creds.get("signing_secret", ""))
        elif self.channel == "discord":
            from .notification_discord import signed_request
            valid = signed_request(request, creds.get("public_key", ""))
        else:
            from django.utils.crypto import constant_time_compare
            valid = (hasattr(request.data, "get") and bool(creds.get("webhook_token"))
                     and constant_time_compare(creds["webhook_token"], request.data.get("token", "")))
        if not valid:
            return Response({"code": "invalid_signature"}, status=403)
        # Slack and Discord payload parsing happens only after authenticity verification.
        try:
            data = json.loads(request.body) if self.channel == "discord" else request.data
            if not hasattr(data, "get"):
                raise ValueError()
        except (ValueError, UnicodeError):
            return Response({"code": "invalid_payload"}, status=400)
        if self.channel == "slack" and data.get("type") == "url_verification":
            return Response({"challenge": str(data.get("challenge", ""))[:512]})
        if self.channel == "discord":
            return Response({"type": 1} if data.get("type") == 1 else
                            {"type": 4, "data": {"content": "Acknowledged", "flags": 64}})
        return Response({"ok": True})


class SlackInstallStartView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ChatUserThrottle]

    @extend_schema(tags=["Chat notifications"], request=None,
        responses={201: OAuthStartSerializer, **errors(400, 401, 403, 404, 429, 423, 503)})
    def post(self, request, makerspace_id):
        space = contract_space(request.user, makerspace_id, manager=True)
        config = configuration(space.pk, "slack")
        try:
            creds = config.get_credentials()
        except Exception:
            return provider_error()
        if not all(creds.get(key) for key in ("client_id", "client_secret", "signing_secret")):
            raise ValidationError({"channel": gettext("Configure Slack app credentials first.")})
        from .notification_slack_oauth import install_challenge, redirect_uri
        from .notification_slack import install_url
        redirect_uri("slack", config.makerspace_id, 1)
        challenge, code = install_challenge(request.user, config)
        response = Response({"connect_url": install_url(config, challenge, code),
                             "expires_at": challenge.expires_at}, status=201)
        response["Cache-Control"] = "no-store"
        return response


class ChatInstallationView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ChatUserThrottle]
    channel = ""
    serializer_class = None

    @extend_schema(tags=["Chat notifications"], responses={200: InstallationStatusSerializer,
        **errors(400, 401, 403, 404, 429, 423, 503, e403=REAUTH_403)})
    def post(self, request, makerspace_id):
        space = contract_space(request.user, makerspace_id, manager=True)
        # Every installation body carries bot/app secrets.
        require_recent_reauth(request)
        config = configuration(space.pk, self.channel)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            install = install_mattermost if self.channel == "mattermost" else install_discord
            config = install(config, request.user, serializer.validated_data)
        except (ProviderFailure, KeyError, TypeError, ValueError, AttributeError):
            return provider_error()
        return Response({"channel": self.channel, "generation": config.generation, "configured": True})
