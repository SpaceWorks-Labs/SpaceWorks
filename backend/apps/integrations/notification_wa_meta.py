"""Meta WhatsApp Cloud adapter registered through the frozen provider factory seam."""
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

from .notification_providers import register_provider
from .notification_wa_meta_http import PHONE, credentials, failure, send_message
from .notification_wa_meta_templates import bound_template, sync_templates, template_content
from .notification_wa_window import in_session_window
from .notification_wa_meta_reference import client_reference


class MetaWhatsAppProvider:
    def __init__(self, configuration):
        self.configuration = configuration

    def _ready(self):
        from apps.makerspaces.platform import module_enabled
        from apps.makerspaces.servability import is_servable
        config = self.configuration
        return bool(config.channel == "whatsapp" and config.provider == "meta"
                    and config.enabled and config.personal_enabled
                    and is_servable(config.makerspace)
                    and module_enabled(config.makerspace, "notifications")
                    and config.integration_identity and credentials(config))

    def _endpoint_valid(self, endpoint):
        config = self.configuration
        return bool(endpoint and getattr(endpoint, "configuration_id", None) == config.pk
            and endpoint.makerspace_id == config.makerspace_id and endpoint.channel == "whatsapp"
            and endpoint.provider == "meta" and endpoint.integration_generation == config.generation
            and endpoint.integration_identity == config.integration_identity
            and endpoint.verification_state == "verified" and endpoint.verified_at
            and endpoint.consented_at and not endpoint.revoked_at)

    def send(self, delivery, rendered):
        if not self._ready():
            return failure("not_configured")
        endpoint, config = delivery.endpoint, self.configuration
        if (not self._endpoint_valid(endpoint) or delivery.makerspace_id != config.makerspace_id
                or delivery.integration_generation != config.generation
                or delivery.integration_identity != config.integration_identity
                or not isinstance(endpoint.destination, str) or not PHONE.fullmatch(endpoint.destination)):
            return failure("invalid_endpoint")
        envelope = delivery.envelope
        if envelope.recipient_id != endpoint.user_id or envelope.makerspace_id != config.makerspace_id:
            return failure("invalid_endpoint")
        return self._send(endpoint, envelope.event, envelope.audience, envelope.context,
                          rendered.get("text", ""), reference=client_reference(config, delivery))

    def _send(self, endpoint, event, audience, context, text, *, reference=""):
        if not self._live_target(endpoint):
            return failure("invalid_endpoint")
        if in_session_window(endpoint):
            if not isinstance(text, str) or not text or len(text) > 4096:
                return failure("provider_error")
            content = {"type": "text", "text": {"body": text, "preview_url": False}}
        else:
            approval = sync_templates(self.configuration)
            if not approval.accepted:
                return approval
            # Approval I/O can take seconds: a withdrawal/rotation during it wins.
            if not self._live_target(endpoint):
                return failure("invalid_endpoint")
            binding = bound_template(self.configuration, event, audience, context.get("locale", "en"))
            content = template_content(binding, context)
            if content is None:
                return failure("template_required")
        if reference:
            content["biz_opaque_callback_data"] = reference
        return send_message(self.configuration, endpoint.destination, content)

    def _live_target(self, endpoint):
        from apps.notifications.inbox import eligible_owner
        config = self.configuration
        generation, identity = config.generation, config.integration_identity
        try:
            config.refresh_from_db()
            endpoint.refresh_from_db()
        except ObjectDoesNotExist:
            return False
        return bool(config.generation == generation and config.integration_identity == identity
            and self._ready() and self._endpoint_valid(endpoint)
            and eligible_owner(config.makerspace, endpoint.user_id))

    def verify_callback(self, request):
        from .notification_wa_meta_callbacks import callback_event
        return callback_event(self.configuration, request)

    def start_challenge(self, challenge, code):
        config = self.configuration
        if (not self._ready() or challenge.configuration_id != config.pk
                or challenge.makerspace_id != config.makerspace_id
                or challenge.integration_generation != config.generation
                or challenge.integration_identity != config.integration_identity
                or challenge.consumed_at or challenge.expires_at <= timezone.now()):
            raise ValueError("not_configured")
        # No candidate: the user sends the code to the business number themselves.
        if not challenge.candidate_destination:
            return {"instructions": f"Message the business WhatsApp number with: {code}"}
        approval = sync_templates(config)
        if not approval.accepted:
            raise ValueError(approval.error_code)
        generation, identity = config.generation, config.integration_identity
        config.refresh_from_db()
        challenge.refresh_from_db()
        if (config.generation != generation or config.integration_identity != identity
                or not self._ready() or challenge.integration_generation != config.generation
                or challenge.integration_identity != config.integration_identity
                or challenge.consumed_at or challenge.expires_at <= timezone.now()):
            raise ValueError("not_configured")
        binding = bound_template(config, "notification_opt_in", "member")
        content = template_content(binding, {"code": code})
        if content is None or binding.variables != ["code"]:
            raise ValueError("template_required")
        result = send_message(config, challenge.candidate_destination, content)
        if not result.accepted:
            raise ValueError(result.error_code)
        return {"instructions": "Reply to the business WhatsApp number with the code to confirm consent."}

    def test(self, target):
        if not self._ready():
            return failure("not_configured")
        if not self._endpoint_valid(target):
            return failure("invalid_endpoint")
        if in_session_window(target):
            result = sync_templates(self.configuration)
            if not result.accepted:
                return result
        return self._send(target, "notification_test", "member", {}, "Space Works WhatsApp delivery test.")


def register_meta_provider():
    """Call from IntegrationsConfig.ready(); query-free and idempotent."""
    register_provider("whatsapp", "meta", MetaWhatsAppProvider)
