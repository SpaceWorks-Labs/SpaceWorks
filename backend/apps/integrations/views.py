from django.utils.translation import gettext
from .notification_cutover import guarded, sending_allowed, CutoverClosed
import logging

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.audit import services as audit
from apps.accounts.models import User
from apps.integrations.serializers import (
    TelegramTestAlertSerializer,
    TelegramWebhookSerializer,
)
from apps.integrations.telegram import TelegramDeliveryError, send_message
from .notification_telegram_callbacks import handle_start, webhook_secret_ok
from apps.makerspaces.models import Makerspace
from apps.makerspaces.guards import require_module
from apps.openapi_errors import errors

logger = logging.getLogger(__name__)


class TelegramWebhookView(APIView):
    """Verify private account-link proofs; acknowledge and discard all decisions.

    Telegram is a notification channel, not an action surface: every `callback_query`
    is acknowledged and discarded and nothing here reaches the request workflow. The
    route is kept because a deployment that already called `setWebhook` would otherwise
    have Telegram retry a 404 for hours. The only state it may change is a personal
    endpoint link from a private `/start <code>` message, and only after the secret
    header has been verified -- `from.id` in the payload is attacker-controllable.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "telegram_webhook"

    @extend_schema(
        tags=["Telegram"],
        summary="Verify a private Telegram account link or acknowledge an ignored update",
        description=(
            "Requires X-Telegram-Bot-Api-Secret-Token. Only /start <code> in a private "
            "chat can consume an account/tenant/integration-bound connection challenge. "
            "Invalid, expired or replayed codes are acknowledged without linking. Every "
            "callback_query and other update is discarded; decisions stay in the console."
        ),
        auth=[],
        request=TelegramWebhookSerializer,
        responses={
            200: OpenApiResponse(description="Acknowledged; eligible private proof consumed, otherwise ignored."),
            **errors(
                400, 403, 429,
                e403="TELEGRAM_WEBHOOK_SECRET is unset, or the secret-token header is wrong.",
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        if not _webhook_secret_ok(request):
            return Response({"detail": gettext("Invalid webhook secret.")}, status=403)
        serializer = TelegramWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if "callback_query" in request.data:
            logger.info(
                "Telegram callback ignored; chat is not an action surface.",
                extra={"has_callback": True},
            )
        else:
            handle_start(request)
        return Response({"detail": gettext("Ignored.")})


class TelegramTestAlertView(APIView):
    @extend_schema(
        tags=["Telegram"],
        summary="Send Telegram test alert",
        request=TelegramTestAlertSerializer,
        responses={
            200: OpenApiResponse(
                inline_serializer("TelegramTestAlertResult", fields={
                    "delivered": serializers.BooleanField(),
                    "detail": serializers.CharField(required=False),
                }),
                description="Delivery attempt result; `delivered: false` with a reason when "
                "Telegram is unconfigured or rejects the message."
            ),
            **errors(400, 401, 403, 404, 503),
        },
    )
    @guarded(mutation=True)
    def post(self, request, *args, **kwargs):
        if not sending_allowed():
            raise CutoverClosed()
        serializer = TelegramTestAlertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        makerspace = get_object_or_404(
            Makerspace,
            pk=serializer.validated_data["makerspace_id"],
        )
        require_module(makerspace, "telegram")
        from rest_framework.exceptions import PermissionDenied

        # rbac.can checks membership/action only; gate access_status too so a
        # suspended/restricted staffer with a live JWT can't still send alerts.
        if request.user.access_status != User.AccessStatus.ACTIVE:
            raise PermissionDenied()
        if not rbac.can(request.user, rbac.Action.MANAGE_MAKERSPACE, makerspace.id):
            raise PermissionDenied()
        # send_message returns False only when the makerspace has no token/chat_id
        # configured; a real Telegram failure (bad token, bot not in the group,
        # network) RAISES TelegramDeliveryError. Catch it here so the staff console
        # gets a clear {delivered:false, detail} instead of an opaque 500 — the test
        # alert is a diagnostic, so a delivery failure is an expected outcome, not a
        # server error.
        # A test send reaches a real group chat, so it is audited like DeliveryTestView's.
        audit.record(request.user, "telegram.test_sent", makerspace=makerspace, target=makerspace)
        try:
            delivered = send_message(makerspace, serializer.validated_data["message"])
        except TelegramDeliveryError:
            return Response(
                {
                    "delivered": False,
                    "detail": (
                        gettext("Telegram rejected the message. Check the bot token is correct "
                        "and the bot has been added to the group chat.")
                    ),
                }
            )
        if not delivered:
            return Response(
                {
                    "delivered": False,
                    "detail": gettext("Telegram is not configured — save a bot token and group chat ID first."),
                }
            )
        return Response({"delivered": True})


def _webhook_secret_ok(request):
    return webhook_secret_ok(request)
