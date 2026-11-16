"""Query-free continuity contract shared by archive preflight and host import."""

import base64

from cloud_contracts.continuity import CONTINUITY_KEYS


def validate_continuity_secrets(payload):
    if not isinstance(payload, dict) or set(payload) != set(CONTINUITY_KEYS):
        raise ValueError("Continuity secret names do not match this release.")
    for name, value in payload.items():
        if not isinstance(value, str) or len(value) > 32768 or any(c in value for c in "\x00\r\n"):
            raise ValueError("Continuity secrets must be bounded single-line strings.")
    if not payload["SECRET_KEY"]:
        raise ValueError("Required signing continuity is unavailable.")
    if payload["EVENT_STATION_PIN_PEPPER"] and len(payload["EVENT_STATION_PIN_PEPPER"].encode("utf-8")) < 32:
        raise ValueError("Configured station continuity is malformed.")
    # Optional legacy values stay optional; an archived nonempty value must be a
    # usable key rather than silently accepted corruption or replacement bytes.
    for name in ("API_CLIENT_ENC_KEY", "AUDIT_MAC_MASTER_KEY", "PII_MASTER_KEY", "PII_MASTER_KEY_PREVIOUS", "PII_SEARCH_HASH_KEY"):
        if payload[name]:
            try:
                raw = payload[name].encode("ascii")
                if len(base64.b64decode(raw + b"=" * (-len(raw) % 4), altchars=b"-_", validate=True)) != 32:
                    raise ValueError
            except (ValueError, UnicodeError):
                raise ValueError("An archived encryption key is malformed.") from None
    return dict(payload)
