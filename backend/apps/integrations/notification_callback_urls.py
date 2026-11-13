"""Installation-derived public ingress URLs. No verifier secret is exposed."""
from django.urls import reverse

from .messaging.resolver import webhook_base, webhook_urls
from .notification_sender import effective_credentials


def callback_urls(config):
    try:
        if config.channel == "sms" and config.provider == "twilio":
            from .notification_sender import sms_sender
            # Setup URLs are useful while a channel is held, too.
            from copy import copy
            candidate = copy(config)
            candidate.activation_hold = False
            sender = sms_sender(candidate)
            if sender is None:
                return {}
            urls = webhook_urls("sms", config.makerspace_id if sender.provider_source == "own" else None)
            return {kind + "_url": url for kind, url in urls.items() if url}
        if config.channel == "whatsapp" and config.provider == "twilio":
            from .notification_wa_twilio_config import callback_url, validate_credentials
            values = validate_credentials(effective_credentials(config))
            return {"inbound_url": callback_url(config, values, "inbound"),
                "status_url_template": callback_url(config, values, "status", 1).removesuffix("1") + "{delivery_id}"}
        if config.channel == "whatsapp" and config.provider == "meta" and webhook_base():
            from .notification_wa_meta_http import credentials
            values = credentials(config)
            if values:
                return {"webhook_url": webhook_base() + reverse("whatsapp-meta-webhook", kwargs={
                    "makerspace_id": config.makerspace_id, "generation": config.generation,
                    "phone_number_id": values["phone_number_id"]})}
    except (ValueError, TypeError, KeyError):
        # An incomplete/unreadable setup cannot advertise a usable ingress.
        pass
    return {}
