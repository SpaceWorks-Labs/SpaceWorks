"""Personal WhatsApp adapter. Import/registration never reads DB or contacts Twilio."""
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .notification_providers import ProviderResult, register_provider
from .notification_wa_twilio_config import ConfigurationError, callback_url, phone, validate_credentials
from .notification_wa_twilio_http import send_message
from .notification_wa_twilio_templates import template_payload
from .notification_wa_window import in_session_window


class TwilioWhatsAppProvider:
    def __init__(self, configuration):
        self.configuration = configuration

    def credentials(self):
        try:
            return validate_credentials(self.configuration.get_credentials())
        except Exception:
            raise ConfigurationError("not_configured") from None

    def active(self):
        from apps.makerspaces.platform import module_enabled
        from apps.makerspaces.servability import is_servable
        config = self.configuration
        return (config.channel == "whatsapp" and config.provider == "twilio" and config.enabled
                and config.personal_enabled and bool(config.integration_identity)
                and is_servable(config.makerspace) and module_enabled(config.makerspace, "notifications"))

    def valid_endpoint(self, endpoint):
        config = self.configuration
        from .models_endpoints import NotificationEndpoint
        from apps.notifications.inbox import eligible_owner
        return bool(isinstance(endpoint, NotificationEndpoint) and endpoint.configuration_id == config.pk
            and endpoint.makerspace_id == config.makerspace_id and endpoint.channel == "whatsapp"
            and endpoint.provider == "twilio" and endpoint.integration_generation == config.generation
            and endpoint.integration_identity == config.integration_identity
            and endpoint.verification_state == "verified" and endpoint.verified_at
            and endpoint.consented_at and not endpoint.revoked_at
            and eligible_owner(config.makerspace, endpoint.user_id))

    def _send(self, destination, payload, delivery_id=None):
        try:
            credentials = self.credentials()
            payload = {**payload, "To": "whatsapp:" + phone(destination)}
            if credentials.messaging_service_sid:
                payload["MessagingServiceSid"] = credentials.messaging_service_sid
            if credentials.sender:
                payload["From"] = "whatsapp:" + credentials.sender
            if delivery_id is not None:
                payload["StatusCallback"] = callback_url(self.configuration, credentials, "status", delivery_id)
            return send_message(credentials, payload)
        except ConfigurationError as exc:
            return ProviderResult(False, error_code=str(exc), sanitized_error=str(exc))

    def send(self, delivery, rendered):
        config = self.configuration
        endpoint = delivery.endpoint
        if (not self.active() or not self.valid_endpoint(endpoint)
                or delivery.makerspace_id != config.makerspace_id or delivery.channel != "whatsapp"
                or delivery.provider != "twilio" or delivery.integration_generation != config.generation
                or delivery.integration_identity != config.integration_identity
                or delivery.envelope.makerspace_id != config.makerspace_id
                or delivery.envelope.recipient_id != endpoint.user_id):
            return ProviderResult(False, error_code="invalid_endpoint")
        if in_session_window(endpoint):
            body = rendered.get("text", "")
            if not isinstance(body, str) or not body.strip() or len(body) > 4096:
                return ProviderResult(False, error_code="provider_error")
            payload = {"Body": body}
        else:
            envelope = delivery.envelope
            payload = template_payload(config, envelope.event, envelope.audience,
                envelope.context.get("locale", "en"), envelope.context)
            if payload is None:
                return ProviderResult(False, error_code="template_required")
        return self._send(endpoint.destination, payload, delivery.pk)

    def send_document(self, delivery, *, filename, pdf_bytes, caption):
        from .notification_wa_documents import twilio_document
        return twilio_document(self, delivery, filename=filename, pdf_bytes=pdf_bytes, caption=caption)

    def verify_callback(self, request):
        from .notification_wa_twilio_callbacks import verify_callback
        try:
            return verify_callback(self.configuration, self.credentials(), request)
        except ConfigurationError:
            return None

    def start_challenge(self, challenge, code):
        config = self.configuration
        if (not self.active() or challenge.configuration_id != config.pk
                or challenge.makerspace_id != config.makerspace_id
                or challenge.integration_generation != config.generation
                or challenge.integration_identity != config.integration_identity
                or challenge.consumed_at or challenge.expires_at <= timezone.now()):
            raise ValidationError({"channel": "Account linking is unavailable."})
        payload = template_payload(config, "notification_opt_in", "member", "en", {"code": code})
        import json
        if (payload is None or code not in json.loads(payload["ContentVariables"]).values()
                or not self._send(challenge.candidate_destination, payload).accepted):
            raise ValidationError({"channel": "The opt-in template could not be sent."})
        return {"instructions": "Reply to the WhatsApp business sender with the verification code to connect."}

    def test(self, target):
        if not self.active() or not self.valid_endpoint(target):
            return ProviderResult(False, error_code="invalid_endpoint")
        payload = template_payload(self.configuration, "notification_test", "member", "en", {})
        if payload is None:
            return ProviderResult(False, error_code="template_required")
        return self._send(target.destination, payload)


def register():
    register_provider("whatsapp", "twilio", TwilioWhatsAppProvider)
