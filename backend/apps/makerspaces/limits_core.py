from django.conf import settings


NUMERIC_LIMIT_KEYS = frozenset(
    {
        "products",
        "assets",
        "machines",
        "events",
        "bookings",
        "staff",
        "members",
        "storage",
        "print",
        "email",
        "telegram",
        "slack",
        "mattermost",
        "discord",
        "webhook",
        "native_push",
        "sms",
        "whatsapp",
        "api_clients",
        "machine_service_open",
        "machine_service_submit",
        "data_exports",
    }
)
BOOLEAN_LIMIT_KEYS = frozenset({"custom_domain"})
KNOWN_LIMIT_KEYS = NUMERIC_LIMIT_KEYS | BOOLEAN_LIMIT_KEYS
# One vocabulary (#77): the per-space keys above are each defaulted in
# MANAGED_RESOURCE_LIMITS and overridable per space (`resource_limit_overrides`); these
# two are platform-wide daily counters, defaulted there and overridable per deployment
# (MANAGED_OTP_EMAIL_DAILY_LIMIT / MANAGED_OTP_SMS_DAILY_LIMIT). `custom_domain` is the
# one boolean key and defaults to allowed.
PLATFORM_LIMIT_KEYS = frozenset({"otp_email", "otp_sms"})

RESOURCE_LABELS = {
    "products": "products",
    "assets": "assets",
    "machines": "machines",
    "events": "events",
    "bookings": "active bookings",
    "staff": "staff members",
    "members": "members",
    "storage": "storage",
    "print": "monthly print requests",
    "email": "daily emails",
    "telegram": "daily Telegram notifications",
    "slack": "daily Slack notifications",
    "mattermost": "daily Mattermost notifications",
    "discord": "daily Discord notifications",
    "webhook": "daily signed webhook deliveries",
    "native_push": "daily native push notifications",
    "sms": "daily SMS notifications",
    "whatsapp": "daily WhatsApp notifications",
    "api_clients": "API clients",
    "machine_service_open": "open machine service requests",
    "machine_service_submit": "daily machine service requests",
    "data_exports": "active data exports",
    "custom_domain": "custom domains",
}


def resource_limit(makerspace, key) -> int | None:
    """Return the effective managed limit; ``None`` means unlimited."""
    from apps.makerspaces import limits

    if limits.is_self_host():
        return None
    overrides = makerspace.resource_limit_overrides or {}
    if key in overrides:
        value = overrides[key]
        if value is None or value == -1:
            return None
        return int(value)
    return settings.MANAGED_RESOURCE_LIMITS.get(key)
