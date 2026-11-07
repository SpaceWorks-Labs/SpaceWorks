"""Deployment bootstrap and host defaults."""

from datetime import timedelta
from pathlib import Path
import sys

from celery.schedules import crontab
import environ
from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured

from config.locale_registry import SYSTEM_LOCALE, django_languages
from config.log_setup import build_logging
from config.storage_validation import assert_distinct_storage_buckets

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")
from cloud_contracts.deployment import parse_selection

try:
    _deployment = parse_selection({
        "SPACEWORKS_DEPLOYMENT_MODE": env("SPACEWORKS_DEPLOYMENT_MODE", default="host"),
        "SPACEWORKS_DEPLOYMENT_PROFILE": env("SPACEWORKS_DEPLOYMENT_PROFILE", default="full"),
    })
except ValueError as exc:
    raise ImproperlyConfigured(str(exc)) from exc
SPACEWORKS_DEPLOYMENT_MODE = _deployment.mode
SPACEWORKS_DEPLOYMENT_PROFILE = _deployment.profile
if _deployment.mode == "managed":
    from config.cloud_settings.secrets import materialize
    materialize()
CLOUD_TASK_PROFILE = env("CLOUD_TASK_PROFILE", default="")
CLOUD_SCHEDULER = env("CLOUD_SCHEDULER", default="")
# Imported after read_env: both read TOMBSTONED_APPS straight from the environment,
# and the sidebar in config.unfold is built at import time.
from apps.separability.tombstones import tombstoned_app_labels
from config.unfold import UNFOLD

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

_configured_trusted_proxy_count = env.int("TRUSTED_PROXY_COUNT", default=None)
if not DEBUG and _configured_trusted_proxy_count is None:
    raise ImproperlyConfigured(
        "TRUSTED_PROXY_COUNT must be explicitly set when DEBUG is False. "
        "Use 0 for direct access or the exact number of trusted reverse proxies."
    )
if _configured_trusted_proxy_count is not None and _configured_trusted_proxy_count < 0:
    raise ImproperlyConfigured("TRUSTED_PROXY_COUNT cannot be negative.")
# Direct development access has no trusted proxy. Production may never reach this
# fallback because the guard above forces its topology to be declared explicitly.
TRUSTED_PROXY_COUNT = (
    0 if _configured_trusted_proxy_count is None else _configured_trusted_proxy_count
)


def normalize_platform_domain_suffix(raw):
    """Canonicalize the platform suffix to the leading-dot lowercase form.

    Blank/whitespace/None => "" (self-host). Otherwise lowercase + strip and
    prepend a leading "." if missing, so an operator may set PLATFORM_DOMAIN_SUFFIX
    as either "space-works.tech" or ".space-works.tech" and the stored value is always ".space-works.tech".
    The leading dot is what makes endswith(suffix) reject look-alikes (evilspace-works.tech)
    and what provisioning.provision_subdomain requires.
    """
    value = str(raw or "").strip().lower()
    if not value:
        return ""
    return value if value.startswith(".") else "." + value


PLATFORM_DOMAIN_SUFFIX = normalize_platform_domain_suffix(
    env("PLATFORM_DOMAIN_SUFFIX", default="")
)
PLATFORM_SUBDOMAIN_AUTO_TLS = env.bool("PLATFORM_SUBDOMAIN_AUTO_TLS", default=False)
INFRA_HOSTS = set(
    env.list(
        "INFRA_HOSTS",
        default=["localhost", "127.0.0.1", "backend", "backend:8000"],
    )
)
PLATFORM_STAFF_ORIGINS = env.list("PLATFORM_STAFF_ORIGINS", default=[])
BEHIND_TRUSTED_PROXY = env.bool("BEHIND_TRUSTED_PROXY", default=False)
PLATFORM_ORIGIN_HOST = env("PLATFORM_ORIGIN_HOST", default="")  # e.g. origin.space-works.tech; blank => resolution gate dormant
DOMAIN_CHANGE_COOLDOWN_SECONDS = env.int("DOMAIN_CHANGE_COOLDOWN_SECONDS", default=0)  # 0 => no cooldown
if BEHIND_TRUSTED_PROXY:
    if SPACEWORKS_DEPLOYMENT_MODE == "host":
        ALLOWED_HOSTS = ["*"]  # Existing host domain middleware remains authoritative.
PUBLIC_APP_BASE_URL = env("PUBLIC_APP_BASE_URL", default="").rstrip("/")
STRIPE_CONNECT_REDIRECT_URI = env("STRIPE_CONNECT_REDIRECT_URI", default="")
MANAGED_POSTGRES = env.bool("MANAGED_POSTGRES", default=False)
DATABASE_CONNECTION_MODE = env("DATABASE_CONNECTION_MODE", default="direct")
MANAGED_RESOURCE_LIMITS = {
    "products": 500,
    "assets": 2000,
    "machines": 5,
    "machine_service_open": 100,
    "machine_service_submit": 100,
    "events": 10,
    "bookings": 500,
    "staff": 10,
    "members": 25,
    "storage": 1073741824,
    "print": 200,
    "email": 100,
    "telegram": 100,
    "slack": 100,
    "mattermost": 100,
    "discord": 100,
    "native_push": 500,
    "sms": 100,
    "whatsapp": 100,
    # Release 2 L4 (#77): every limit key has a default; signed webhooks were unlimited.
    "webhook": 100,
    "api_clients": 1,
    # Tenant exports retain a long-lived database snapshot while running. This is an
    # active-job ceiling, independent of the byte quota charged when an archive lands.
    "data_exports": 1,
    # Platform-wide daily caps (not per space); the deployment may override them (#77).
    "otp_email": env.int("MANAGED_OTP_EMAIL_DAILY_LIMIT", default=200),
    "otp_sms": env.int("MANAGED_OTP_SMS_DAILY_LIMIT", default=100),
}
# Applies on SELF-HOST TOO, unlike the managed limits above: every auth text is billed
# by the operator's SMS vendor, so this is a cost ceiling rather than a fair-use quota.
# Blank disables the cap entirely.
OTP_SMS_DAILY_CAP = env.int("OTP_SMS_DAILY_CAP", default=200)
STORAGE_PRESIGN_METHOD = env("STORAGE_PRESIGN_METHOD", default="post")
CRON_SECRET = env("CRON_SECRET", default="")
ADMIN_SITE_NAME = env("ADMIN_SITE_NAME", default="Space Works")
# Whether this deployment has a way into `/control/` that does not use a password.
# There is no such route today -- social sign-in mints JWTs for the React console and
# never a Django session -- so this stays False, and it is what keeps the
# `password_enabled=False` switch from sealing the one page that can turn it back on.
# See `config.admin_access.AdminSuperuserOnlyMiddleware._password_login_blocked`.
# Declared here rather than read with a `getattr` default so that a reader can find it
# and an operator building such a route has somewhere to flip.
PLATFORM_ADMIN_SSO = env.bool("PLATFORM_ADMIN_SSO", default=False)
