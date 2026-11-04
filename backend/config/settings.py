from datetime import timedelta
from pathlib import Path
import sys

from celery.schedules import crontab
import environ
from corsheaders.defaults import default_headers
from django.core.exceptions import ImproperlyConfigured

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

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "django.contrib.admin",
    "django.contrib.auth",
    "axes",
    "django.contrib.contenttypes",
    "django.contrib.postgres",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "storages",
    "apps.accounts",
    "apps.makerspaces",
    "apps.organizations",
    "apps.payments",
    # The provider rail's surfaces, separable from the ledger above.
    "apps.payments_rail",
    "apps.presence",
    "apps.encryption",
    "apps.apiclients",
    "apps.boxes",
    "apps.inventory",
    "apps.hardware_requests",
    "apps.printing",
    "apps.audit",
    "apps.evidence",
    "apps.warranty",
    "apps.admin_api",
    "apps.data_export",
    "apps.integrations",
    "apps.operations",
    "apps.procurement",
    "apps.notifications",
    "apps.backup",
    "apps.machines",
    "apps.events",
    "apps.event_reimbursements",
    "apps.bookings",
    "apps.maintenance",
    "apps.roadmap",
    "apps.tenant_migration",
    # Enrolled printers/label printers (phase 7a); separable.
    "apps.devices",
    # Managed-platform hosting requests; inert on self-host.
    "apps.hosting_requests",
    # Release 2 L3: the shared card engine (designs, rendering, jobs, verify, wallet); core.
    "apps.card_designs",
    # Release 2 L3: organisation ID programmes; separable, switched by membership.id_programmes.
    "apps.id_programmes",
    # Release 2 L22: the per-space shop; separable, switched by the `shop` module key.
    "apps.shop",
    # Must stay LAST. Django calls ready() in this order, so being last is what
    # guarantees every other app has registered before finalize() freezes the
    # separability registries.
    "apps.separability",
]

# App labels whose runtime surfaces this deployment does not ship: no URLs, no admin
# registration, no sidebar entry, no OpenAPI paths. Rows and migrations are retained,
# and so is the retention registry, so nothing becomes unpurgeable or unencryptable.
# Deployment-scoped rather than per-tenant, because URL routing and the schema are
# process-global. App labels, not module keys -- one app can own several keys.
# A label naming a core module's app is refused at startup (separability.E007).
TOMBSTONED_APPS = tombstoned_app_labels()

MIDDLEWARE = [
    # The recovery gate stays FIRST -- it must refuse a request before any other layer
    # can act on it, and tests/backup/test_recovery_gate.py pins that position.
    "apps.backup.middleware.DeploymentRecoveryGateMiddleware",
    # Second, so it still wraps every view that could log a calendar-feed bearer token.
    "apps.events.middleware.CalendarFeedLogRedactionMiddleware",
    # Binds the per-request correlation id before any layer below can log. The two gates
    # above refuse without logging through it; that is the accepted cost of their position.
    "config.request_id.RequestIdMiddleware",
    # Clears the per-request native-session marker (accounts.native_session).
    "apps.accounts.native_session.NativeSessionContextMiddleware",
    "apps.tenant_migration.middleware.SourceMigrationGateMiddleware",
    "apps.makerspaces.middleware.TenantHostValidationMiddleware",
    "config.cloud_settings.forwarded_host.TrustedForwardedHostMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "apps.accounts.social_csp.SocialCspMiddleware",
    "csp.middleware.CSPMiddleware",
    "config.admin_access.AdminCspEvalMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "apps.inventory.middleware.FrontendHMACMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "config.admin_access.AdminSuperuserOnlyMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
    # Masks tenant PII for a superadmin inside a space's staff routes (owner decision #115).
    "apps.accounts.platform_tenant_pii.PlatformTenantPiiMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": env.db()}
# Persistent connections by default: gunicorn's worker processes otherwise open and close
# a Postgres connection per request. Transaction-mode poolers (Supabase :6543, PgBouncer)
# hand back a different server connection each time, so deployments on one set
# CONN_MAX_AGE=0 explicitly -- .env.production.example and docs/deploy-production.md do.
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = env.bool("CONN_HEALTH_CHECKS", default=True)
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = env.bool(
    "DISABLE_SERVER_SIDE_CURSORS", default=False
)
if SPACEWORKS_DEPLOYMENT_MODE == "managed":
    from config.cloud_settings.wiring import managed_database
    DATABASES["default"] = managed_database(DATABASES["default"], env)
SPACEWORKS_HOST_MARKER_PATH = env(
    "SPACEWORKS_HOST_MARKER_PATH",
    default="/run/spaceworks-host/restore-marker.json",
)
BACKUP_PRODUCER_CAPABILITY_MARKER_PATH = env(
    "BACKUP_PRODUCER_CAPABILITY_MARKER_PATH",
    default="/run/spaceworks-host/producer-capability.json",
)
BACKUP_PRODUCER_PRIVILEGED_SCRIPTS_DIR = env(
    "BACKUP_PRODUCER_PRIVILEGED_SCRIPTS_DIR",
    default="/run/spaceworks-privileged-scripts",
)
BACKUP_PRODUCER_ENTRYPOINT_PATH = env(
    "BACKUP_PRODUCER_ENTRYPOINT_PATH",
    default="/app/scripts/spaceworks_entrypoint.py",
)
BACKUP_PRODUCER_MIGRATIONS_DIR = env(
    "BACKUP_PRODUCER_MIGRATIONS_DIR",
    default=str(BASE_DIR / "apps"),
)

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
ACCOUNT_DELETION_RETENTION_DAYS = env.int("ACCOUNT_DELETION_RETENTION_DAYS", default=90)
# PostgreSQL supports 63-character identifiers. The approved Maintenance schema
# intentionally uses a 32-character descriptive index name.
SILENCED_SYSTEM_CHECKS = ["models.E034"]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "apps.accounts.auth_backends.SpaceWorksModelBackend",
]

AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=5)
AXES_COOLOFF_TIME = 1
AXES_RESET_ON_SUCCESS = True
# Axes hooks Django's authenticate(), so it covers BOTH the admin session login and
# the SimpleJWT staff login (apps/accounts LoginView) - intentional brute-force lockout
# on top of that view's DRF rate throttle. The nested list makes the lockout key the
# COMBINATION of ip_address+username (AND), not either alone (OR): repeated failures
# against a known username from other IPs can't lock that account out (no username DoS).
AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]
AXES_ENABLED = env.bool("AXES_ENABLED", default=True)
# django-axes 8 names this setting AXES_IPWARE_PROXY_COUNT. Keep its declared
# topology tied to DRF's and use the shared resolver below so the two protections
# cannot interpret an X-Forwarded-For chain differently.
AXES_IPWARE_PROXY_COUNT = TRUSTED_PROXY_COUNT
AXES_CLIENT_IP_CALLABLE = "config.client_ip.get_throttle_client_ip"

AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="evidence")
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default="http://localhost:9000")
AWS_S3_PUBLIC_ENDPOINT_URL = env(
    "AWS_S3_PUBLIC_ENDPOINT_URL",
    default=AWS_S3_ENDPOINT_URL,
)
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="us-east-1")
AWS_S3_ADDRESSING_STYLE = "path"
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = True

STORAGES = {
    "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
    # Match prior behavior: plain static storage (whitenoise serves it via middleware).
    # Manifest storage would require collectstatic before runserver, breaking host dev.
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

EVIDENCE_URL_TTL_SECONDS = env.int("EVIDENCE_URL_TTL_SECONDS", default=300)
# Signed download links for scheduled report deliveries; the stored file is swept once
# this window has passed. Longer than an evidence presign because the link lands in an
# inbox or a chat room and is read later, but still bounded and never a public URL.
REPORT_DELIVERY_URL_TTL_SECONDS = env.int("REPORT_DELIVERY_URL_TTL_SECONDS", default=6 * 60 * 60)
EVIDENCE_MAX_BYTES = env.int("EVIDENCE_MAX_BYTES", default=10485760)
EVIDENCE_ALLOWED_MIME = ["image/jpeg", "image/png", "image/webp"]
EVIDENCE_OBJECT_RETENTION_DAYS = env.int(
    "EVIDENCE_OBJECT_RETENTION_DAYS", default=365
)
EVIDENCE_OBJECT_EXPIRY_ENABLED = env.bool(
    "EVIDENCE_OBJECT_EXPIRY_ENABLED", default=False
)
EVIDENCE_RETENTION_BATCH_SIZE = env.int("EVIDENCE_RETENTION_BATCH_SIZE", default=100)
# Abandoned-upload cleanup DELETES rows (only post-marker presigns proven unconsumed);
# independent of object expiry and default off. Existing receipts still reconcile.
EVIDENCE_ABANDONED_UPLOAD_CLEANUP_ENABLED = env.bool(
    "EVIDENCE_ABANDONED_UPLOAD_CLEANUP_ENABLED", default=False
)
EVIDENCE_ABANDONED_UPLOAD_RETENTION_DAYS = env.int(
    "EVIDENCE_ABANDONED_UPLOAD_RETENTION_DAYS", default=7
)
# Event travel support: private receipts and payee documents (core payouts), and
# stage-form uploads. Retention counts from the financial/terminal anchor; quotas are
# per member and per event. Values outside these bounds refuse to start.
EVENT_REIMBURSEMENT_RECEIPT_RETENTION_DAYS = env.int("EVENT_REIMBURSEMENT_RECEIPT_RETENTION_DAYS", default=2555)
EVENT_REIMBURSEMENT_PAYEE_PURGE_DAYS = env.int("EVENT_REIMBURSEMENT_PAYEE_PURGE_DAYS", default=30)
EVENT_REIMBURSEMENT_FILE_MAX_BYTES = env.int("EVENT_REIMBURSEMENT_FILE_MAX_BYTES", default=10485760)
EVENT_REIMBURSEMENT_MEMBER_STORAGE_BYTES = env.int("EVENT_REIMBURSEMENT_MEMBER_STORAGE_BYTES", default=104857600)
EVENT_REIMBURSEMENT_EVENT_STORAGE_BYTES = env.int("EVENT_REIMBURSEMENT_EVENT_STORAGE_BYTES", default=1073741824)
EVENT_STAGE_FILE_RETENTION_DAYS = env.int("EVENT_STAGE_FILE_RETENTION_DAYS", default=365)
EVENT_STAGE_MEMBER_QUOTA_BYTES = env.int("EVENT_STAGE_MEMBER_QUOTA_BYTES", default=104857600)
EVENT_STAGE_EVENT_QUOTA_BYTES = env.int("EVENT_STAGE_EVENT_QUOTA_BYTES", default=1073741824)
for _name, _low, _high in (
    ("EVENT_REIMBURSEMENT_RECEIPT_RETENTION_DAYS", 1, 36500), ("EVENT_REIMBURSEMENT_PAYEE_PURGE_DAYS", 1, 36500),
    ("EVENT_REIMBURSEMENT_FILE_MAX_BYTES", 1, 10485760), ("EVENT_STAGE_FILE_RETENTION_DAYS", 1, 36500),
    ("EVENT_REIMBURSEMENT_MEMBER_STORAGE_BYTES", 1, 2 ** 40), ("EVENT_REIMBURSEMENT_EVENT_STORAGE_BYTES", 1, 2 ** 40),
    ("EVENT_STAGE_MEMBER_QUOTA_BYTES", 1, 2 ** 40), ("EVENT_STAGE_EVENT_QUOTA_BYTES", 1, 2 ** 40),
):
    if not _low <= globals()[_name] <= _high:
        raise ImproperlyConfigured(f"{_name} must be between {_low} and {_high}.")
del _name, _low, _high
WARRANTY_DOC_MAX_BYTES = env.int("WARRANTY_DOC_MAX_BYTES", default=10485760)
WARRANTY_DOC_ALLOWED_MIME = env.list(
    "WARRANTY_DOC_ALLOWED_MIME",
    default=["application/pdf", "image/jpeg", "image/png", "image/webp"],
)
MACHINE_DOC_MAX_BYTES = env.int("MACHINE_DOC_MAX_BYTES", default=10485760)
MACHINE_DOC_ALLOWED_EXT = env.list(
    "MACHINE_DOC_ALLOWED_EXT",
    default=[
        "pdf", "jpg", "jpeg", "png", "webp", "stl", "3mf", "step", "stp",
        "obj", "amf", "ply", "gcode", "gco", "iges", "igs", "dxf",
    ],
)
MACHINE_DOC_ALLOWED_MIME = env.list(
    "MACHINE_DOC_ALLOWED_MIME",
    default=[
        "application/pdf", "image/jpeg", "image/png", "image/webp",
        "application/octet-stream", "model/stl", "application/sla",
        "application/vnd.ms-pki.stl", "model/3mf",
        "application/vnd.ms-package.3dmanufacturing-3dmodel+xml",
        "application/vnd.ms-3mfdocument", "application/step", "model/step",
        "model/obj", "application/xml", "text/xml", "application/x-amf",
        "model/amf", "application/x-ply", "model/ply", "text/x.gcode",
        "application/x-gcode", "application/iges", "model/iges",
        "image/vnd.dxf", "application/dxf", "application/x-dxf", "text/plain",
    ],
)
PROCUREMENT_RECEIPT_MAX_BYTES = env.int("PROCUREMENT_RECEIPT_MAX_BYTES", default=10485760)
PROCUREMENT_RECEIPT_ALLOWED_MIME = env.list(
    "PROCUREMENT_RECEIPT_ALLOWED_MIME",
    default=["application/pdf", "image/jpeg", "image/png", "image/webp"],
)
PUBLIC_IMAGE_BUCKET = env("PUBLIC_IMAGE_BUCKET", default="public-images")
assert_distinct_storage_buckets(AWS_STORAGE_BUCKET_NAME, PUBLIC_IMAGE_BUCKET)
PUBLIC_IMAGE_BASE_URL = env("PUBLIC_IMAGE_BASE_URL", default="")
PUBLIC_IMAGE_MAX_BYTES = env.int("PUBLIC_IMAGE_MAX_BYTES", default=10485760)
PUBLIC_IMAGE_URL_TTL_SECONDS = env.int("PUBLIC_IMAGE_URL_TTL_SECONDS", default=300)
PUBLIC_IMAGE_ALLOWED_MIME = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/webp": [".webp"],
}
PRINT_UPLOAD_MAX_BYTES = env.int("PRINT_UPLOAD_MAX_BYTES", default=104857600)  # 100 MB
PRINT_ALLOWED_MODEL_EXT = env.list(
    "PRINT_ALLOWED_MODEL_EXT",
    default=[
        "stl", "3mf", "step", "stp", "obj", "amf", "ply", "gcode", "gco",
        "iges", "igs", "dxf",
    ],
)
PRINT_ALLOWED_MODEL_MIME = env.list(
    "PRINT_ALLOWED_MODEL_MIME",
    default=[
        "application/octet-stream", "model/stl", "application/sla",
        "application/vnd.ms-pki.stl", "model/3mf",
        "application/vnd.ms-package.3dmanufacturing-3dmodel+xml",
        "application/vnd.ms-3mfdocument", "application/step", "model/step",
        "model/obj", "application/xml", "text/xml", "application/x-amf",
        "model/amf", "application/x-ply", "model/ply", "text/x.gcode",
        "application/x-gcode", "application/iges", "model/iges",
        "image/vnd.dxf", "application/dxf", "application/x-dxf", "text/plain",
    ],
)
PRINT_ALLOWED_SCREENSHOT_EXT = ["png", "jpg", "jpeg", "webp", "pdf"]
PRINT_ALLOWED_SCREENSHOT_MIME = [
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/pdf",
]

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

# A bounded repeatable-read snapshot is part of the export's correctness contract.
# Operators may tune the bound, but disabling it would pin PostgreSQL vacuum forever.
DATA_EXPORT_DEADLINE_SECONDS = env.int("DATA_EXPORT_DEADLINE_SECONDS", default=900)
DATA_EXPORT_PAGE_SIZE = env.int("DATA_EXPORT_PAGE_SIZE", default=500)
DATA_EXPORT_RETENTION_SECONDS = env.int(
    "DATA_EXPORT_RETENTION_SECONDS", default=7 * 24 * 60 * 60
)
DATA_EXPORT_DOWNLOAD_TTL_SECONDS = env.int(
    "DATA_EXPORT_DOWNLOAD_TTL_SECONDS", default=5 * 60
)
TENANT_MIGRATION_GATE_LEASE_SECONDS = env.int(
    "TENANT_MIGRATION_GATE_LEASE_SECONDS", default=2 * 60 * 60
)
TENANT_MIGRATION_PRESIGN_DRAIN_SECONDS = env.int(
    "TENANT_MIGRATION_PRESIGN_DRAIN_SECONDS",
    default=max(
        EVIDENCE_URL_TTL_SECONDS,
        PUBLIC_IMAGE_URL_TTL_SECONDS,
    ),
)
BACKUP_AGE_RECIPIENT = env("BACKUP_AGE_RECIPIENT", default="")
BACKUP_ARCHIVE_SIGNING_PRIVATE_KEY = env(
    "BACKUP_ARCHIVE_SIGNING_PRIVATE_KEY", default=""
)
BACKUP_ARCHIVE_VERIFY_PUBLIC_KEY = env(
    "BACKUP_ARCHIVE_VERIFY_PUBLIC_KEY", default=""
)
TENANT_MIGRATION_AGE_RECIPIENT = env(
    "TENANT_MIGRATION_AGE_RECIPIENT", default=""
)
TENANT_MIGRATION_AGE_IDENTITY_FILE = env(
    "TENANT_MIGRATION_AGE_IDENTITY_FILE", default=""
)
BACKUP_DOWNLOAD_TTL_SECONDS = env.int("BACKUP_DOWNLOAD_TTL_SECONDS", default=5 * 60)
BACKUP_LEASE_SECONDS = env.int("BACKUP_LEASE_SECONDS", default=2 * 60 * 60)
BACKUP_DECISION_SECONDS = env.int("BACKUP_DECISION_SECONDS", default=5 * 60)
BACKUP_PRESIGN_DRAIN_SECONDS = env.int(
    "BACKUP_PRESIGN_DRAIN_SECONDS",
    default=max(EVIDENCE_URL_TTL_SECONDS, PUBLIC_IMAGE_URL_TTL_SECONDS),
)
BACKUP_OPS_DIR = env("BACKUP_OPS_DIR", default="/var/lib/spaceworks/ops")
TENANT_DUMP_STAGING_DIR = env("TENANT_DUMP_STAGING_DIR", default="")
TENANT_DUMP_STAGING_MAX_AGE_SECONDS = env.int(
    "TENANT_DUMP_STAGING_MAX_AGE_SECONDS", default=7 * 24 * 60 * 60
)
# Beat runs return reminders hourly; the internal cron endpoint remains a manual/external fallback.
REMINDER_SWEEP_BATCH_SIZE = env.int("REMINDER_SWEEP_BATCH_SIZE", default=200)
if REMINDER_SWEEP_BATCH_SIZE < 1:
    raise ImproperlyConfigured("REMINDER_SWEEP_BATCH_SIZE must be positive.")

# Canonical outbox and per-device recovery share the sending cutover fence.
# Deployment activation remains an explicit operator checkpoint after replay.
CELERY_BEAT_SCHEDULE = {
    "missing-payment-bills": {
        "task": "apps.payments.tasks.issue_missing_bills_task",
        "schedule": crontab(minute="*/5"),
    },
    # Rebuilds refund cases an events cancellation hook failed to open; idempotent.
    "rebuild-refund-cases": {
        "task": "apps.payments.tasks.rebuild_refund_cases_task",
        "schedule": crontab(minute="17"),
    },
    "notification-contract-outbox": {
        "task": "apps.integrations.notification_tasks.sweep_notification_outbox",
        "schedule": crontab(minute="*"),
    },
    "messaging-credential-wipe": {"task": "apps.integrations.tasks_messaging_settings.wipe_messaging_credentials_task", "schedule": crontab(hour=2, minute=15)},
    "inventory-stock-snapshot": {"task": "apps.inventory.tasks.snapshot_stock_task", "schedule": crontab(hour=0, minute=15)},
    "member-push-recovery": {
        "task": "apps.notifications.tasks.sweep_member_push",
        "schedule": crontab(minute="*/5"),
    },
    "purge-deleted-accounts": {
        "task": "apps.accounts.tasks.purge_deleted_accounts_task",
        "schedule": crontab(hour=3, minute=20),
    },
    # Superadmin PII windows last 30 minutes (#111 Q12). Reads close lapsed windows
    # lazily; this sweep writes the expiry audit row for windows nobody reads again.
    "pii-access-expiry": {
        "task": "apps.accounts.tasks.expire_pii_access_windows_task",
        "schedule": crontab(minute="*/5"),
    },
    "reminder-sweep": {
        "task": "apps.operations.tasks_reminders.run_reminder_sweep_task",
        "schedule": crontab(minute="*/5"),
    },
    "platform-problem-checks": {
        "task": "apps.operations.tasks_platform.run_platform_problem_checks_task",
        "schedule": crontab(minute="*/15"),
    },
    "membership-admissions": {
        "task": "apps.operations.tasks_admissions.sweep_membership_admissions_task",
        "schedule": crontab(minute="*/5"),
    },
    "scan-offline-devices": {
        "task": "apps.devices.tasks.scan_offline_devices_task",
        "schedule": crontab(minute="*"),
    },
    "cleanup-kiosk-replay-commands": {
        "task": "apps.hardware_requests.tasks_replay.cleanup_replay_commands_task",
        "schedule": crontab(hour=3, minute=20),
    },
    "flush-api-client-usage": {
        "task": "apps.apiclients.tasks.flush_api_client_usage_task",
        "schedule": crontab(minute="*"),
    },
    "audit-attestation": {
        "task": "apps.audit.tasks.run_audit_attestation_task",
        "schedule": crontab(minute="*/5"),
    },
    # Recovery issuance stays entirely off the anonymous request path. One minute keeps
    # user-visible latency bounded while each invocation still claims a bounded batch.
    "drain-password-reset-envelopes": {
        "task": "apps.accounts.tasks.drain_password_reset_envelopes_task",
        "schedule": crontab(minute="*"),
    },
    "return-reminders": {
        "task": "apps.hardware_requests.tasks.send_return_reminders_task",
        "schedule": crontab(minute=0),
    },
    "evidence-object-expiry": {
        "task": "apps.evidence.tasks.sweep_evidence_retention_task",
        "schedule": crontab(minute=10, hour="*/6"),
    },
    # Every 360 minutes: reconcile due late-write receipts first, then new cleanup.
    "evidence-abandoned-upload-cleanup": {
        "task": "apps.evidence.tasks.cleanup_abandoned_evidence_uploads_task",
        "schedule": crontab(minute=40, hour="*/6"),
    },
    "extend-event-series": {
        "task": "apps.events.tasks.extend_event_series_task",
        "schedule": crontab(minute=10),
    },
    "event-admission-deadlines": {
        "task": "apps.events.tasks_programme.sweep_admission_deadlines_task",
        "schedule": crontab(minute="*/5"),
    },
    "event-contributor-maintenance": {
        "task": "apps.events.tasks_contributions.sweep_contributor_maintenance_task",
        "schedule": crontab(minute="*"),
    },
    "event-scheduled-broadcasts": {
        "task": "apps.events.programme.broadcast_schedule.resume_scheduled_broadcasts",
        "schedule": crontab(minute="*"),
    },
    "event-asset-work": {"task": "apps.events.tasks_assets.sweep_asset_work_task", "schedule": crontab(minute="*")},
    "event-asset-deadlines": {"task": "apps.events.tasks_assets.sweep_asset_deadlines_task", "schedule": crontab(minute="*")},
    "event-asset-retention": {"task": "apps.events.tasks_assets.sweep_asset_retention_task", "schedule": crontab(minute="*/5")},
    "event-asset-obligations": {"task": "apps.events.tasks_assets.reconcile_asset_obligations_task", "schedule": crontab(minute="*/5")},
    "event-certificate-batches": {"task": "apps.events.certificates.tasks.resume_batches", "schedule": crontab(minute="*")},
    "event-certificate-renders": {"task": "apps.events.certificates.tasks.resume_certificates", "schedule": crontab(minute="*/5")},
    "event-print-cleanup": {"task": "apps.events.tasks_recovery.sweep_print_cleanup_task", "schedule": crontab(minute="*/5")},
    "event-judging-notices": {"task": "apps.events.tasks_recovery.sweep_judging_notices_task", "schedule": crontab(minute="*")},
    # Stage forms (Events core), travel-support deadlines (event_reimbursements) and the core
    # payout ledger's upload recovery and retention. Each per-subject step gates its host.
    "event-stage-reconcile": {"task": "apps.events.staged_forms.tasks.reconcile_stage_forms_task", "schedule": crontab(minute="*/5")},
    "event-stage-file-recovery": {"task": "apps.events.staged_forms.tasks.recover_stage_files_task", "schedule": crontab(minute="*/5")},
    "event-stage-file-retention": {"task": "apps.events.staged_forms.tasks.sweep_stage_file_retention_task", "schedule": crontab(hour=3, minute=50)},
    "event-reimbursement-deadlines": {"task": "apps.event_reimbursements.tasks.sweep_deadlines_task", "schedule": crontab(minute="*/5")},
    "finance-event-payout-recovery": {"task": "apps.payments.event_payouts.tasks.recover_finance_work_task", "schedule": crontab(minute="*/5")},
    "finance-event-payout-retention": {"task": "apps.payments.event_payouts.tasks.sweep_retention_task", "schedule": crontab(hour=3, minute=55)},
    "account-saved-details": {
        "task": "apps.accounts.saved_details.tasks.process_saved_details",
        "schedule": crontab(minute="*/5"),
    },
    # Spent email/phone verification challenges hold an address or a number and nothing
    # deleted them. Off-peak because it is a pure delete nobody is waiting on.
    "purge-auth-challenges": {
        "task": "apps.accounts.tasks.purge_auth_challenges_task",
        "schedule": crontab(hour=3, minute=30),
    },
    # Hosting requests: delete unconfirmed public submissions after 48 h and wipe the
    # applicant's details from dead requests after 90 days. Runs on self-host too.
    "hosting-request-retention": {
        "task": "apps.hosting_requests.tasks.sweep_hosting_requests_task",
        "schedule": crontab(hour=3, minute=45),
    },
    # Maker-profile GitHub counts. Daily and off-peak: the cache interval is 24h, the
    # data is a vanity number, and nothing is waiting on it. A deployment with no
    # GITHUB_API_TOKEN makes no outbound call at all -- the task returns immediately.
    "refresh-github-contributions": {
        "task": "apps.makerspaces.tasks.refresh_github_contributions_task",
        "schedule": crontab(hour=4, minute=15),
    },
    "cleanup-public-page-assets": {
        "task": "apps.makerspaces.tasks.cleanup_public_page_assets_task",
        "schedule": crontab(minute=10),
    },
    "membership-renewals": {
        "task": "apps.makerspaces.tasks_membership.run_membership_renewals_task",
        "schedule": crontab(minute=30),
    },
    "purge-expired-kiosk-operator-leases": {
        "task": "apps.makerspaces.tasks_station.purge_expired_operator_leases_task",
        "schedule": crontab(hour=3, minute=25),
    },
    "purge-expired-data-exports": {
        "task": "apps.data_export.tasks.purge_expired_exports_task",
        "schedule": crontab(hour=3, minute=45),
    },
    "finalize-report-rollups": {
        "task": "apps.operations.tasks.finalize_report_rollups_task",
        "schedule": crontab(hour=1, minute=0),
    },
    "report-schedules": {
        "task": "apps.operations.tasks_report_schedules.run_report_schedules_task",
        "schedule": crontab(minute="*/15"),
    },
    "scheduled-deployment-backup": {
        "task": "apps.backup.tasks.scheduled_deployment_backup_task",
        "schedule": crontab(hour=2, minute=0),
    },
    # Nightly one-space archives (#111 Q4): two due spaces per tick, oldest first, off
    # the same automatic-backups switch; 01:00-07:50 covers 84 spaces a night.
    "scheduled-space-backups": {
        "task": "apps.backup.tasks.scheduled_space_backups_task",
        "schedule": crontab(hour="1-7", minute="*/10"),
    },
    # Picks up a per-space restore step whose dispatch was lost, one per tick.
    "resume-space-restores": {
        "task": "apps.backup.tasks_space_restore.resume_space_restores_task",
        "schedule": crontab(minute="*/5"),
    },
    "reconcile-backup-artifacts": {
        "task": "apps.backup.tasks.reconcile_backup_artifacts_task",
        "schedule": crontab(minute="*/5"),
    },
    # Offsite destinations: enqueue, push+verify and prune. Never under the backup
    # operation lock, and an outage only backs the journal row off.
    "push-offsite-backups": {
        "task": "apps.backup.tasks.push_offsite_backups_task",
        "schedule": crontab(minute="*/5"),
    },
    "purge-expired-backup-archives": {
        "task": "apps.backup.tasks.purge_expired_backup_archives_task",
        "schedule": crontab(hour=3, minute=55),
    },
    "cleanup-expired-restore-rollbacks": {
        "task": "apps.backup.tasks.cleanup_expired_restore_rollbacks_task",
        "schedule": crontab(hour=4, minute=5),
    },
    "cleanup-expired-tenant-import-jobs": {
        "task": "apps.tenant_migration.tasks.cleanup_expired_import_jobs_task",
        "schedule": crontab(minute=20),
    },
    "cleanup-abandoned-tenant-import-objects": {
        "task": "apps.tenant_migration.tasks.cleanup_abandoned_import_objects_task",
        "schedule": crontab(minute=35),
    },
    "cleanup-refused-tenant-dump-artifacts": {
        "task": "apps.tenant_migration.tasks.cleanup_refused_tenant_dump_artifacts_task",
        "schedule": crontab(minute=40),
    },
    "resume-expired-tenant-import-finalizations": {
        "task": "apps.tenant_migration.tasks.resume_expired_finalizing_import_jobs_task",
        "schedule": crontab(minute="*/5"),
    },
}
from apps.presence.schedule import beat_entries as presence_beat_entries
CELERY_BEAT_SCHEDULE.update(presence_beat_entries(TOMBSTONED_APPS))
# --- Release 2 L2: approval digest, integrity flags, storage reconcile, escalation, room health ---
CELERY_BEAT_SCHEDULE.update({
    "event-approval-digest": {"task": "apps.events.approval_digest.send_approval_digests_task",
                              "schedule": crontab(minute="*/30")},
    "event-submission-integrity": {"task": "apps.events.submissions.integrity_jobs.sweep_integrity_checks_task",
                                   "schedule": crontab(minute="*/15")},
    "event-storage-reconcile": {"task": "apps.events.submissions.storage_reconcile.reconcile_event_storage_task",
                                "schedule": crontab(hour=4, minute=25)},
    "notification-escalation": {"task": "apps.notifications.escalation.escalate_unseen_task",
                                "schedule": crontab(minute="*/5")},
    "notification-destination-health": {"task": "apps.integrations.destination_health.disable_dead_destinations_task",
                                        "schedule": crontab(minute=50)},
})
# --- lane L5 (release 2): gateway poll of open attempts and pending provider refunds.
# Read-only provider lookups; the task itself no-ops while payments_rail is tombstoned.
CELERY_BEAT_SCHEDULE["payment-gateway-poll"] = {
    "task": "apps.payments.tasks.run_gateway_poll_task", "schedule": crontab(minute="*/5"),
}
# --- end lane L5
# --- lanes L10/L11 (release 2): restore drills (one due space per hourly tick, 7-day default
# cadence per space, #128 C-22) and a requested re-encryption to rotated keys (BK-68).
CELERY_BEAT_SCHEDULE["restore-drill"] = {
    "task": "apps.backup.tasks.run_restore_drill_task", "schedule": crontab(minute=20),
}
CELERY_BEAT_SCHEDULE["reencrypt-backup-archives"] = {
    "task": "apps.backup.tasks.reencrypt_archives_task", "schedule": crontab(minute="*/10"),
}
# --- end lanes L10/L11
# --- lane L12 (release 2): loan pickup expiry and waitlist lapses; machine job quotes,
# pickup reminders, uncollected flags and prepaid jobs entering the queue. Bounded sweeps.
CELERY_BEAT_SCHEDULE["loan-pickups"] = {
    "task": "apps.hardware_requests.tasks_loans.sweep_loan_pickups_task", "schedule": crontab(minute="*/15"),
}
CELERY_BEAT_SCHEDULE["machine-job-flow"] = {
    "task": "apps.machines.tasks_jobs.sweep_job_flow_task", "schedule": crontab(minute="*/15"),
}
# --- end lane L12

# --- lane L3 (release 2): card jobs resume (free tick + broker loss), 7-day result purge,
# wallet-pass refresh after renewals/expiry, and the single "photo needs update" reminder.
CELERY_BEAT_SCHEDULE["card-jobs"] = {
    "task": "apps.card_designs.tasks.resume_card_jobs", "schedule": crontab(minute="*"),
}
CELERY_BEAT_SCHEDULE["card-job-results"] = {
    "task": "apps.card_designs.tasks.purge_expired_card_job_results", "schedule": crontab(minute="7"),
}
CELERY_BEAT_SCHEDULE["card-wallet-refresh"] = {
    "task": "apps.card_designs.tasks.refresh_wallet_passes", "schedule": crontab(minute="*/30"),
}
CELERY_BEAT_SCHEDULE["event-id-cards"] = {
    "task": "apps.events.tasks_id_cards.reconcile_event_id_cards_task", "schedule": crontab(minute="*/15"),
}
CELERY_BEAT_SCHEDULE["card-photo-reminders"] = {
    "task": "apps.card_designs.tasks.remind_photo_requests", "schedule": crontab(minute="17"),
}
# --- end lane L3

# --- lane L6 (release 2): expired checkout holds, missed order settlements, one payment reminder.
CELERY_BEAT_SCHEDULE["event-order-checkouts"] = {
    "task": "apps.events.reminders_payments.sweep_order_checkouts_task", "schedule": crontab(minute="*"),
}
# --- end lane L6

# --- lane L22 (release 2): shop holds that lapsed, missed settlements, uncollected-order reminders.
CELERY_BEAT_SCHEDULE["shop-sweep"] = {
    "task": "apps.shop.tasks.sweep_shop_task", "schedule": crontab(minute="*"),
}
# --- end lane L22

if "tenant_migration" in TOMBSTONED_APPS:
    CELERY_BEAT_SCHEDULE = {
        name: entry
        for name, entry in CELERY_BEAT_SCHEDULE.items()
        if ".tenant_migration." not in entry["task"]
    }
if "events" in TOMBSTONED_APPS:
    CELERY_BEAT_SCHEDULE = {
        name: entry
        for name, entry in CELERY_BEAT_SCHEDULE.items()
        if ".events." not in entry["task"] or name in {
            "event-asset-work", "event-asset-retention", "event-asset-obligations", "event-print-cleanup",
            "event-stage-file-retention",
        }
    }
if "event_reimbursements" in TOMBSTONED_APPS:
    CELERY_BEAT_SCHEDULE = {
        name: entry for name, entry in CELERY_BEAT_SCHEDULE.items()
        if ".event_reimbursements." not in entry["task"]
    }

if "devices" in TOMBSTONED_APPS:
    CELERY_BEAT_SCHEDULE = {
        name: entry for name, entry in CELERY_BEAT_SCHEDULE.items()
        if ".devices." not in entry["task"]
    }
if "shop" in TOMBSTONED_APPS:
    CELERY_BEAT_SCHEDULE = {
        name: entry for name, entry in CELERY_BEAT_SCHEDULE.items() if ".shop." not in entry["task"]
    }

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:5000", "http://localhost:5173"],
)
CORS_ALLOW_HEADERS = (
    *default_headers,
    "upload-offset",
    "x-client-id",
    "x-nonce",
    "x-signature",
    "x-timestamp",
    "x-refresh-csrf",
    "x-station-csrf",
    "x-kiosk-operator-lease",
    "x-publishable-key",
)
# --- release 2 lane L1: the SPA marks the first short-link resolve of a page load (one visit) ---
CORS_ALLOW_HEADERS += ("x-sw-visit",)
CORS_ALLOW_CREDENTIALS = True

HMAC_CLIENT_ID = env("HMAC_CLIENT_ID", default="")
HMAC_SECRET = env("HMAC_SECRET", default="")
HMAC_MAX_CLOCK_SKEW_SECONDS = env.int("HMAC_MAX_CLOCK_SKEW_SECONDS", default=300)
APICLIENT_REQUIRE_NONCE = env.bool("APICLIENT_REQUIRE_NONCE", default=False)
# Enrolled devices (apps.devices, protocol v1). The nonce TTL must cover the whole
# accepted timestamp window (2 x skew) -- devices.E003 refuses startup otherwise.
DEVICE_SIGNATURE_MAX_SKEW_SECONDS = env.int("DEVICE_SIGNATURE_MAX_SKEW_SECONDS", default=300)
DEVICE_ENROLLMENT_TTL_SECONDS = env.int("DEVICE_ENROLLMENT_TTL_SECONDS", default=900)
DEVICE_NONCE_TTL_SECONDS = env.int("DEVICE_NONCE_TTL_SECONDS", default=86400)
DEVICE_COMMAND_LEASE_SECONDS = env.int("DEVICE_COMMAND_LEASE_SECONDS", default=60)
DEVICE_COMMAND_MAX_ATTEMPTS = env.int("DEVICE_COMMAND_MAX_ATTEMPTS", default=10)
HMAC_PROTECTED_PATH_PREFIXES = env.list(
    "HMAC_PROTECTED_PATH_PREFIXES",
    default=["/api/public/", "/api/v1/public/"],
)
from apps.apiclients.read_prefixes import mandatory_hmac_prefixes
HMAC_PROTECTED_PATH_PREFIXES = list(dict.fromkeys([
    *HMAC_PROTECTED_PATH_PREFIXES, *mandatory_hmac_prefixes(),
]))

# Fernet key for encrypting ApiClient secrets at rest. Generate with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# default="" (review fix #5) so settings import never fails when encryption isn't used;
# _fernet() raises ImproperlyConfigured only when a key is actually needed. Tests/CI get a
# real key from .env / docker-compose (added below).
API_CLIENT_ENC_KEY = env("API_CLIENT_ENC_KEY", default="")
# Dedicated domain-separation secret for event-station PIN verification. The raw PIN
# is encrypted with API_CLIENT_ENC_KEY only because staff reveal is an explicit product
# requirement; the slow hash plus this independent pepper remains the verifier.
EVENT_STATION_PIN_PEPPER = env("EVENT_STATION_PIN_PEPPER", default="")
# Phase 9b kiosk Stations. The session is the shared channel; the operator lease
# attributes work to a signed-in User and may never outlive the session (checked in
# apps.makerspaces.checks_station). Kiosk PINs reuse EVENT_STATION_PIN_PEPPER under a
# distinct namespace rather than adding a second deployment secret.
KIOSK_STATION_SESSION_TTL_SECONDS = env.int(
    "KIOSK_STATION_SESSION_TTL_SECONDS", default=12 * 60 * 60
)
KIOSK_OPERATOR_LEASE_TTL_SECONDS = env.int(
    "KIOSK_OPERATOR_LEASE_TTL_SECONDS", default=8 * 60 * 60
)
KIOSK_OPERATOR_LEASE_RETENTION_SECONDS = env.int(
    "KIOSK_OPERATOR_LEASE_RETENTION_SECONDS", default=7 * 24 * 60 * 60
)
KIOSK_COMMAND_MAX_AGE_SECONDS = env.int("KIOSK_COMMAND_MAX_AGE_SECONDS", default=8 * 60 * 60)
KIOSK_REPLAY_RETENTION_SECONDS = env.int("KIOSK_REPLAY_RETENTION_SECONDS", default=7 * 24 * 60 * 60)
KIOSK_REPLAY_CLAIM_TIMEOUT_SECONDS = env.int("KIOSK_REPLAY_CLAIM_TIMEOUT_SECONDS", default=5 * 60)
KIOSK_REPLAY_CLEANUP_BATCH_SIZE = env.int("KIOSK_REPLAY_CLEANUP_BATCH_SIZE", default=500)
EVENT_CHECKIN_WINDOW_BEFORE_HOURS = env.int(
    "EVENT_CHECKIN_WINDOW_BEFORE_HOURS", default=24
)
EVENT_CHECKIN_WINDOW_AFTER_HOURS = env.int(
    "EVENT_CHECKIN_WINDOW_AFTER_HOURS", default=2
)
EVENT_CHECKIN_SYNC_GRACE_HOURS = env.int(
    "EVENT_CHECKIN_SYNC_GRACE_HOURS", default=24
)
EVENT_CHECKIN_ROSTER_LIFETIME_HOURS = env.int(
    "EVENT_CHECKIN_ROSTER_LIFETIME_HOURS", default=24
)
EVENT_CHECKIN_CLOCK_SKEW_SECONDS = env.int(
    "EVENT_CHECKIN_CLOCK_SKEW_SECONDS", default=300
)
EVENT_CHECKIN_ROSTER_MAX = env.int("EVENT_CHECKIN_ROSTER_MAX", default=1000)
# Wraps the per-scope audit row-MAC keys. Independent of PII_MASTER_KEY on purpose: the
# audit domain gets its own key so a PII key rotation cannot invalidate integrity
# evidence. Empty means row-MAC attestation is OFF and new audit rows are stored
# unattested (see apps.audit.checks, which warns at startup).
AUDIT_MAC_MASTER_KEY = env("AUDIT_MAC_MASTER_KEY", default="")

# Batch attestation (AUD-2). Anchoring is what makes tampering detectable to someone who
# controls the box, so the sink config lives here rather than in the database.
AUDIT_ATTESTATION_DEPLOYMENT_ID = env("AUDIT_ATTESTATION_DEPLOYMENT_ID", default="")
AUDIT_ATTESTATION_ANCHOR_BACKEND = env("AUDIT_ATTESTATION_ANCHOR_BACKEND", default="")
AUDIT_ATTESTATION_S3_BUCKET = env("AUDIT_ATTESTATION_S3_BUCKET", default="")
AUDIT_ATTESTATION_S3_PREFIX = env(
    "AUDIT_ATTESTATION_S3_PREFIX", default="spaceworks-audit/v1"
)
AUDIT_ATTESTATION_RETENTION_DAYS = env.int(
    "AUDIT_ATTESTATION_RETENTION_DAYS", default=2555
)
AUDIT_ATTESTATION_S3_OBJECT_LOCK_MODE = env(
    "AUDIT_ATTESTATION_S3_OBJECT_LOCK_MODE", default="COMPLIANCE"
)
AUDIT_ATTESTATION_S3_ENDPOINT_URL = env(
    "AUDIT_ATTESTATION_S3_ENDPOINT_URL", default=AWS_S3_ENDPOINT_URL
)
AUDIT_ATTESTATION_S3_ACCESS_KEY_ID = env(
    "AUDIT_ATTESTATION_S3_ACCESS_KEY_ID", default=AWS_ACCESS_KEY_ID
)
AUDIT_ATTESTATION_S3_SECRET_ACCESS_KEY = env(
    "AUDIT_ATTESTATION_S3_SECRET_ACCESS_KEY", default=AWS_SECRET_ACCESS_KEY
)
AUDIT_ATTESTATION_S3_REGION_NAME = env(
    "AUDIT_ATTESTATION_S3_REGION_NAME", default=AWS_S3_REGION_NAME
)
AUDIT_ATTESTATION_HTTP_URL = env("AUDIT_ATTESTATION_HTTP_URL", default="")
AUDIT_ATTESTATION_HTTP_BEARER_TOKEN = env(
    "AUDIT_ATTESTATION_HTTP_BEARER_TOKEN", default=""
)
AUDIT_ATTESTATION_HTTP_TIMEOUT = env.float("AUDIT_ATTESTATION_HTTP_TIMEOUT", default=10)
# Scoped requester/contact PII encryption is intentionally dormant by default.  These
# values are read lazily by the encryption broker so a disabled installation needs no
# key material or optional KMS dependency.
PII_ENCRYPTION_ENABLED = env.bool("PII_ENCRYPTION_ENABLED", default=False)
PII_ENCRYPTION_DUAL_READ = env.bool("PII_ENCRYPTION_DUAL_READ", default=True)
PII_KEY_BROKER = env("PII_KEY_BROKER", default="local")
PII_MASTER_KEY = env("PII_MASTER_KEY", default="")
PII_MASTER_KEY_PREVIOUS = env("PII_MASTER_KEY_PREVIOUS", default="")
PII_SEARCH_HASH_KEY = env("PII_SEARCH_HASH_KEY", default="")
PII_DEK_CACHE_TTL_SECONDS = env.int("PII_DEK_CACHE_TTL_SECONDS", default=300)
PII_AWS_KMS_KEY_ID = env("PII_AWS_KMS_KEY_ID", default="")
PII_AWS_KMS_REGION = env("PII_AWS_KMS_REGION", default="")
PII_AWS_KMS_ENDPOINT_URL = env("PII_AWS_KMS_ENDPOINT_URL", default="")
# Independent account custody; Events never receives these wrapping secrets.
ACCOUNT_SAVED_DETAILS_ENABLED = env.bool("ACCOUNT_SAVED_DETAILS_ENABLED", default=False)
ACCOUNT_PII_KEY_BROKER = env("ACCOUNT_PII_KEY_BROKER", default="local")
ACCOUNT_PII_MASTER_KEY = env("ACCOUNT_PII_MASTER_KEY", default="")
ACCOUNT_PII_MASTER_KEY_PREVIOUS = env("ACCOUNT_PII_MASTER_KEY_PREVIOUS", default="")
ACCOUNT_PII_AWS_KMS_KEY_ID = env("ACCOUNT_PII_AWS_KMS_KEY_ID", default="")
# --- Release 2 / U-A1: one account per person -------------------------------------------
# The unification migration converts live staff accounts only when this equals the
# plan_sha256 that `manage.py account_unification_report` printed for this database.
ACCOUNT_UNIFICATION_ACK = env("ACCOUNT_UNIFICATION_ACK", default="")
# --- end U-A1 --------------------------------------------------------------------------
# --- Release 2 / S0: login security (#62, #66, #128 C-2) --------------------------------
# Deployment-wide PLATFORM DEFAULTS. A space's security policy may only tighten them
# (`makerspaces.security_settings_registry` `stricter`); it can never loosen one.
# Breached-password check (HIBP k-anonymity range API): on, fail-open, bounded timeout.
PASSWORD_BREACH_CHECK_ENABLED = env.bool("PASSWORD_BREACH_CHECK_ENABLED", default=True)
PASSWORD_BREACH_CHECK_TIMEOUT_SECONDS = env.int("PASSWORD_BREACH_CHECK_TIMEOUT_SECONDS", default=2)
# Cloudflare Turnstile. Dormant until BOTH keys are set; the secret is secret-bearing.
TURNSTILE_SITE_KEY = env("TURNSTILE_SITE_KEY", default="")
TURNSTILE_SECRET_KEY = env("TURNSTILE_SECRET_KEY", default="")
TURNSTILE_FAIL_MODE = env("TURNSTILE_FAIL_MODE", default="open")
TURNSTILE_AFTER_FAILURES = env.int("TURNSTILE_AFTER_FAILURES", default=3)
TURNSTILE_HOSTNAMES = env.list("TURNSTILE_HOSTNAMES", default=[])
# Automatic IP blocking for credential stuffing (one source, many accounts).
LOGIN_IP_BLOCK_ENABLED = env.bool("LOGIN_IP_BLOCK_ENABLED", default=True)
LOGIN_IP_BLOCK_DISTINCT_ACCOUNTS = env.int("LOGIN_IP_BLOCK_DISTINCT_ACCOUNTS", default=10)
LOGIN_IP_BLOCK_WINDOW_SECONDS = env.int("LOGIN_IP_BLOCK_WINDOW_SECONDS", default=900)
LOGIN_IP_BLOCK_SECONDS = env.int("LOGIN_IP_BLOCK_SECONDS", default=3600)
# Unusual-login check, remembered devices, emailed login codes and alert links.
LOGIN_RISK_FAILURE_THRESHOLD = env.int("LOGIN_RISK_FAILURE_THRESHOLD", default=3)
LOGIN_REMEMBERED_DEVICE_DAYS = env.int("LOGIN_REMEMBERED_DEVICE_DAYS", default=90)
LOGIN_CODE_TTL_SECONDS = env.int("LOGIN_CODE_TTL_SECONDS", default=600)
SECURITY_ALERT_LINK_TTL_DAYS = env.int("SECURITY_ALERT_LINK_TTL_DAYS", default=14)
# Passkeys (WebAuthn): the relying-party display name; the RP ID is the request's host.
WEBAUTHN_RP_NAME = env("WEBAUTHN_RP_NAME", default="Space Works")
for _name, _low, _high in (
    ("PASSWORD_BREACH_CHECK_TIMEOUT_SECONDS", 1, 10), ("TURNSTILE_AFTER_FAILURES", 1, 20),
    ("LOGIN_IP_BLOCK_DISTINCT_ACCOUNTS", 2, 1000), ("LOGIN_IP_BLOCK_WINDOW_SECONDS", 60, 86400),
    ("LOGIN_IP_BLOCK_SECONDS", 60, 604800), ("LOGIN_RISK_FAILURE_THRESHOLD", 1, 20),
    ("LOGIN_REMEMBERED_DEVICE_DAYS", 1, 90), ("LOGIN_CODE_TTL_SECONDS", 60, 1800),
    ("SECURITY_ALERT_LINK_TTL_DAYS", 1, 30),
):
    if not _low <= globals()[_name] <= _high:
        raise ImproperlyConfigured(f"{_name} must be between {_low} and {_high}.")
del _name, _low, _high
if TURNSTILE_FAIL_MODE not in {"open", "closed"}:
    raise ImproperlyConfigured("TURNSTILE_FAIL_MODE must be open or closed.")
if bool(TURNSTILE_SITE_KEY) != bool(TURNSTILE_SECRET_KEY):
    raise ImproperlyConfigured("Set TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY together, or neither.")
if not WEBAUTHN_RP_NAME.strip() or len(WEBAUTHN_RP_NAME) > 64:
    raise ImproperlyConfigured("WEBAUTHN_RP_NAME must be 1 to 64 characters.")
# --- end S0 ----------------------------------------------------------------------------
# --- Release 2 / U-A2: minimum native app version (#128 C-6a) ---------------------------
# Semver x.y.z per platform, compared numerically; empty = no minimum. Device sign-in and
# refresh refuse an older (or unversioned) app with 426 native_app_update_required.
MIN_NATIVE_APP_VERSION_IOS = env("MIN_NATIVE_APP_VERSION_IOS", default="").strip()
MIN_NATIVE_APP_VERSION_ANDROID = env("MIN_NATIVE_APP_VERSION_ANDROID", default="").strip()
import re as _re  # noqa: E402 -- local to this check
for _name in ("MIN_NATIVE_APP_VERSION_IOS", "MIN_NATIVE_APP_VERSION_ANDROID"):
    if globals()[_name] and not _re.fullmatch(r"(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})",
                                             globals()[_name]):
        raise ImproperlyConfigured(f"{_name} must be a version like 1.4.0 (x.y.z), or empty.")
del _name, _re
# --- end U-A2 --------------------------------------------------------------------------
ACCOUNT_SAVED_ASSET_BUDGET_BYTES = env.int("ACCOUNT_SAVED_ASSET_BUDGET_BYTES", default=50 * 1024**2)
ACCOUNT_SAVED_RESUME_SCAN_REQUIRED = env.bool("ACCOUNT_SAVED_RESUME_SCAN_REQUIRED", default=False)
ACCOUNT_SAVED_RESUME_SCANNER = env("ACCOUNT_SAVED_RESUME_SCANNER", default="")
EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY = env("EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY", default="")
EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION = env.int("EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION", default=1)
EVENT_REGISTRATION_CREDENTIAL_KEYS = env.json("EVENT_REGISTRATION_CREDENTIAL_KEYS", default={})
EVENT_ASSET_SCAN_BACKEND = env("EVENT_ASSET_SCAN_BACKEND", default="none")
EVENT_ASSET_CLAMAV_HOST = env("EVENT_ASSET_CLAMAV_HOST", default="")
EVENT_ASSET_CLAMAV_PORT = env.int("EVENT_ASSET_CLAMAV_PORT", default=3310)
UI_DELIGHT_ENABLED = env.bool("UI_DELIGHT_ENABLED", default=True)
UI_EASTER_EGGS_ENABLED = env.bool("UI_EASTER_EGGS_ENABLED", default=True)
# When True, requests to HMAC_PROTECTED_PATH_PREFIXES must carry a valid signed client.
API_CLIENT_AUTH_REQUIRED = env.bool("API_CLIENT_AUTH_REQUIRED", default=False)

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 24,
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.SpaceWorksJWTAuthentication",
    ),
    # DENY BY DEFAULT (review fix #4): every view requires auth unless it explicitly
    # opts into AllowAny. Public views are marked AllowAny in Step 3b.
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "EXCEPTION_HANDLER": "apps.hardware_requests.exceptions.workflow_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "login": env("THROTTLE_LOGIN", default="10/min"),
        "mfa_verify": env("THROTTLE_MFA_VERIFY", default="10/min"),
        "mfa_challenge": env("THROTTLE_MFA_CHALLENGE", default="10/min"),
        "mfa_user": env("THROTTLE_MFA_USER", default="20/hour"),
        "mfa_manage": env("THROTTLE_MFA_MANAGE", default="10/hour"),
        "staff_invite": env("THROTTLE_STAFF_INVITE", default="20/hour"),
        "staff_invite_accept": env("THROTTLE_STAFF_INVITE_ACCEPT", default="10/min"),
        "device_attestation_challenge": env("THROTTLE_DEVICE_ATTESTATION_CHALLENGE", default="5/min"),
        "device_login": env("THROTTLE_DEVICE_LOGIN", default="5/min"),
        "device_login_user": env("THROTTLE_DEVICE_LOGIN_USER", default="10/hour"),
        "device_refresh": env("THROTTLE_DEVICE_REFRESH", default="30/min"),
        "push_device_registration": env("THROTTLE_PUSH_DEVICE_REGISTRATION", default="10/min"),
        "social_nonce": env("THROTTLE_SOCIAL_NONCE", default="10/min"),
        "social_login": env("THROTTLE_SOCIAL_LOGIN", default="10/min"),
        "social_link": env("THROTTLE_SOCIAL_LINK", default="10/hour"),
        # Issuance and redemption deliberately have independent budgets. A member who
        # mistypes a physically handed code must not consume the staff issue budget (or
        # vice versa), repeating the phone-OTP shared-bucket failure.
        "member_claim_issue": env("THROTTLE_MEMBER_CLAIM_ISSUE", default="10/hour"),
        # Each staff verification run is bounded cryptographic + anchor work.
        "audit_verification": env("THROTTLE_AUDIT_VERIFICATION", default="6/hour"),
        "member_claim_redeem": env("THROTTLE_MEMBER_CLAIM_REDEEM", default="10/min"),
        # Tighter than the email OTP rates: every one of these costs the operator money
        # and lands on a stranger's handset if the number is wrong.
        "phone_otp_request": env("THROTTLE_PHONE_OTP_REQUEST", default="5/min"),
        "phone_otp_number": env("THROTTLE_PHONE_OTP_NUMBER", default="5/hour"),
        "phone_login_confirm": env("THROTTLE_PHONE_LOGIN_CONFIRM", default="10/min"),
        "phone_confirm_number": env("THROTTLE_PHONE_CONFIRM_NUMBER", default="15/hour"),
        "password_reset_request": env(
            "THROTTLE_PASSWORD_RESET_REQUEST",
            default="5/min",
        ),
        "password_reset_email": env(
            "THROTTLE_PASSWORD_RESET_EMAIL",
            default="5/hour",
        ),
        "password_reset_confirm": env(
            "THROTTLE_PASSWORD_RESET_CONFIRM",
            default="10/min",
        ),
        "password_reset_confirm_email": env(
            "THROTTLE_PASSWORD_RESET_CONFIRM_EMAIL",
            default="15/hour",
        ),
        "member_sign_up": env("THROTTLE_MEMBER_SIGN_UP", default="5/min"),
        "email_verification_resend": env(
            "THROTTLE_EMAIL_VERIFICATION_RESEND", default="5/min"
        ),
        "email_verification_confirm": env(
            "THROTTLE_EMAIL_VERIFICATION_CONFIRM", default="10/min"
        ),
        "member_verification_email": env(
            "THROTTLE_MEMBER_VERIFICATION_EMAIL", default="5/hour"
        ),
        "telegram_webhook": env("THROTTLE_TELEGRAM_WEBHOOK", default="60/min"),
        "public_request_submit": env(
            "THROTTLE_PUBLIC_REQUEST_SUBMIT",
            default="10/min",
        ),
        "anonymous_request_ip_burst": env(
            "THROTTLE_ANONYMOUS_REQUEST_IP_BURST",
            default="5/min",
        ),
        "anonymous_request_ip_hour": env(
            "THROTTLE_ANONYMOUS_REQUEST_IP_HOUR",
            default="30/hour",
        ),
        "anonymous_request_email": env(
            "THROTTLE_ANONYMOUS_REQUEST_EMAIL",
            default="5/hour",
        ),
        "public_invitation_request": env(
            "THROTTLE_PUBLIC_INVITATION_REQUEST", default="10/hour"
        ),
        "hosting_request_submit": env("THROTTLE_HOSTING_REQUEST_SUBMIT", default="5/hour"),
        "hosting_request_email": env("THROTTLE_HOSTING_REQUEST_EMAIL", default="3/day"),
        "hosting_request_token": env("THROTTLE_HOSTING_REQUEST_TOKEN", default="30/hour"),
        "hosting_invitation_create": env("THROTTLE_HOSTING_INVITATION_CREATE", default="20/hour"),
        "print_request_submit": env("THROTTLE_PRINT_REQUEST_SUBMIT", default="10/min"),
        "public_tool_checkout": env("THROTTLE_PUBLIC_TOOL_CHECKOUT", default="10/min"),
        "public_tool_return": env("THROTTLE_PUBLIC_TOOL_RETURN", default="10/min"),
        "request_submit": env("THROTTLE_REQUEST_SUBMIT", default="10/min"),
        "request_status": env("THROTTLE_REQUEST_STATUS", default="60/min"),
        "public_read": env("THROTTLE_PUBLIC_READ", default="120/min"),
        "event_register": env("THROTTLE_EVENT_REGISTER", default="10/hour"),
        "event_registration_retry": env(
            "THROTTLE_EVENT_REGISTRATION_RETRY", default="30/hour"
        ),
        "event_checkin_resolve": env(
            "THROTTLE_EVENT_CHECKIN_RESOLVE", default="60/min"
        ),
        "event_offline_roster": env(
            "THROTTLE_EVENT_OFFLINE_ROSTER", default="10/hour"
        ),
        "event_offline_sync": env(
            "THROTTLE_EVENT_OFFLINE_SYNC", default="60/hour"
        ),
        "event_station_pin_token": env(
            "THROTTLE_EVENT_STATION_PIN_TOKEN", default="10/hour"
        ),
        "event_station_pin_ip": env(
            "THROTTLE_EVENT_STATION_PIN_IP", default="30/hour"
        ),
        "event_station_session": env(
            "THROTTLE_EVENT_STATION_SESSION", default="120/hour"
        ),
        "event_station_reveal": env(
            "THROTTLE_EVENT_STATION_REVEAL", default="5/hour"
        ),
        "kiosk_station_pin_token": env(
            "THROTTLE_KIOSK_STATION_PIN_TOKEN", default="10/hour"
        ),
        "kiosk_station_pin_ip": env(
            "THROTTLE_KIOSK_STATION_PIN_IP", default="30/hour"
        ),
        "kiosk_station_session": env(
            "THROTTLE_KIOSK_STATION_SESSION", default="120/hour"
        ),
        "kiosk_operator_lease": env(
            "THROTTLE_KIOSK_OPERATOR_LEASE", default="30/hour"
        ),
        "kiosk_replay_prepare": env("THROTTLE_KIOSK_REPLAY_PREPARE", default="60/hour"),
        "kiosk_replay_execute": env("THROTTLE_KIOSK_REPLAY_EXECUTE", default="240/hour"),
        # Fixed, not env-tunable: the plan pins reveal at exactly 5/hour.
        "kiosk_station_reveal": "5/hour",
        "event_calendar_feed_token": env(
            "THROTTLE_EVENT_CALENDAR_FEED_TOKEN", default="120/hour"
        ),
        "event_calendar_feed_ip": env(
            "THROTTLE_EVENT_CALENDAR_FEED_IP", default="300/hour"
        ),
        "public_stats": env("THROTTLE_PUBLIC_STATS", default="30/min"),
        "client_public": env("THROTTLE_CLIENT_PUBLIC", default="30/min"),
        "client_standard": env("THROTTLE_CLIENT_STANDARD", default="120/min"),
        "client_trusted": env("THROTTLE_CLIENT_TRUSTED", default="600/min"),
        'booking_submit': env('THROTTLE_BOOKING_SUBMIT', default='10/hour'),
        "membership_request": env("THROTTLE_MEMBERSHIP_REQUEST", default="10/hour"),
        "presence_start": env("THROTTLE_PRESENCE_START", default="10/hour"),
        # A presigned upload can be requested and never attached, stranding an object
        # that no row names and no quota counts. Generous for the real workflow -- an
        # avatar plus a handful of project images -- and a hard ceiling on how much one
        # member can strand. See `makerspaces.throttles.MemberImagePresignThrottle`.
        "member_image_presign": env("THROTTLE_MEMBER_IMAGE_PRESIGN", default="20/hour"),
        "data_export_create": env("THROTTLE_DATA_EXPORT_CREATE", default="3/hour"),
        "tenant_migration_read": env(
            "THROTTLE_TENANT_MIGRATION_READ", default="120/min"
        ),
        "tenant_migration_write": env(
            "THROTTLE_TENANT_MIGRATION_WRITE", default="30/hour"
        ),
        "tenant_migration_upload": env(
            "THROTTLE_TENANT_MIGRATION_UPLOAD", default="1200/min"
        ),
        # --- release 2 lane L1: event short-link resolution (/e/<code>) ---
        "event_short_link": env("THROTTLE_EVENT_SHORT_LINK", default="30/min"),
        # --- release 2 lane S0: login security (codes, passkeys, alert links) ---
        "login_code_resend": env("THROTTLE_LOGIN_CODE_RESEND", default="5/hour"),
        "login_code_ip": env("THROTTLE_LOGIN_CODE_IP", default="30/hour"),
        "passkey_options": env("THROTTLE_PASSKEY_OPTIONS", default="30/min"),
        "passkey_verify": env("THROTTLE_PASSKEY_VERIFY", default="10/min"),
        "security_alert_action": env("THROTTLE_SECURITY_ALERT_ACTION", default="10/hour"),
        # --- release 2 lane U-C: account merge (start/resend, proofs/preview/confirm) ---
        "account_merge_start": env("THROTTLE_ACCOUNT_MERGE_START", default="10/hour"),
        "account_merge_prove": env("THROTTLE_ACCOUNT_MERGE_PROVE", default="30/hour"),
    },
    # Proxy-aware client IP for throttling. Production must declare its topology at
    # settings import above; direct DEBUG development defaults to zero trusted proxies.
    # A positive count selects the Nth-from-last XFF entry appended by trusted proxies.
    "NUM_PROXIES": TRUSTED_PROXY_COUNT,
    "URL_FORMAT_OVERRIDE": None,
}

# TLS-dependent hardening. Gated behind ENABLE_HTTPS (env), NOT DEBUG: the default
# Docker/prod compose serves plain HTTP and must not trust client-supplied forwarded
# proto headers. TLS overlays set TRUST_X_FORWARDED_PROTO=true only when a trusted
# reverse proxy is the sole path to the backend.
ENABLE_HTTPS = env.bool("ENABLE_HTTPS", default=False)
TRUST_X_FORWARDED_PROTO = env.bool("TRUST_X_FORWARDED_PROTO", default=False)
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https") if TRUST_X_FORWARDED_PROTO else None
)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=ENABLE_HTTPS)
# Plain-HTTP callers INSIDE the deployment must not be bounced to https:// -- there is no
# TLS on the backend port, so the redirect is a failure, not an upgrade. These are the
# compose healthchecks (`urllib` follows the 301 onto a TLS-less port), Caddy's on-demand
# TLS ask (any non-200 means no certificate is ever issued for a custom domain) and a
# Prometheus scrape. A request that arrives through the TLS proxy is already secure
# (`TRUST_X_FORWARDED_PROTO`), so it was never redirected: the exemption changes the answer
# only for a caller that reached the plain backend port, which is exactly the internal one.
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/", r"^api/v1/internal/", r"^api/v1/metrics/$"]
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=ENABLE_HTTPS)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=ENABLE_HTTPS)
# Needed for admin/login POST when reached over HTTPS via a custom domain behind a
# proxy. Same-origin HTTP needs nothing here; set to the public https origin(s) when
# ENABLE_HTTPS is on, e.g. CSRF_TRUSTED_ORIGINS=https://makerspace.example.org
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
SECURE_HSTS_SECONDS = env.int(
    "SECURE_HSTS_SECONDS", default=31536000 if ENABLE_HTTPS else 0
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0

# Always-on, transport-independent headers.
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin"

# Permissive enough for the current admin and API docs; tighten per deployment later.
# drf-spectacular's Swagger UI / Redoc load their JS+CSS from the jsDelivr CDN, so the
# CDN is allowed for script/style/img/font; drop it (or adopt drf-spectacular-sidecar to
# serve the assets from 'self') once the docs UI is locally hosted.
_SWAGGER_CDN = "https://cdn.jsdelivr.net"
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        # 'wasm-unsafe-eval' lets the in-browser QR scanner instantiate the bundled
        # zxing-wasm reader (the camera fallback on browsers without a native
        # BarcodeDetector). It permits ONLY WebAssembly compilation, NOT arbitrary
        # JS eval, so it is far narrower than 'unsafe-eval'.
        "script-src": ["'self'", "'unsafe-inline'", "'wasm-unsafe-eval'", _SWAGGER_CDN],
        "style-src": ["'self'", "'unsafe-inline'", _SWAGGER_CDN],
        "img-src": ["'self'", "data:", _SWAGGER_CDN],
        "font-src": ["'self'", "data:", _SWAGGER_CDN],
        "worker-src": ["'self'", "blob:"],
    }
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": (
        "apps.accounts.tokens.SpaceWorksAccessToken",
        "apps.accounts.claim_tokens.ClaimAccessToken",
    ),
}

# Cross-site refresh cookie (frontends live on separate origins).
AUTH_REFRESH_COOKIE = "refresh_token"
# CSRF defense for the cookie-bearing endpoints (refresh/logout): the view requires
# this custom header to be PRESENT - a non-simple header forces a CORS preflight that
# an attacker's origin cannot pass - AND validates the Origin header against the
# allowlist (review fixes #1, #8). The header VALUE is not a secret; presence + Origin
# is the defense. This works cross-origin where a readable double-submit cookie cannot.
AUTH_REFRESH_CSRF_HEADER = "X-Refresh-CSRF"
AUTH_COOKIE_PATH = "/api/v1/auth/"
# SameSite=None REQUIRES Secure or browsers silently drop the cookie (review fix #2).
# Prod (separate origins over HTTPS): SAMESITE=None, SECURE=True.
# Local dev: serve the frontend through a same-origin Vite proxy to the API and set
# AUTH_COOKIE_SAMESITE=Lax + AUTH_COOKIE_SECURE=False via .env (see Step 3c note).
AUTH_COOKIE_SAMESITE = env("AUTH_COOKIE_SAMESITE", default="None")
AUTH_COOKIE_SECURE = env.bool("AUTH_COOKIE_SECURE", default=True)

# Native device routes are dormant until an exact app allowlist and both the selected
# provider verifier URL and bearer credential are configured. Verifiers must perform
# real Apple App Attest / Google Play Integrity validation and return bound claims.
DEVICE_ATTESTATION_APPS = env.json("DEVICE_ATTESTATION_APPS", default={})
DEVICE_ATTESTATION_DEV_INSECURE = env.bool("DEVICE_ATTESTATION_DEV_INSECURE", default=False)
DEVICE_APPLE_ATTESTATION_VERIFY_URL = env("DEVICE_APPLE_ATTESTATION_VERIFY_URL", default="")
DEVICE_APPLE_ATTESTATION_VERIFY_TOKEN = env("DEVICE_APPLE_ATTESTATION_VERIFY_TOKEN", default="")
DEVICE_ANDROID_ATTESTATION_VERIFY_URL = env("DEVICE_ANDROID_ATTESTATION_VERIFY_URL", default="")
DEVICE_ANDROID_ATTESTATION_VERIFY_TOKEN = env("DEVICE_ANDROID_ATTESTATION_VERIFY_TOKEN", default="")
DEVICE_ATTESTATION_CHALLENGE_TTL_SECONDS = env.int("DEVICE_ATTESTATION_CHALLENGE_TTL_SECONDS", default=180)
DEVICE_ATTESTATION_PROVIDER_TIMEOUT_SECONDS = env.int("DEVICE_ATTESTATION_PROVIDER_TIMEOUT_SECONDS", default=10)
PUSH_TOKEN_HMAC_KEY = env("PUSH_TOKEN_HMAC_KEY", default="")
SOCIAL_AUTH_NONCE_TTL_SECONDS = env.int("SOCIAL_AUTH_NONCE_TTL_SECONDS", default=300)
SOCIAL_AUTH_CLOCK_SKEW_SECONDS = env.int("SOCIAL_AUTH_CLOCK_SKEW_SECONDS", default=60)
SOCIAL_AUTH_JWKS_TIMEOUT_SECONDS = env.int("SOCIAL_AUTH_JWKS_TIMEOUT_SECONDS", default=5)
SOCIAL_AUTH_JWKS_CACHE_SECONDS = env.int("SOCIAL_AUTH_JWKS_CACHE_SECONDS", default=3600)
SOCIAL_AUTH_JWKS_MAX_BYTES = env.int("SOCIAL_AUTH_JWKS_MAX_BYTES", default=1048576)
OIDC_ATTEMPT_TTL_SECONDS = env.int("OIDC_ATTEMPT_TTL_SECONDS", default=300)
OIDC_HTTP_TIMEOUT_SECONDS = env.int("OIDC_HTTP_TIMEOUT_SECONDS", default=5)
OIDC_HTTP_MAX_BYTES = env.int("OIDC_HTTP_MAX_BYTES", default=65536)
OIDC_DISCOVERY_CACHE_SECONDS = env.int("OIDC_DISCOVERY_CACHE_SECONDS", default=300)
MEMBER_CLAIM_CODE_TTL_SECONDS = env.int(
    "MEMBER_CLAIM_CODE_TTL_SECONDS", default=15 * 60
)
MEMBER_CLAIM_SESSION_TTL_SECONDS = env.int(
    "MEMBER_CLAIM_SESSION_TTL_SECONDS", default=12 * 60 * 60
)
SOCIAL_GOOGLE_JWKS_URL = env("SOCIAL_GOOGLE_JWKS_URL", default="https://www.googleapis.com/oauth2/v3/certs")
SOCIAL_APPLE_JWKS_URL = env("SOCIAL_APPLE_JWKS_URL", default="https://appleid.apple.com/auth/keys")

SPECTACULAR_SETTINGS = {
    "TITLE": "Space Works API",
    "DESCRIPTION": (
        "Multi-tenant makerspace hardware loan system.\n\n"
        "Public flow: browse inventory, search with `q`, page with `page`, "
        "sign in as a member, submit a borrow request, then track it by public token.\n\n"
        "Admin flow: authenticate with JWT, manage makerspaces, inventory, "
        "staff, QR labels, bulk imports, request review, issue, and return.\n\n"
        "Authentication: staff/admin endpoints use `Authorization: Bearer <access>`. "
        "Public browser endpoints can use `X-Publishable-Key` when public key "
        "hardening is enabled. Server API clients send `X-Client-Id`, `X-Timestamp`, "
        "`X-Nonce`, and `X-Signature`. Generate a unique, unpredictable `X-Nonce` "
        "for every request and sign the byte sequence "
        "`METHOD\\nFULL_PATH\\nTIMESTAMP\\nNONCE\\nBODY` with HMAC-SHA256. "
        "The nonce uses 1-128 characters from `A-Z`, `a-z`, `0-9`, `.`, `_`, `~`, "
        "and `-`. A deployment may temporarily accept the legacy nonce-less signed "
        "format while `APICLIENT_REQUIRE_NONCE` is disabled."
    ),
    # Kept in step with the root `VERSION` file by
    # `tests/test_version_consistency.py`. It cannot simply READ that file: the backend
    # image is built with `context: ./backend`, so the repo root is outside the build
    # context and the file does not exist inside the container.
    "VERSION": "0.9.2",
    "ENUM_NAME_OVERRIDES": {
        "DevicePlatformEnum": "apps.accounts.models_devices.DevicePlatform.choices",
        # Each anyOf proof branch has a `type` discriminator. Without unique names
        # spectacular extracts all three as DeviceAttestationPayloadTypeEnum and
        # silently replaces the iOS/development choices with the Android choice.
        "PlayIntegrityAttestationTypeEnum": ["play_integrity"],
        "AppAttestAttestationTypeEnum": ["app_attest"],
        "DevelopmentAttestationTypeEnum": ["development"],
        # Phase 9b: the kiosk evidence-prepare route shares these choices; pin the
        # existing component name so the generated client type does not rename.
        "EvidenceUrlRequestEvidenceTypeEnum": [("issue", "Issue"), ("return", "Return")],
        "QrPrintBatchStatusEnum": [
            ("draft", "Draft"),
            ("printed", "Printed"),
            ("archived", "Archived"),
        ],
        # Refund cases: stable names instead of hash-suffixed collision names.
        "RefundCaseKindEnum": [("due", "Due under policy"), ("request", "Requested by member")],
        "RefundCaseStatusEnum": [
            ("open", "Open"), ("approved", "Approved"), ("approval_failed", "Approval failed"),
            ("declined", "Declined"), ("withdrawn", "Withdrawn"), ("void", "Void"),
        ],
        "RefundCaseReasonCodeEnum": [
            ("event_cancelled", "Event cancelled by the space"), ("registration_cancelled", "Registration cancelled"),
            ("booking_cancelled", "Booking cancelled"), ("staff_cancelled", "Cancelled by staff"),
            ("membership_cancelled", "Membership term cancelled"),
            ("member_request", "Member request"),
            ("capture_flagged", "Unexpected online capture"),  # lane L5 (capture flags)
            ("fee_waived", "Loan fee waived by staff"),  # lane L15 (loan fee waivers)
            ("order_unfulfilled", "Order could not be seated"),  # lane L6 (ticket orders)
            ("ticket_type_changed", "Changed to a cheaper ticket"),  # lane L6
            ("pass_occurrence_cancelled", "Pass occurrence cancelled"),  # lane L6
        ],
        "InventoryAssetStatusEnum": [
            ("available", "Available"),
            ("reserved", "Reserved"),
            ("issued", "Issued"),
            ("damaged", "Damaged"),
            ("lost", "Lost"),
            ("retired", "Retired"),
            ("maintenance", "Maintenance"),
        ],
    },
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVERS": [
        {"url": "http://localhost:8001", "description": "Local Docker backend"},
        {"url": "http://localhost:8000", "description": "Local Django runserver"},
    ],
    "TAGS": [
        {"name": "Auth", "description": "Staff login, refresh, logout, and profile."},
        {"name": "Public inventory", "description": "Public makerspace catalog browsing."},
        {"name": "Public requests", "description": "Public borrow request and status flows."},
        {"name": "Admin makerspaces", "description": "Admin makerspace CRUD."},
        {"name": "Admin inventory", "description": "Admin inventory CRUD and search lists."},
        {"name": "Admin requests", "description": "Review, handover, issue, and return workflows."},
        {"name": "Bulk import", "description": "Inventory import preview and apply workflow."},
        {"name": "Admin users", "description": "Staff, guest-admin, and access restriction."},
        {"name": "QR assets", "description": "QR-coded boxes, tools, scans, print, revoke."},
        {"name": "Telegram", "description": "Telegram webhook and alert integration."},
        {"name": "Printing", "description": "3D printing request and management APIs."},
        {"name": "Payments", "description": "Stripe payment configuration and verified webhooks."},
        {"name": "Containers", "description": "Container hierarchy, movement, contents, and scan history."},
        {"name": "Stock transfers", "description": "Administrative stock movement between containers and makerspaces."},
        {"name": "Stocktake", "description": "Stocktake sessions, line counts, approvals, and adjustments."},
        {"name": "Analytics", "description": "Operational inventory analytics and report summaries."},
        {"name": "Reports", "description": "CSV and XLSX operational report exports."},
        {"name": "QR print batches", "description": "QR label batch creation, item management, and print HTML."},
        {"name": "Asset units", "description": "Individual asset unit generation and QR assignment."},
        {"name": "Health", "description": "Health and readiness probes."},
        {"name": "Notifications", "description": "Persistent staff inbox notifications."},
        {"name": "Platform", "description": "Superadmin platform settings: email, social sign-in, Stripe Connect."},
        {"name": "Admin hosting", "description": "Platform subdomains and custom-domain verification."},
        {"name": "Internal", "description": "Infrastructure-only routes (TLS ask, cron); refused at the public edge."},
        {"name": "API clients", "description": "HMAC API clients, their scopes and integration settings."},
        {"name": "API key requests", "description": "Staff requests for a superadmin to issue an API client."},
    ],
}

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

# --- lane L3 (release 2): card verify, scan and join throttles; the card font library;
# photo clean-up model; platform wallet-pass credentials (Q-I11, superadmin/operator only).
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({
    "card_verify": env("THROTTLE_CARD_VERIFY", default="30/min"),
    "member_card_resolve": env("THROTTLE_MEMBER_CARD_RESOLVE", default="60/min"),
    "id_join": env("THROTTLE_ID_JOIN", default="10/min"),
    "id_join_upload": env("THROTTLE_ID_JOIN_UPLOAD", default="12/hour"),
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

# --- lane L22 (release 2): the public shop's order and guest email-code budgets, per client/IP.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({
    "shop_orders": "30/hour",
    "shop_codes": "10/hour",
})
# --- end lane L22
