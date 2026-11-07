"""Integration delivery, mail and worker transport."""

from config.settings_runtime import env, sys

# Read-only token for the GitHub GraphQL API, used only to cache a member's public
# contribution total onto their maker profile. Unset means the feature is dormant: no
# call is made and profiles simply omit the section. Never required.
GITHUB_API_TOKEN = env("GITHUB_API_TOKEN", default="")
# --- Release 2 L2: browser notifications (W3C Web Push / VAPID). Unset = dormant. ---
# The private key is the base64url raw P-256 scalar (secret-bearing); the public key is
# derived from it. The subject is a mailto: or https: contact the push services may use.
WEB_PUSH_VAPID_PRIVATE_KEY = env("WEB_PUSH_VAPID_PRIVATE_KEY", default="")
WEB_PUSH_VAPID_SUBJECT = env("WEB_PUSH_VAPID_SUBJECT", default="")
# Release 2 L2 (X31): applicants may edit and resubmit after "changes requested" (platform switch).
HOSTING_REQUEST_RESUBMIT_ENABLED = env.bool("HOSTING_REQUEST_RESUBMIT_ENABLED", default=True)

TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
NOTIFICATION_SLACK_REDIRECT_URI = env("NOTIFICATION_SLACK_REDIRECT_URI", default="")
NOTIFICATION_MATTERMOST_REDIRECT_URI = env("NOTIFICATION_MATTERMOST_REDIRECT_URI", default="")
NOTIFICATION_DISCORD_REDIRECT_URI = env("NOTIFICATION_DISCORD_REDIRECT_URI", default="")
NOTIFICATION_MATTERMOST_ALLOW_PRIVATE_HOSTS = env.bool("NOTIFICATION_MATTERMOST_ALLOW_PRIVATE_HOSTS", default=False)
WHATSAPP_META_GRAPH_VERSION = env("WHATSAPP_META_GRAPH_VERSION", default="v25.0")
TELEGRAM_API_URL = env("TELEGRAM_API_URL", default="https://api.telegram.org")
# Secret passed to Telegram's setWebhook(secret_token=...); Telegram echoes it in
# the X-Telegram-Bot-Api-Secret-Token header on every callback. The webhook fails
# closed when this is unset, so an unconfigured webhook can't be driven by spoofed
# callbacks.
TELEGRAM_WEBHOOK_SECRET = env("TELEGRAM_WEBHOOK_SECRET", default="")

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Makerspace <noreply@makerspace.local>")
EMAIL_PROVIDER = env("EMAIL_PROVIDER", default="")
EMAIL_PROVIDER_CONFIG_FILE = env("EMAIL_PROVIDER_CONFIG_FILE", default="")
EMAIL_PROVIDER_WEBHOOKS_ENABLED = env.bool("EMAIL_PROVIDER_WEBHOOKS_ENABLED", default=False)
if EMAIL_PROVIDER:
    from config.cloud_settings.wiring import provider_email
    # Provider routing is per message; preserve Django's legacy fallback backend.
    _provider_email = provider_email(env)
    EMAIL_PROVIDER_CONFIG_FILE = _provider_email["EMAIL_PROVIDER_CONFIG_FILE"]
    EMAIL_PROVIDER_WEBHOOKS_ENABLED = _provider_email["EMAIL_PROVIDER_WEBHOOKS_ENABLED"]

# Async email runs through a Celery worker ONLY when a broker is configured (the Compose
# stack + prod set CELERY_BROKER_URL). With no broker - e.g. the documented local flow
# (`docker compose up -d db` + `python manage.py runserver`), or any non-Compose process -
# fall back to EAGER (synchronous) execution so dispatch_email still delivers inline instead
# of enqueuing to an unreachable `redis` host and marking every email failed.
_celery_broker = env("CELERY_BROKER_URL", default="")
CELERY_TASK_ALWAYS_EAGER = env.bool(
    "CELERY_TASK_ALWAYS_EAGER", default=(_celery_broker == "")
)
CELERY_BROKER_URL = _celery_broker or "redis://redis:6379/0"

def cache_config(cache_url):
    """Pick the cache backend, given whatever Redis URL was explicitly configured.

    A per-process cache silently multiplies every DRF rate limit by the worker count and
    loses its counters on each worker recycle. The fallback is therefore Django's
    **DatabaseCache**, never LocMem: the brokerless cloud profile sets an empty
    `CELERY_BROKER_URL` and still runs `gunicorn --workers 3 --max-requests 1000`, so a
    per-process cache would put login, OTP, password-reset and the member image presign
    caps at three times their configured rate and reset them regularly.

    A function rather than an inline expression so the choice is testable against real
    inputs instead of asserted on the live value -- the deployment running the tests is
    not the deployment the rule is about.
    """
    if cache_url:
        return {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": cache_url}
    return {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "spaceworks_cache",
        # MAX_ENTRIES is NOT optional here, and the default would have defeated the point
        # of this whole branch. Django's DatabaseCache defaults to 300 entries and culls a
        # third of them once exceeded. A throttle key is one row per (scope, identity), and
        # this deployment has well over a dozen scoped throttles -- login, public request
        # submit, social nonce and login, password reset, the two phone OTP budgets, public
        # read, member image presign -- so 300 rows is roughly twenty callers before
        # unexpired throttle histories start being evicted. Someone rotating identities
        # could then push a live login or OTP counter out of the cache and reset their own
        # cap, which is precisely the bypass DatabaseCache was chosen to prevent.
        #
        # Culling deletes EXPIRED rows first and only culls by count if still over, so a
        # ceiling this high is effectively never reached: throttle entries expire on their
        # own window, and the rows are tiny.
        "OPTIONS": {"MAX_ENTRIES": 100_000},
    }


_cache_url = env("CACHE_URL", default="") or _celery_broker
CACHES = {"default": cache_config(_cache_url)}

# Under pytest, force LocMem. `DatabaseCache` would make the autouse `cache.clear()` in
# `tests/conftest.py` a DATABASE operation, so every test without the `django_db` mark
# fails with "Database access not allowed" -- 365 of them did. The multi-worker problem
# `DatabaseCache` exists to solve cannot occur in a single-process test run, so LocMem is
# both correct here and the only backend that keeps non-db tests db-free.
#
# Done here rather than with `override_settings(...).enable()` in `pytest_configure`:
# that leaves a global override enabled for the whole session and broke the setup of
# every `transaction=True` test in the suite. Settings are imported by pytest-django
# after pytest itself, so this check is reliable.
if "pytest" in sys.modules:  # pragma: no cover - exercised by running the suite at all
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "spaceworks-tests",
        }
    }

CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="") or None
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_ACKS_LATE = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
