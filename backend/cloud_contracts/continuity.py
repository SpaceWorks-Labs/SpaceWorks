"""Versioned names shared by archive producers and offline recovery tools.

These are continuity keys, never provider credentials or scheduling authority.
"""
CONTINUITY_SCHEMA_VERSION = 2
CONTINUITY_KEYS = (
    "SECRET_KEY", "API_CLIENT_ENC_KEY", "PII_MASTER_KEY", "PII_MASTER_KEY_PREVIOUS",
    "PII_SEARCH_HASH_KEY", "HMAC_SECRET", "PUSH_TOKEN_HMAC_KEY", "CRON_SECRET",
    "AUDIT_MAC_MASTER_KEY", "EVENT_STATION_PIN_PEPPER",
    # Events programme: account-scoped PII and registration-credential keys.
    "ACCOUNT_PII_MASTER_KEY", "ACCOUNT_PII_MASTER_KEY_PREVIOUS",
    "EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY", "EVENT_REGISTRATION_CREDENTIAL_KEYS",
)
