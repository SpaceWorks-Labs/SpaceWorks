"""Authenticate first; only private, human /start proofs can mutate an endpoint."""
import logging
import re

from django.conf import settings
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from rest_framework.exceptions import APIException

from apps.tenant_migration.gate_errors import SourceMigrationGateError

from .notification_providers import CallbackEvent, EndpointProof

logger = logging.getLogger(__name__)
START = re.compile(r"/start ([A-Za-z0-9_-]{1,64})", re.ASCII)


def webhook_secret_ok(request):
    secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
    return bool(secret and constant_time_compare(
        request.headers.get("X-Telegram-Bot-Api-Secret-Token", ""), secret,
    ))


def private_start(request):
    if not webhook_secret_ok(request):
        return None
    data = request.data
    if not isinstance(data, dict) or "callback_query" in data:
        return None
    message = data.get("message")
    if not isinstance(message, dict):
        return None
    chat, sender = message.get("chat"), message.get("from")
    if not isinstance(chat, dict) or not isinstance(sender, dict):
        return None
    text = message.get("text")
    match = START.fullmatch(text) if isinstance(text, str) else None
    chat_id, subject = chat.get("id"), sender.get("id")
    if (not match or chat.get("type") != "private" or sender.get("is_bot", False) is not False
            or type(chat_id) is not int or type(subject) is not int
            or chat_id <= 0 or chat_id != subject):
        return None
    # Forwarding another person's start message does not prove their identity.
    if any(key in message for key in ("forward_origin", "forward_from", "forward_sender_name")):
        return None
    return match[1], str(chat_id), str(subject)


def callback_event(configuration, request):
    parsed = private_start(request)
    if parsed is None:
        return None
    code, destination, subject = parsed
    return CallbackEvent(proof=EndpointProof(code, destination,
        configuration.integration_identity, subject, private=True), inbound=True)


def handle_start(request):
    parsed = private_start(request)
    if parsed is None:
        return
    from .models_endpoints import NotificationEndpointChallenge
    from .notification_proofs import digest, verified_callback
    from .dispatch_channels import channel_module_blocks
    from apps.makerspaces.platform import module_enabled
    # The opaque code, never a submitted tenant/account/destination, resolves authority.
    challenge = NotificationEndpointChallenge.objects.select_related("configuration__makerspace").filter(
        code_digest=digest(parsed[0]), configuration__channel="telegram",
        configuration__provider="telegram", consumed_at__isnull=True,
        expires_at__gt=timezone.now(), attempts__lt=5,
    ).first()
    if challenge is None:
        _technician_opt_in(parsed)
        return
    config = challenge.configuration
    try:
        if channel_module_blocks(config.makerspace, "telegram") or not module_enabled(config.makerspace, "notifications"):
            return
        verified_callback(config, request, expected_user_id=challenge.user_id,
                          expected_challenge_id=challenge.pk)
    except (APIException, SourceMigrationGateError):
        # Expired/replayed proofs and closed tenant gates are terminal for this update.
        # Acknowledge so Telegram does not retry it; the browser can start a new challenge.
        logger.info("telegram_endpoint_proof_refused", extra={"configuration_id": config.pk})


def _technician_opt_in(parsed):
    """L16 (#128 C-4): a repair technician's one-time opt-in code records their private chat.

    Same proof bar as an account link: verified secret, private human chat, not forwarded.
    """
    from apps.separability.registry import runtime_active
    if not runtime_active("maintenance"):
        return
    from apps.maintenance.repairs.optin import telegram_start
    try:
        telegram_start(parsed[0], parsed[1])
    except SourceMigrationGateError:
        logger.info("telegram_technician_opt_in_refused")
