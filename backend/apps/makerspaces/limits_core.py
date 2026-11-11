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
        "guest_passes",
        "upload_bytes",
    }
)
# Per-file caps, not counters: nothing is "used" up. `upload_bytes` bounds ONE uploaded object
# (bytes) and is enforced by `limits_uploads` at presign (declared size) and at finalize (real size).
# There is deliberately no analytics-view key (#234 addendum 2): nothing server-side counts views.
# Metabase dashboards are embedded by a short-lived signed URL per request and web page views go
# straight to the space's own telemetry provider, so a cap would first need a new counter table.
CAP_LIMIT_KEYS = frozenset({"upload_bytes"})
BOOLEAN_LIMIT_KEYS = frozenset({"custom_domain"})
# Owner 2026-11-11: monthly usage of the PLATFORM credentials, per space (own or hosted), unlimited
# unless the superadmin sets a value in `resource_limit_overrides`. Deliberately NOT in
# NUMERIC_LIMIT_KEYS: `resource_limit` exempts own spaces and these must not be. See
# `managed_hosting/platform_limits.py`.
PLATFORM_CREDENTIAL_LIMIT_KEYS = frozenset({
    "platform_email_monthly", "platform_sms_monthly", "platform_whatsapp_monthly", "platform_push_monthly",
    "platform_wallet_monthly", "platform_payments_monthly_count", "platform_payments_monthly_amount",
})
# Owner 2026-11-11: monthly quotas on ANY space (see `managed_hosting/space_quotas.py`), superadmin-set, default none.
SPACE_QUOTA_LIMIT_KEYS = frozenset({"events_monthly", "bookings_monthly", "payments_monthly_count",
                                    "payments_monthly_amount"})
# Owner 2026-11-11 (decision 284 addendum): every other countable per-space resource. Superadmin-set, default
# none, any space; specs, counters and typed 409s live in `managed_hosting/extra_quotas.py`.
EXTRA_QUOTA_LIMIT_KEYS = frozenset({
    "event_registrations_monthly", "shop_orders_monthly", "shop_products", "membership_plans",
    "donation_campaigns", "bookable_spaces", "boxes", "organizations_linked", "api_requests_per_minute",
    "analytics_connections", "report_exports_monthly", "kiosk_stations", "devices", "machine_jobs_monthly",
    "machine_sessions_monthly", "storage_evidence_bytes", "storage_public_images_bytes", "webhook_endpoints",
    "member_cards_issued_monthly", "wallet_passes", "member_units", "collection_sheet_rows_monthly", "staff_cards_issued_monthly",
    "series_invites", "checkin_lists", "saved_views", "hackathon_stages", "event_badge_prints_monthly",
})
KNOWN_LIMIT_KEYS = (NUMERIC_LIMIT_KEYS | BOOLEAN_LIMIT_KEYS | PLATFORM_CREDENTIAL_LIMIT_KEYS
                    | SPACE_QUOTA_LIMIT_KEYS | EXTRA_QUOTA_LIMIT_KEYS)
# One vocabulary (#77): the per-space keys above are unlimited unless the superadmin sets them on
# a HOSTED space's plan or override (#236); MANAGED_RESOURCE_LIMITS only suggests values. These
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
    "guest_passes": "guest and day passes issued per day",
    "upload_bytes": "largest single upload",
    "custom_domain": "custom domains",
}


def resource_limit(makerspace, key) -> int | None:
    """Return the effective limit; ``None`` means unlimited.

    Decision 236 + addendum: an OWN space (or any space while hosting is off) is unlimited; for
    a HOSTED space the order is override > plan > unlimited. ``MANAGED_RESOURCE_LIMITS`` is only
    a suggestion the console shows next to an empty field (``suggested_limit``), never enforced.
    """
    from apps.makerspaces import limits

    # Owner 2026-11-11 (decision 281 addendum): a limit the superadmin SET on a space applies to that
    # space whether it is own or hosted. Plans and built-in values stay hosted-only (decision 236);
    # nothing is stored by default, so nothing is enforced by default.
    overrides = makerspace.resource_limit_overrides or {}
    if key in overrides:
        value = overrides[key]
        if value is None or isinstance(value, bool) or value == -1:
            return None
        return int(value)
    if limits.is_self_host():
        return None
    from apps.managed_hosting.hosting_type import is_hosted

    if not is_hosted(makerspace):
        return None
    from apps.managed_hosting.enforcement import NOT_SET, plan_limit

    planned = plan_limit(makerspace, key)
    return None if planned is NOT_SET else planned


def suggested_limit(key) -> int | None:
    """The built-in fair-use value, shown as "Suggested: N" next to an empty limit (#236 addendum)."""
    return settings.MANAGED_RESOURCE_LIMITS.get(key)
