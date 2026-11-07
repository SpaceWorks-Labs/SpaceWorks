"""Logging, metrics, deployment edition and late infrastructure wiring."""

from config.settings_django import MIDDLEWARE
from config.settings_http import CONTENT_SECURITY_POLICY
from config.settings_runtime import DEBUG, ImproperlyConfigured, build_logging, env
from config.settings_schema import SPECTACULAR_SETTINGS

# --- Observability -----------------------------------------------------------------------
# JSON log lines in production (one object per line, request_id on every record); the plain
# single-line format when DEBUG, because a person is reading it. LOG_JSON overrides either.
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOGGING = build_logging(LOG_LEVEL, json_output=env.bool("LOG_JSON", default=not DEBUG))

# Live-update stream (SSE over Redis pub/sub). Defaults to the Celery broker; empty means the
# stream answers 503 and browsers fall back to polling. Bounded stream length so a thread is
# never held forever -- the browser reconnects.
LIVE_REDIS_URL = env("LIVE_REDIS_URL", default="")
LIVE_MAX_STREAM_SECONDS = env.int("LIVE_MAX_STREAM_SECONDS", default=3600)

# What this deployment is FOR (apps/makerspaces/editions.py): makerspace (default), events,
# bookings or organization. Hides surfaces and public routes; never changes core modules.
SPACEWORKS_EDITION = env("SPACEWORKS_EDITION", default="makerspace").strip().lower()
if SPACEWORKS_EDITION not in ("makerspace", "events", "bookings", "organization"):
    raise ImproperlyConfigured(
        f"SPACEWORKS_EDITION={SPACEWORKS_EDITION!r} is not an edition "
        "(makerspace, events, bookings, organization)."
    )

# Static bearer token for GET /api/v1/metrics/ (Prometheus text). Unset => the route is 404.
METRICS_TOKEN = env("METRICS_TOKEN", default="")

# Error tracking is opt-in and only imported when a DSN is configured, so the SDK is never
# on the import path of a deployment that did not ask for it. PII stays off: scoped PII
# fields are encrypted at rest and must not leave the box through an error report.
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        send_default_pii=False,
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
        environment=env("SENTRY_ENVIRONMENT", default="production" if not DEBUG else "development"),
    )

MFA_CHALLENGE_TTL_SECONDS = env.int("MFA_CHALLENGE_TTL_SECONDS", default=300)
MFA_MAX_ATTEMPTS = env.int("MFA_MAX_ATTEMPTS", default=5)
if not 60 <= MFA_CHALLENGE_TTL_SECONDS <= 600:
    raise ImproperlyConfigured("MFA_CHALLENGE_TTL_SECONDS must be between 60 and 600.")
if not 1 <= MFA_MAX_ATTEMPTS <= 10:
    raise ImproperlyConfigured("MFA_MAX_ATTEMPTS must be between 1 and 10.")

# Lane F infrastructure is always present, independent of separable domain apps.
from config.web_analytics import analytics_settings
WEB_ANALYTICS_SCRIPT_URL, WEB_ANALYTICS_COLLECT_URL, WEB_ANALYTICS_DOMAIN = analytics_settings(
    env, CONTENT_SECURITY_POLICY,
)
ROUTE_METRICS_ENABLED = env.bool("ROUTE_METRICS_ENABLED", default=False)
PROMETHEUS_MULTIPROC_DIR = env("PROMETHEUS_MULTIPROC_DIR", default="")
MIDDLEWARE.insert(3, "apps.operations.route_metrics.RouteMetricsMiddleware")
ORGANIZATION_SELF_CREATION_ENABLED = env.bool("ORGANIZATION_SELF_CREATION_ENABLED", default=False)
ORGANIZATION_SELF_CREATION_MAX_OWNED = env.int("ORGANIZATION_SELF_CREATION_MAX_OWNED", default=3)
ORGANIZATION_SELF_CREATION_MAX_PER_DAY = env.int("ORGANIZATION_SELF_CREATION_MAX_PER_DAY", default=1)
if not all(1 <= limit <= 100 for limit in (
    ORGANIZATION_SELF_CREATION_MAX_OWNED, ORGANIZATION_SELF_CREATION_MAX_PER_DAY,
)):
    raise ImproperlyConfigured("Organization creation limits must be between 1 and 100.")

SPECTACULAR_SETTINGS.setdefault("APPEND_COMPONENTS", {}).setdefault("securitySchemes", {})["ServerHMAC"] = {
    "type": "apiKey", "in": "header", "name": "X-Signature",
    "description": "Tenant-bound server HMAC over METHOD, full path, timestamp, nonce "
                   "(when present), body. X-Client-Id and X-Timestamp also required; "
                   "see API client protocol.",
}
