"""Compose Django settings in the original deployment initialization order."""

def _publish(section):
    # Django reads uppercase names from config.settings. Publish each section as it
    # loads so later sections and the deployment overlays see the same values.
    globals().update((name, value) for name, value in vars(section).items() if name.isupper())


from config import settings_runtime as _runtime
from config.settings_runtime import (
    ImproperlyConfigured, _deployment, crontab, env, normalize_platform_domain_suffix,
)
_publish(_runtime)

from config import settings_django as _django
_publish(_django)

from config import settings_storage as _storage
_publish(_storage)

from config import settings_delivery as _delivery
from config.settings_delivery import cache_config
_publish(_delivery)

from config import settings_recovery as _recovery
_publish(_recovery)

from config import settings_beat as _beat
_publish(_beat)

from config import settings_beat_extensions as _beat_extensions
_publish(_beat_extensions)

from config import settings_credentials as _credentials
_publish(_credentials)

from config import settings_drf as _drf
_publish(_drf)

from config import settings_http as _http
_publish(_http)

from config import settings_schema as _schema
_publish(_schema)

from config import settings_observability as _observability
_publish(_observability)

# Addressed notifications require an operator-owned absolute callback origin.
MESSAGING_WEBHOOK_BASE_URL = env("MESSAGING_WEBHOOK_BASE_URL", default="").rstrip("/")

CELERY_BEAT_SCHEDULE["messaging-recovery"] = {
    "task": "apps.integrations.tasks_messaging.sweep_messaging_task", "schedule": 300.0,
}
# Bounded canonical addressed-leg and processed-receipt retention (docs/INVARIANTS.md).
CELERY_BEAT_SCHEDULE["canonical-messaging-retention"] = {
    "task": "apps.integrations.tasks_messaging.canonical_retention_task", "schedule": crontab(minute=35),
}
# Applied after legacy settings so host/full with no explicit task selector is
# byte-for-byte equivalent in effective values. No free knobs are read under full.
from config.cloud_settings.tasks import task_settings
try:
    _cloud_tasks = task_settings(
        env, _deployment, profile=CLOUD_TASK_PROFILE, scheduler=CLOUD_SCHEDULER,
    )
    CLOUD_TASK_PROFILE = _cloud_tasks.get("CLOUD_TASK_PROFILE", "")
    CLOUD_SCHEDULER = _cloud_tasks.get("CLOUD_SCHEDULER", "")
    if _cloud_tasks:
        CELERY_BROKER_URL = _cloud_tasks["CELERY_BROKER_URL"]
        CELERY_TASK_ALWAYS_EAGER = _cloud_tasks["CELERY_TASK_ALWAYS_EAGER"]
        CELERY_RESULT_BACKEND = _cloud_tasks["CELERY_RESULT_BACKEND"]
        LIVE_REDIS_URL = _cloud_tasks["LIVE_REDIS_URL"]
        CACHES = {"default": cache_config(_cloud_tasks["CACHE_URL"])}
    if _deployment.is_free:
        from config.cloud_settings.free import free_settings
        globals().update(free_settings({
            "FREE_TICK_SECRET": env("FREE_TICK_SECRET", default=""),
            "FREE_TICK_INTERVAL_SECONDS": env.int("FREE_TICK_INTERVAL_SECONDS", default=600),
            "FREE_TICK_BUDGET_SECONDS": env.int("FREE_TICK_BUDGET_SECONDS", default=20),
            "FREE_TICK_RATE_LIMIT_PER_MINUTE": env.int("FREE_TICK_RATE_LIMIT_PER_MINUTE", default=6),
            "FREE_DB_CAP_BYTES": env.int("FREE_DB_CAP_BYTES", default=None),
            "FREE_OBJECT_CAP_BYTES": env.int("FREE_OBJECT_CAP_BYTES", default=None),
            "FREE_EMAIL_DAILY_CAP": env.int("FREE_EMAIL_DAILY_CAP", default=None),
        }))
        # Free ticks use J's typed catalog, never Celery beat or its whole sweeps.
        CELERY_BEAT_SCHEDULE = {}
except ValueError as exc:
    raise ImproperlyConfigured(str(exc)) from exc

if SPACEWORKS_DEPLOYMENT_MODE == "managed" or CLOUD_TASK_PROFILE:
    from config.cloud_settings.wiring import cloud_task_modules
    CELERY_IMPORTS = cloud_task_modules(tombstones=TOMBSTONED_APPS)

from config.cloud_settings.configuration import deployment_settings
globals().update(deployment_settings(env, _deployment))
if CLOUD_PROGRAMMES:
    from apps.operations.cloud_jobs.catalog import assert_no_programme_overlap
    assert_no_programme_overlap(CLOUD_PROGRAMMES, CELERY_BEAT_SCHEDULE, SPACEWORKS_DEPLOYMENT_MODE)
if SPACEWORKS_DEPLOYMENT_MODE == "managed" and not _deployment.is_free:
    from apps.operations.cloud_jobs.catalog import beat_entries
    # Preserve legacy calendar slots; new reviewed tasks alone acquire intervals.
    for _name, _entry in beat_entries().items():
        CELERY_BEAT_SCHEDULE.setdefault(_name, _entry)
    if CLOUD_SCHEDULER == "beat":
        CELERY_BEAT_SCHEDULER = "apps.operations.cloud_jobs.beat.DatabaseScheduler"
if SPACEWORKS_DEPLOYMENT_MODE == "host":
    # Preserve PersistentScheduler's file/calendar behavior, while exposing real
    # dispatcher contact to the existing installer completion probe (C17).
    CELERY_BEAT_SCHEDULER = "apps.operations.cloud_jobs.host_beat.ObservedPersistentScheduler"

# --- lane L5 (release 2): payer-facing throttles for offline claims and pay links.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({
    "payment_claims": env("THROTTLE_PAYMENT_CLAIMS", default="5/hour"),
    "pay_links": env("THROTTLE_PAY_LINKS", default="30/min"),
})
# --- end lane L5

# --- lane L15 (release 2): the price preview, per account or per IP when signed out.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({
    "pricing_quote": env("THROTTLE_PRICING_QUOTE", default="60/min"),
})
# Stable names for the pricing enums instead of hash-suffixed collision names.
SPECTACULAR_SETTINGS["ENUM_NAME_OVERRIDES"].update({
    "PricingDomainEnum": "apps.payments.models_pricing.PricingDomain.choices",
    "PricingModeEnum": [("free", "Free"), ("paid", "Paid")],
    "PriceOverrideModeEnum": [("inherit", "Use the space default"), ("free", "Free"), ("custom", "Custom price")],
})
# --- end lane L15
# --- Release 2 / S-C: IP blocking, Turnstile and breached passwords (#62, #66) ----------
# The middleware, validator, axes and beat lines sit beside their neighbours above.
# Sign-in routes document 429 ip_blocked, 400 captcha_required/captcha_failed and
# password_breached without each view repeating them.
SPECTACULAR_SETTINGS["POSTPROCESSING_HOOKS"] = [
    *SPECTACULAR_SETTINGS.get("POSTPROCESSING_HOOKS", ["drf_spectacular.hooks.postprocess_schema_enums"]),
    "apps.accounts.ip_guard_schema.document_login_guard_errors",
]
# --- end S-C ---------------------------------------------------------------------------

# --- lane L3 (release 2): card verify, scan and join throttles; the card font library;
# photo clean-up model; platform wallet-pass credentials (Q-I11, superadmin/operator only).
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({
    "card_verify": env("THROTTLE_CARD_VERIFY", default="30/min"),
    "member_card_resolve": env("THROTTLE_MEMBER_CARD_RESOLVE", default="60/min"),
    "id_join": env("THROTTLE_ID_JOIN", default="10/min"),
    "id_join_upload": env("THROTTLE_ID_JOIN_UPLOAD", default="12/hour"),
    # Staff sheet previews render up to one sheet in the request (r2-idcards-best); fixed, not tunable.
    "card_render": "120/hour",
})
CARD_FONT_DOWNLOADS_ENABLED = env.bool("CARD_FONT_DOWNLOADS_ENABLED", default=True)
CARD_FONT_SOURCE_URL = env("CARD_FONT_SOURCE_URL", default="https://fonts.googleapis.com/css2")
CARD_FONT_CACHE_DIR = env("CARD_FONT_CACHE_DIR", default="")
CARD_PHOTO_MODEL_PATH = env("CARD_PHOTO_MODEL_PATH", default="")
WALLET_APPLE_PASS_TYPE_ID = env("WALLET_APPLE_PASS_TYPE_ID", default="")
WALLET_APPLE_TEAM_ID = env("WALLET_APPLE_TEAM_ID", default="")
WALLET_APPLE_CERT_FILE = env("WALLET_APPLE_CERT_FILE", default="")
WALLET_APPLE_KEY_FILE = env("WALLET_APPLE_KEY_FILE", default="")
WALLET_APPLE_WWDR_FILE = env("WALLET_APPLE_WWDR_FILE", default="")
WALLET_GOOGLE_ISSUER_ID = env("WALLET_GOOGLE_ISSUER_ID", default="")
WALLET_GOOGLE_SERVICE_ACCOUNT_FILE = env("WALLET_GOOGLE_SERVICE_ACCOUNT_FILE", default="")
# --- end lane L3

# --- lane L13 (release 2): the import-source enum (upload or public Google Sheet) gets one stable name.
SPECTACULAR_SETTINGS["ENUM_NAME_OVERRIDES"].update({
    "ImportSourceKindEnum": [("file", "file"), ("google_sheet", "google_sheet")],
})
# --- end lane L13
# --- lane L6 (release 2): a stable name for the ticket type's pricing mode, so it never
# takes over L15's rate-card PricingModeEnum (free | paid) in the OpenAPI schema.
SPECTACULAR_SETTINGS["ENUM_NAME_OVERRIDES"].update({
    "TicketPricingModeEnum": [("fixed", "Fixed price"), ("pwyw", "Pay what you want")],
})
# The member ticket-order budget (quote, place, attendees, chase, cancel, claim), per account.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({
    "event_orders": "60/hour",
})
# --- end lane L6

# --- lane L22 (release 2): stable OpenAPI names for the shop's choice sets.
SPECTACULAR_SETTINGS["ENUM_NAME_OVERRIDES"].update({
    "ShopProductKindEnum": "apps.shop.models_catalogue.ShopProduct.Kind",
    "ShopOrderStatusEnum": "apps.shop.models_orders.ShopOrder.Status",
    "ShopStockMovementKindEnum": "apps.shop.models_stock.ShopStockMovement.Kind",
    "ShopStockMoveKindEnum": [("restock", "restock"), ("count", "count"), ("damage", "damage"),
                              ("internal_use", "internal_use")],
    "ShopCashSessionStatusEnum": "apps.shop.models_pos.ShopCashSession.Status",
})
# The public shop's order and guest email-code budgets, per client/IP.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({
    "shop_orders": "30/hour",
    "shop_codes": "10/hour",
})
# --- end lane L22

# --- lane r2-platform-overview (#183A): stable OpenAPI names for the overview's metric unit and timing.
SPECTACULAR_SETTINGS["ENUM_NAME_OVERRIDES"].update({
    "OverviewMetricUnitEnum": [(value, value) for value in ("count", "hours", "bytes", "percent", "money")],
    "OverviewMetricTimingEnum": [("period", "period"), ("snapshot", "snapshot")],
})
# --- end lane r2-platform-overview
# --- lane r2-peoples-choice (release 2, #181 S3): the People's choice vote budget, per account,
# and a stable OpenAPI name for its audience choice.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({
    "peoples_choice_vote": "20/hour",
})
SPECTACULAR_SETTINGS["ENUM_NAME_OVERRIDES"].update({
    "PeoplesChoiceAudienceEnum": [("members", "Any signed-in member"), ("attendees", "Checked-in attendees only")],
    "PeoplesChoiceStateEnum": [("off", "off"), ("scheduled", "scheduled"), ("open", "open"), ("closed", "closed"),
                               ("published", "published")],
    # The prize payout method is now shared with the People's choice payout input: keep L21b's name.
    "PayoutInputMethodEnum": [(value, value) for value in (
        "cash", "upi", "bank_transfer", "card", "cheque", "online", "other")],
    "PeoplesChoiceRefusalEnum": [(value, value) for value in (
        "off", "not_open", "closed", "published", "attendees_only", "voided")],
})
# --- end lane r2-peoples-choice
# --- lane r2-gap-api (release 2, #193): the OpenAPI contract and API-client management.
from config import openapi_settings as _openapi_settings
_openapi_settings.apply(REST_FRAMEWORK, SPECTACULAR_SETTINGS, env)
# #196: personal access tokens and app connections (OAuth 2.0 / OIDC via django-oauth-toolkit).
from config import oauth_settings as _oauth_settings
INSTALLED_APPS += ["oauth2_provider"]
OAUTH2_PROVIDER_APPLICATION_MODEL = "oauth2_provider.Application"
OAUTH2_PROVIDER = _oauth_settings.provider_settings(env)
_oauth_settings.apply(REST_FRAMEWORK, SPECTACULAR_SETTINGS, env)
PERSON_CREDENTIAL_RATE_PER_MINUTE = env.int("PERSON_CREDENTIAL_RATE_PER_MINUTE", default=120)
# --- end lane r2-gap-api
# --- lane r2-control-restructure (#189 as revised by #191): who may reach /control/ at all.
# false (default) = server-only: loopback, or the SSH-tunnel listener when the tunnel overlay
# (docker/compose.control-tunnel.yml) sets CONTROL_PLANE_TUNNEL=on. true = the opt-in website
# route, exactly as before (the proxy's CIDR allowlist applies at the edge).
CONTROL_PLANE_PROXY = env.bool("CONTROL_PLANE_PROXY", default=False)
CONTROL_PLANE_TUNNEL = env.str("CONTROL_PLANE_TUNNEL", default="off").strip().lower() == "on"
# #188: `{% load control_copy %}` gives every /control/ list and form its one-line help from
# config.control_catalog (config is not an app, so the library is registered by path).
TEMPLATES[0]["OPTIONS"]["libraries"] = {"control_copy": "config.control_templatetags"}
# --- end lane r2-control-restructure
