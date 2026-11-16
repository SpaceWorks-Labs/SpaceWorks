"""Frozen names for release-2 login security (lane S0; decisions #62, #66, #74, #128 C-1/C-2).

Every later lane (U-A2, U-C, S-A, S-B, S-C, S-D) imports these names instead of spelling
its own, so an error code, a claim value or an audit action means the same thing at every
door. Adding a value is an append; renaming or removing one is a contract change.

The per-space settings rows are in ``login_security_settings`` and re-exported here.
"""

from datetime import timedelta

# --- API error codes (``{"code": ...}`` in a 4xx body) --------------------------------
CAPTCHA_REQUIRED = "captcha_required"
CAPTCHA_FAILED = "captcha_failed"
IP_BLOCKED = "ip_blocked"
PASSWORD_BREACHED = "password_breached"
LOGIN_CODE_REQUIRED = "login_code_required"
LOGIN_CODE_INVALID = "login_code_invalid"
PASSKEY_FAILED = "passkey_failed"
SECURITY_ALERT_USED = "security_alert_used"
# Existing code, named here so the grace expiry (S-A) reuses it rather than inventing one.
MFA_ENROLLMENT_REQUIRED = "mfa_enrollment_required"
# S-A: staff proof missing or stale, the relying-party ID cannot be derived, the MFA-reset
# rule refused, the last factor of a required account, and an ended staff session.
MFA_REQUIRED = "mfa_required"
RP_ID_UNAVAILABLE = "rp_id_unavailable"
MFA_RESET_NOT_ALLOWED = "mfa_reset_not_allowed"
LAST_FACTOR = "last_factor"
STAFF_SESSION_EXPIRED = "staff_session_expired"
PASSKEYS_UNAVAILABLE = "passkeys_unavailable"
PASSKEY_REQUIRED = "passkey_required"  # re-authentication: a passkey-only account confirms with it
# S-C: a staff route of a space whose staff IP allow-list does not cover the client (403).
STAFF_NETWORK_REFUSED = "staff_network_refused"
ERROR_CODES = (
    CAPTCHA_REQUIRED, CAPTCHA_FAILED, IP_BLOCKED, PASSWORD_BREACHED, LOGIN_CODE_REQUIRED,
    LOGIN_CODE_INVALID, PASSKEY_FAILED, SECURITY_ALERT_USED, MFA_ENROLLMENT_REQUIRED,
    MFA_REQUIRED, RP_ID_UNAVAILABLE, MFA_RESET_NOT_ALLOWED, LAST_FACTOR, STAFF_SESSION_EXPIRED,
    PASSKEYS_UNAVAILABLE, PASSKEY_REQUIRED, STAFF_NETWORK_REFUSED,
)

# --- Second-factor vocabulary --------------------------------------------------------
# A new ``mfa_source`` beside mfa_policy's verified/provider/none/bypass: the person
# proved a fresh emailed code (the unusual-login check for someone with no factor).
MFA_SOURCE_EMAIL_CODE = "email_code"
# Access-token claim naming WHICH factor satisfied MFA (absent when none did).
MFA_METHOD_CLAIM = "mfa_method"
MFA_METHOD_TOTP, MFA_METHOD_RECOVERY, MFA_METHOD_PASSKEY = "totp", "recovery", "passkey"
MFA_METHODS = (MFA_METHOD_TOTP, MFA_METHOD_RECOVERY, MFA_METHOD_PASSKEY)
# ``factors[]`` in a challenge response: what this person may answer with, in this order.
FACTOR_TOTP, FACTOR_PASSKEY, FACTOR_RECOVERY, FACTOR_EMAIL_CODE = "totp", "passkey", "recovery", "email_code"
FACTORS = (FACTOR_TOTP, FACTOR_PASSKEY, FACTOR_RECOVERY, FACTOR_EMAIL_CODE)

# --- Challenge purposes (emailed codes, risk checks, re-authentication) ----------------
PURPOSE_LOGIN = "login"
PURPOSE_RISK = "risk"
REAUTH_PREFIX = "reauth:"
# #135 Q-A3: what still needs a factor during the staff grace, plus factor changes.
REAUTH_INTENTS = (
    "security_settings", "pii_window", "data_export", "credential_reset", "staff_roles",
    "mfa_change", "passkey_change",
)
CHALLENGE_PURPOSES = (PURPOSE_LOGIN, PURPOSE_RISK, *(REAUTH_PREFIX + intent for intent in REAUTH_INTENTS))

# --- Passkeys (WebAuthn) ---------------------------------------------------------------
CEREMONY_REGISTRATION, CEREMONY_LOGIN, CEREMONY_MFA, CEREMONY_REAUTH = "registration", "login", "mfa", "reauth"
CEREMONY_PURPOSES = (CEREMONY_REGISTRATION, CEREMONY_LOGIN, CEREMONY_MFA, CEREMONY_REAUTH)
CEREMONY_TTL = timedelta(minutes=5)

# --- Unusual-login check -----------------------------------------------------------------
NETWORK_IPV4_24, NETWORK_IPV6_64 = "ipv4_24", "ipv6_64"
NETWORK_GRANULARITIES = (NETWORK_IPV4_24, NETWORK_IPV6_64)
DEVICE_COOKIE = "sw_device"
ALERT_NEW_DEVICE, ALERT_PASSWORD_CHANGED, ALERT_MFA_CHANGED, ALERT_LOCKOUT = (
    "new_device", "password_changed", "mfa_changed", "lockout")
ALERT_KINDS = (ALERT_NEW_DEVICE, ALERT_PASSWORD_CHANGED, ALERT_MFA_CHANGED, ALERT_LOCKOUT)

# --- IP access ---------------------------------------------------------------------------
IP_ALLOW, IP_DENY = "allow", "deny"
IP_ACTIONS = (IP_ALLOW, IP_DENY)

# --- Staff MFA grace (#128 C-1; #135 Q-A1/Q-A2) -----------------------------------------
STAFF_MFA_GRACE = timedelta(days=3)
GRACE_GRANT, GRACE_INVITE, GRACE_MERGE, GRACE_UPGRADE = "grant", "invite", "merge", "upgrade"
GRACE_SOURCES = (GRACE_GRANT, GRACE_INVITE, GRACE_MERGE, GRACE_UPGRADE)

# --- Audit actions (reserved; each lane adds its presentation entry with its emitter,
# because the presentation guard refuses an entry nothing emits) ------------------------
AUDIT_ACTIONS = {
    "auth.login_risk_challenged": "Unusual sign-in checked",
    "auth.login_code_sent": "Login code sent",
    "auth.login_code_failed": "Login code rejected",
    "auth.risk_unverifiable": "Unusual sign-in could not be checked",
    "auth.device_remembered": "Device remembered",
    "auth.device_forgotten": "Device forgotten",
    "auth.passkey_registered": "Passkey added",
    "auth.passkey_renamed": "Passkey renamed",
    "auth.passkey_removed": "Passkey removed",
    "auth.passkey_login_succeeded": "Signed in with a passkey",
    "auth.passkey_login_failed": "Passkey sign-in failed",
    "auth.security_alert_sent": "Security alert sent",
    "auth.not_me_used": "\"This wasn't me\" used",
    "auth.ip_auto_blocked": "Address blocked automatically",
    "auth.ip_unblocked": "Address unblocked",
    "auth.captcha_failed": "CAPTCHA failed",
    "auth.password_breach_rejected": "Breached password refused",
    "auth.staff_mfa_grace_started": "Staff two-step grace started",
    # S-A
    "auth.mfa_reset": "Two-step sign-in reset",
}

# --- Retention (registered here; purge lands in S-B/S-C via services_challenge_purge) ---
# model label -> (timestamp field, how long after it, what happens)
RETENTION = {
    "accounts.KnownNetwork": ("last_seen", timedelta(days=90), "delete"),
    "accounts.KnownDevice": ("last_verified_at", timedelta(days=180), "delete"),
    "accounts.IPAutoBlock": ("blocked_until", timedelta(days=7), "delete"),
    "accounts.SecurityAlert": ("expires_at", timedelta(0), "clear network_label and ua_label"),
    "accounts.SecurityAlert#row": ("expires_at", timedelta(days=30), "delete"),
    "accounts.WebAuthnCeremony": ("expires_at", timedelta(days=1), "delete"),
}

# --- Dependency floor (X-9): S-A owns the pin; recorded so nobody lowers it -------------
CRYPTOGRAPHY_FLOOR = "cryptography>=50"

from .login_security_settings import (  # noqa: E402,F401 -- re-exported
    CAPTCHA_ON_SIGN_IN, LOGIN_RISK_CHECK, PASSKEYS_ALLOWED, PER_SPACE_SETTINGS,
    REMEMBERED_DEVICE_DAYS, STAFF_IP_ALLOWLIST, STAFF_IDLE_TIMEOUT_MINUTES,
    STAFF_SESSION_MAX_HOURS,
)
