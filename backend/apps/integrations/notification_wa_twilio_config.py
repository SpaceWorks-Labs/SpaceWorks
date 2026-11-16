"""Twilio credentials stay in ChannelConfiguration's encrypted credential map."""
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.urls import reverse


class ConfigurationError(ValueError):
    """Static, secret-free configuration failure."""


def sid(value, prefix):
    return isinstance(value, str) and re.fullmatch(prefix + r"[0-9a-fA-F]{32}", value) is not None


def phone(value):
    if not isinstance(value, str):
        raise ConfigurationError("invalid_endpoint")
    value = value.removeprefix("whatsapp:")
    if not re.fullmatch(r"\+[1-9][0-9]{6,14}", value):
        raise ConfigurationError("invalid_endpoint")
    return value


@dataclass(frozen=True, repr=False)
class Credentials:
    account_sid: str
    auth_token: str
    username: str
    password: str
    sender: str
    messaging_service_sid: str
    public_base_url: str


def validate_credentials(values):
    """API keys authenticate REST; the account auth token still signs webhooks."""
    if not isinstance(values, dict) or any(not isinstance(v, str) for v in values.values()):
        raise ConfigurationError("not_configured")
    allowed = {"account_sid", "auth_token", "api_key_sid", "api_key_secret",
               "whatsapp_sender", "messaging_service_sid", "public_base_url"}
    if set(values) - allowed:
        raise ConfigurationError("not_configured")
    account, token = values.get("account_sid", ""), values.get("auth_token", "")
    if not sid(account, "AC") or not re.fullmatch(r"[0-9a-fA-F]{32}", token):
        raise ConfigurationError("not_configured")
    key, secret = values.get("api_key_sid", ""), values.get("api_key_secret", "")
    if (key or secret) and (not sid(key, "SK") or not re.fullmatch(r"[A-Za-z0-9]{32}", secret)):
        raise ConfigurationError("not_configured")
    sender, service = values.get("whatsapp_sender", ""), values.get("messaging_service_sid", "")
    if not sender and not service:
        raise ConfigurationError("not_configured")
    if sender:
        sender = phone(sender)
    if service and not sid(service, "MG"):
        raise ConfigurationError("not_configured")
    base = values.get("public_base_url", "").rstrip("/")
    try:
        url = urlsplit(base)
        valid = (base.isascii() and not any(c.isspace() for c in base)
                 and url.scheme == "https" and url.hostname and not url.username and not url.password
                 and not url.query and not url.fragment and not url.path and url.port != 0)
    except ValueError:
        valid = False
    if not valid:
        raise ConfigurationError("not_configured")
    return Credentials(account, token, key or account, secret or token, sender, service, base)


def callback_path(config, kind, delivery_id=None):
    kwargs = {"makerspace_id": config.makerspace_id, "generation": config.generation}
    if kind == "status":
        kwargs["delivery_id"] = delivery_id
    return reverse(f"whatsapp-twilio-{kind}", kwargs=kwargs)


def callback_url(config, credentials, kind, delivery_id=None):
    return credentials.public_base_url + callback_path(config, kind, delivery_id)
