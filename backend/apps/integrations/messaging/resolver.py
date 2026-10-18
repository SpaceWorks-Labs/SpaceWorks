"""Resolve own credentials first; incomplete/unreadable own senders never fall back."""
import logging
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from django.conf import settings

from apps.integrations.models import MakerspaceMessagingSettings, PlatformSmsSettings, PlatformWhatsAppSettings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedSender:
    channel: str
    sender_key: str
    provider: str
    provider_source: str
    makerspace_id: int | None = None
    account_sid: str = ""
    from_number: str = ""
    phone_number_id: str = ""
    business_account_id: str = ""
    auth_token: str = field(default="", repr=False)
    access_token: str = field(default="", repr=False)
    app_secret: str = field(default="", repr=False)
    verify_token: str = field(default="", repr=False)


def sender_key(channel, *, account_sid="", from_number="", business_account_id="", phone_number_id=""):
    if channel == "sms":
        return f"twilio:{account_sid}:{from_number}" if account_sid and from_number else None
    if channel == "whatsapp":
        return f"meta:{business_account_id}:{phone_number_id}" if business_account_id and phone_number_id else None
    raise ValueError("Unsupported addressed channel.")


def webhook_base():
    value = settings.MESSAGING_WEBHOOK_BASE_URL.rstrip("/")
    try:
        parsed = urlsplit(value)
        parsed.port  # Validate a configured port as well as the host.
        return value if (parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username
                         and not parsed.password and not parsed.query and not parsed.fragment
                         and not any(ord(char) < 32 or ord(char) == 127 for char in value)) else ""
    except ValueError:
        return ""


def resolve_sender(makerspace, channel):
    if channel not in ("sms", "whatsapp"):
        raise ValueError("Unsupported addressed channel.")
    if not webhook_base():
        return None
    own = MakerspaceMessagingSettings.objects.filter(makerspace=makerspace).first() if makerspace else None
    prefix = "sms_" if channel == "sms" else "whatsapp_"
    configured = bool(own and any(getattr(own, prefix + name) for name in (
        ("account_sid", "auth_token", "from_number") if channel == "sms" else
        ("phone_number_id", "business_account_id", "access_token", "app_secret")
    )))
    if not configured and own and not own.use_platform_sender:
        return None
    row = own if configured else (
        PlatformSmsSettings.objects.filter(pk=1).first() if channel == "sms" else
        PlatformWhatsAppSettings.objects.filter(pk=1).first()
    )
    if row is None:
        return None
    if not configured and not (row.notifications_enabled if channel == "sms" else row.is_enabled):
        return None
    try:
        source, tenant_id = ("own", makerspace.pk) if configured else ("platform", None)
        if channel == "sms":
            sid = row.sms_account_sid if configured else row.account_sid
            number = row.sms_from_number if configured else row.notifications_from_number
            token = row.get_secret("sms_auth_token") if configured else row.get_auth_token()
            otp = PlatformSmsSettings.objects.filter(pk=1).first()
            if otp and ((configured and sid == otp.account_sid and sid) or (number == otp.from_number and number)):
                return None
            key = sender_key(channel, account_sid=sid, from_number=number)
            return ResolvedSender(channel, key, "twilio", source, tenant_id, account_sid=sid,
                                  from_number=number, auth_token=token) if key and token else None
        phone = row.whatsapp_phone_number_id if configured else row.phone_number_id
        business = row.whatsapp_business_account_id if configured else row.business_account_id
        token = row.get_secret("whatsapp_access_token" if configured else "access_token")
        secret = row.get_secret("whatsapp_app_secret" if configured else "app_secret")
        verify = row.whatsapp_webhook_verify_token if configured else row.webhook_verify_token
        key = sender_key(channel, business_account_id=business, phone_number_id=phone)
        return ResolvedSender(channel, key, "meta", source, tenant_id, phone_number_id=phone,
                              business_account_id=business, access_token=token,
                              app_secret=secret, verify_token=verify) if key and token and secret and verify else None
    except Exception:
        logger.warning("messaging_sender_unreadable", extra={"channel": channel, "makerspace_id": getattr(makerspace, "pk", None)})
        return None


def webhook_urls(channel, makerspace_id=None):
    owner = f"m/{makerspace_id}" if makerspace_id is not None else "platform"
    configured = webhook_base()
    if not configured:
        return {kind: "" for kind in (("status", "inbound") if channel == "sms" else ("callback",))}
    base = configured + "/api/v1/integrations/messaging/"
    if channel == "sms":
        return {kind: f"{base}twilio/{owner}/{kind}#rc=5&rp=5xx,ct,rt" for kind in ("status", "inbound")}
    return {"callback": f"{base}whatsapp/{owner}"}
