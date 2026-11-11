"""Credential, audit, data protection and login defaults."""

from config.settings_runtime import ImproperlyConfigured, default_headers, env
from config.settings_storage import (
    AWS_ACCESS_KEY_ID, AWS_S3_ENDPOINT_URL, AWS_S3_REGION_NAME, AWS_SECRET_ACCESS_KEY,
)

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
# --- release 2 lane L9: a deliberate in-app language choice (Accept-Language stays the fallback) ---
CORS_ALLOW_HEADERS += ("x-spaceworks-locale",)
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
# --- lane L8 (#75d/#120, #128 C-25): row-level security backstop and key rotation.
# auto = enforce on a narrow runtime role, report-only on an owner role; never refuses to start.
TENANT_RLS_MODE = env("TENANT_RLS_MODE", default="auto")
# Tests and the release regression only: bound statements SET LOCAL ROLE to this narrow role.
TENANT_RLS_PROBE_ROLE = env("TENANT_RLS_PROBE_ROLE", default="")
# A rotated publishable browser key keeps working this long, then is refused (#77).
PUBLISHABLE_KEY_ROTATION_GRACE_HOURS = env.int("PUBLISHABLE_KEY_ROTATION_GRACE_HOURS", default=72)
# --- end lane L8
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
# Decision 300(b): on by default on every install. Off = the main host's front page is the space (or
# the /spaces directory) instead of the product landing. Exposed through GET /api/v1/config.
HUB_LANDING_ENABLED = env.bool("HUB_LANDING_ENABLED", default=True)
# When True, requests to HMAC_PROTECTED_PATH_PREFIXES must carry a valid signed client.
API_CLIENT_AUTH_REQUIRED = env.bool("API_CLIENT_AUTH_REQUIRED", default=False)
