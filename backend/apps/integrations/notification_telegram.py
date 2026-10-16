"""Telegram contract provider: generation-bound personal DMs and existing staff rooms."""
import logging
import re

from django.core.cache import cache
from django.db import transaction
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import ValidationError

from .notification_providers import ProviderResult, register_provider
from .notification_telegram_callbacks import callback_event
from .notification_telegram_transport import call, send_text

logger = logging.getLogger(__name__)


class TelegramProvider:
    def __init__(self, configuration):
        self.configuration = configuration

    def _token(self):
        # Explicit credentials make deployment/legacy token changes unable to silently
        # rebind a personal endpoint. ChannelSettingsView rotates generation on writes.
        token = self.configuration.get_credentials().get("bot_token", "")
        return token if isinstance(token, str) else ""

    def start_challenge(self, challenge, code):
        config = self.configuration
        if (challenge.configuration_id != config.pk or challenge.makerspace_id != config.makerspace_id
                or challenge.integration_generation != config.generation
                or challenge.integration_identity != config.integration_identity
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", code)):
            raise ValidationError({"channel": "Telegram verification is no longer current."})
        token = self._token()
        if not token:
            raise ValidationError({"channel": "Configure the Telegram bot token first."})
        fingerprint = salted_hmac("notification.telegram.bot.v1", token, algorithm="sha256").hexdigest()
        key = f"notification:telegram:bot:{config.pk}:{config.generation}:{fingerprint}"
        try:
            username = cache.get(key)
            if username is None:
                # Concurrent starts cannot amplify getMe calls for one installation.
                if not cache.add(key + ":loading", True, timeout=15):
                    raise ValidationError({"channel": "Telegram verification is temporarily unavailable."})
                try:
                    result, bot = call(token, "getMe", {})
                    username = bot.get("username") if result.accepted else None
                    if (not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username)
                            or bot.get("is_bot") is not True or type(bot.get("id")) is not int):
                        raise ValidationError({"channel": "Telegram bot lookup failed. Check the bot token and retry."})
                    cache.set(key, username, timeout=None)
                finally:
                    cache.delete(key + ":loading")
        except ValidationError:
            raise
        except Exception:
            raise ValidationError({"channel": "Telegram verification is temporarily unavailable."}) from None
        return {"connect_url": f"https://t.me/{username}?start={code}"}

    def verify_callback(self, request):
        return callback_event(self.configuration, request)

    def _endpoint_current(self, endpoint):
        from apps.makerspaces.platform import module_enabled
        from apps.makerspaces.servability import is_servable
        from apps.notifications.inbox import eligible_owner
        from .dispatch_channels import channel_module_blocks
        config = self.configuration
        config.refresh_from_db()
        endpoint.refresh_from_db()
        return bool(config.enabled and config.personal_enabled and config.channel == "telegram"
            and module_enabled(config.makerspace, "notifications")
            and not channel_module_blocks(config.makerspace, "telegram")
            and is_servable(config.makerspace) and eligible_owner(config.makerspace, endpoint.user_id)
            and endpoint.configuration_id == config.pk
            and endpoint.makerspace_id == config.makerspace_id and endpoint.channel == "telegram"
            and endpoint.provider == config.provider == "telegram" and endpoint.verification_state == "verified"
            and endpoint.verified_at and endpoint.consented_at and not endpoint.revoked_at
            and endpoint.integration_generation == config.generation
            and endpoint.integration_identity == config.integration_identity
            and re.fullmatch(r"[1-9][0-9]{0,19}", endpoint.destination)
            and endpoint.provider_subject == endpoint.destination)

    def _dm(self, endpoint, text):
        if not self._endpoint_current(endpoint):
            return ProviderResult(False, error_code="invalid_endpoint")
        result = send_text(self._token(), endpoint.destination, text)
        if result.error_code == "invalid_endpoint":
            from apps.tenant_migration.gate_runtime import tenant_write
            from apps.accounts import rbac
            from .models_endpoints import NotificationEndpoint
            from .notification_proofs import revoke
            with tenant_write(endpoint.makerspace_id), transaction.atomic():
                locked = rbac.scope_notification_policy(NotificationEndpoint.objects.select_for_update(),
                    makerspace_id=endpoint.makerspace_id).get(pk=endpoint.pk, configuration=self.configuration)
                if locked.revoked_at is None:
                    revoke(locked, actor=locked.user)
        return result

    def _room(self, target, text):
        from . import telegram
        from .dispatch_channels import channel_module_blocks
        from apps.makerspaces.platform import module_enabled
        config = self.configuration
        config.refresh_from_db()
        if (not config.enabled or not config.room_enabled
                or channel_module_blocks(config.makerspace, "telegram")
                or not module_enabled(config.makerspace, "notifications")):
            return ProviderResult(False, error_code="not_configured")
        if target is not None and (target.makerspace_id != config.makerspace_id
                or target.channel != "telegram" or not target.is_active):
            return ProviderResult(False, error_code="invalid_endpoint")
        try:
            accepted = telegram.send_message(config.makerspace, text, destination=target)
            return ProviderResult(accepted, error_code="" if accepted else "not_configured")
        except telegram.TelegramDeliveryError:
            return ProviderResult(False, retryable=True, error_code="provider_error")

    def send(self, delivery, rendered):
        try:
            if delivery.makerspace_id != self.configuration.makerspace_id:
                return ProviderResult(False, error_code="invalid_endpoint")
            from .models import NotificationDeliveryLog
            if isinstance(delivery, NotificationDeliveryLog):
                if delivery.channel != "telegram" or (delivery.destination_id is None and delivery.destination_label):
                    return ProviderResult(False, error_code="invalid_endpoint")
                return self._room(delivery.destination, rendered.get("text", ""))
            if delivery.endpoint_id:
                endpoint = delivery.endpoint
                if (delivery.integration_generation != self.configuration.generation
                        or delivery.integration_identity != self.configuration.integration_identity
                        or endpoint.user_id != delivery.envelope.recipient_id):
                    return ProviderResult(False, error_code="invalid_endpoint")
                return self._dm(endpoint, rendered.get("text", ""))
            # Even a staff recipient's personal envelope cannot fall through to a room.
            return ProviderResult(False, error_code="invalid_endpoint")
        except Exception as exc:
            logger.warning("telegram_provider_failed", extra={"configuration_id": self.configuration.pk,
                                                              "error_class": type(exc).__name__})
            return ProviderResult(False, retryable=True, error_code="unavailable")

    def test(self, target):
        from .models_endpoints import NotificationEndpoint
        try:
            if isinstance(target, NotificationEndpoint):
                return self._dm(target, "Space Works test alert.")
            return self._room(target, "Space Works test alert.")
        except Exception as exc:
            logger.warning("telegram_provider_test_failed", extra={"configuration_id": self.configuration.pk,
                                                                   "error_class": type(exc).__name__})
            return ProviderResult(False, retryable=True, error_code="unavailable")


def register_telegram_provider():
    register_provider("telegram", "telegram", TelegramProvider)
