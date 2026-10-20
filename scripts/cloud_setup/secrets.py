"""Persistent continuity generation, with recovery identity kept out of runtime env."""

import base64
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

from .errors import SetupError
from .private_files import read_json, write_json, write_private

GENERATED = {
    "SECRET_KEY": 64, "API_CLIENT_ENC_KEY": 32, "AUDIT_MAC_MASTER_KEY": 32,
    "EVENT_STATION_PIN_PEPPER": 48, "PII_MASTER_KEY": 32, "PII_SEARCH_HASH_KEY": 32,
    "CRON_SECRET": 32, "FREE_TICK_SECRET": 48,
    "TRUSTED_EDGE_INGRESS_SECRET": 48,
}
# Keys whose format is not the 32-byte URL-safe Fernet form above. Generated once when
# absent; an existing value is validated and never replaced (that would make the
# protected data unreadable).
CONTINUITY_EXTRA = ("PUSH_TOKEN_HMAC_KEY", "ACCOUNT_PII_MASTER_KEY",
                    "EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY", "EVENT_REGISTRATION_CREDENTIAL_KEYS")


def _standard_key():
    return base64.b64encode(os.urandom(32)).decode("ascii")


def generate_extra(name):
    if name == "PUSH_TOKEN_HMAC_KEY":
        return base64.urlsafe_b64encode(os.urandom(48)).decode("ascii")
    if name == "ACCOUNT_PII_MASTER_KEY":
        return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    if name == "EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY":
        return _standard_key()
    return json.dumps({"1": _standard_key()}, separators=(",", ":"))


def _valid_standard_key(value):
    try:
        return len(base64.b64decode(value, validate=True)) == 32
    except (ValueError, TypeError):
        return False


def validate_extra(values):
    checks = {
        "PUSH_TOKEN_HMAC_KEY": lambda v: len(v) >= 32 and v.isascii(),
        "ACCOUNT_PII_MASTER_KEY": lambda v: len(base64.urlsafe_b64decode(v.encode("ascii"))) == 32,
        "EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY": _valid_standard_key,
        "EVENT_REGISTRATION_CREDENTIAL_KEYS": lambda v: (
            isinstance(json.loads(v), dict) and bool(json.loads(v))
            and all(isinstance(k, str) and _valid_standard_key(key) for k, key in json.loads(v).items())),
    }
    for name, check in checks.items():
        if name not in values:
            continue
        try:
            valid = check(values[name])
        except (ValueError, TypeError, UnicodeError):
            valid = False
        if not valid:
            raise SetupError("invalid_continuity_key", f"Preserve or deliberately recover the valid {name}; do not silently rotate it.")


RELEASE_ONLY = {"DATABASE_MAINTENANCE_URL", "SPACEWORKS_MAINTENANCE_DATABASE_URL", "DATABASE_MAINTENANCE_CONNECTION_MODE", "CLOUD_SCRATCH_DATABASES_FILE", "SETUP_SUPERADMIN_PASSWORD"}


def validate_secrets(values, *, free=False):
    if not isinstance(values, dict):
        raise SetupError("invalid_secrets", "Supply a version-1 secrets values mapping.")
    for key, value in values.items():
        if not isinstance(key, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise SetupError("invalid_secret_name", "Use environment variable names in secrets values.")
        if not isinstance(value, str) or len(value) > 32768 or any(c in value for c in "\x00\r\n"):
            raise SetupError("invalid_secret_value", "Use bounded single-line secrets; mount multiline provider JSON separately.")
    for name, size in GENERATED.items():
        if name == "FREE_TICK_SECRET" and not free:
            continue
        if name in values:
            if name in {"SECRET_KEY", "EVENT_STATION_PIN_PEPPER", "CRON_SECRET", "FREE_TICK_SECRET", "TRUSTED_EDGE_INGRESS_SECRET"}:
                if len(values[name]) < (50 if name == "SECRET_KEY" else 32):
                    raise SetupError("invalid_continuity_key", f"Recover a sufficiently long {name}; setup never rotates an existing value.")
                if name == "FREE_TICK_SECRET" and not values[name].isascii():
                    raise SetupError("invalid_tick_secret", "Use the generated ASCII tick secret in both backend and trigger secret stores.")
                continue
            try:
                decoded = base64.b64decode(values[name], altchars=b"-_", validate=True)
                if len(decoded) < size:
                    raise ValueError
                if size == 32 and len(decoded) != 32:
                    raise ValueError
            except (ValueError, UnicodeError):
                raise SetupError("invalid_continuity_key", f"Preserve or deliberately recover the valid {name}; do not silently rotate it.") from None
    validate_extra(values)
    if "PII_MASTER_KEY" in values and values.get("PII_MASTER_KEY") == values.get("PII_SEARCH_HASH_KEY"):
        raise SetupError("key_reuse", "PII master and search keys must be independent.")
    wrapping = [values[k] for k in ("API_CLIENT_ENC_KEY", "AUDIT_MAC_MASTER_KEY", "PII_MASTER_KEY",
                                    "PII_SEARCH_HASH_KEY", "ACCOUNT_PII_MASTER_KEY") if values.get(k)]
    if len(set(wrapping)) != len(wrapping):
        raise SetupError("key_reuse", "Integration, audit, PII master and PII search keys must be independent.")
    return values


def continuity_probe(values, *, free):
    required = set(GENERATED) - ({"FREE_TICK_SECRET"} if not free else set())
    required |= {"SPACEWORKS_DEPLOYMENT_ID", "BACKUP_AGE_RECIPIENT", "BACKUP_ARCHIVE_SIGNING_PRIVATE_KEY", "BACKUP_ARCHIVE_VERIFY_PUBLIC_KEY"}
    if any(not values.get(key) for key in required):
        raise SetupError("continuity_missing", "Generate or deliberately recover all persistent continuity/signing/PII keys before launch; validate never generates them.")
    validate_secrets(values, free=free)
    uuid.UUID(values["SPACEWORKS_DEPLOYMENT_ID"])
    signing(dict(values))
    if not re.fullmatch(r"age1[0-9a-z]{58}", values["BACKUP_AGE_RECIPIENT"]):
        raise SetupError("age_recipient_invalid", "Supply the verified escrowed age recipient; retain its private identity separately.")
    return {"status": "passed", "custody": "operator-offline-confirmation-required"}


def ensure_secrets(directory, supplied, *, free):
    path = Path(directory) / "secrets.json"
    stored = read_json(path) if path.exists() else {"version": 1, "values": {}}
    for document in (stored, supplied):
        if set(document) != {"version", "values"} or document["version"] != 1:
            raise SetupError("secret_version", "Use secret file version 1 with a values object.")
        validate_secrets(document["values"], free=free)
    values = dict(stored["values"])
    for key, value in supplied["values"].items():
        if key in values and values[key] != value:
            raise SetupError("secret_change_refused", f"Existing {key} differs; use a reviewed credential rotation instead of setup.")
        values[key] = value
    for name, size in GENERATED.items():
        if name != "FREE_TICK_SECRET" or free:
            values.setdefault(name, base64.urlsafe_b64encode(os.urandom(size)).decode("ascii"))
    for name in CONTINUITY_EXTRA:
        if name not in values:
            values[name] = generate_extra(name)
            if name == "EVENT_REGISTRATION_CREDENTIAL_KEYS":
                values.setdefault("EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION", "1")
    values.setdefault("SPACEWORKS_DEPLOYMENT_ID", str(uuid.uuid4()))
    if not values.get("SETUP_SUPERADMIN_PASSWORD"):
        values["SETUP_SUPERADMIN_PASSWORD"] = base64.urlsafe_b64encode(os.urandom(48)).decode("ascii")
        values["SETUP_SUPERADMIN_PASSWORD_GENERATED"] = "True"
    try:
        uuid.UUID(values["SPACEWORKS_DEPLOYMENT_ID"])
    except ValueError:
        raise SetupError("deployment_identity", "Recover the valid deployment UUID; never mint a new identity on rerun.") from None
    signing(values)
    # Persist before invoking external tools: a failed age-keygen must not rotate keys.
    write_json(path, {"version": 1, "values": values})
    write_json(Path(directory) / "bootstrap-credential.json", {
        "version": 1, "password": values["SETUP_SUPERADMIN_PASSWORD"],
        "generated": values.get("SETUP_SUPERADMIN_PASSWORD_GENERATED") == "True",
        "action": "Keep private, require first-login change for generated credentials, then remove after successful login.",
    })
    age_identity(directory, values)
    write_json(path, {"version": 1, "values": values})
    return values


def signing(values):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    name = "BACKUP_ARCHIVE_SIGNING_PRIVATE_KEY"
    if name in values:
        try:
            key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(values[name], validate=True))
        except (ValueError, TypeError):
            raise SetupError("signing_key_invalid", "Recover the existing valid Ed25519 archive signing key.") from None
    else:
        if values.get("BACKUP_ARCHIVE_VERIFY_PUBLIC_KEY"):
            raise SetupError("signing_private_missing", "Recover the matching signing private key before continuing.")
        key = Ed25519PrivateKey.generate()
        values[name] = base64.b64encode(key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())).decode("ascii")
    public = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode("ascii")
    if values.get("BACKUP_ARCHIVE_VERIFY_PUBLIC_KEY", public) != public:
        raise SetupError("signing_key_mismatch", "Recover matching archive signing and verification keys.")
    values["BACKUP_ARCHIVE_VERIFY_PUBLIC_KEY"] = public


def age_identity(directory, values):
    path = Path(directory) / "recovery-age-identity.txt"
    if not path.exists():
        if values.get("BACKUP_AGE_RECIPIENT"):
            # Existing operator-managed recipient: do not pretend to hold its identity.
            return
        try:
            result = subprocess.run(["age-keygen"], capture_output=True, timeout=15, check=True)
            text = result.stdout.decode("ascii")
            if "AGE-SECRET-KEY-" not in text:
                raise ValueError
            write_private(path, text)
        except (OSError, ValueError, subprocess.SubprocessError):
            raise SetupError("age_keygen_required", "Install age-keygen in the setup job, or supply an escrowed BACKUP_AGE_RECIPIENT.") from None
    from .private_files import check_private
    check_private(path)
    try:
        result = subprocess.run(["age-keygen", "-y", str(path)], capture_output=True, timeout=15, check=True)
        recipient = result.stdout.decode("ascii").strip()
        if not re.fullmatch(r"age1[0-9a-z]{58}", recipient):
            raise ValueError
    except (OSError, ValueError, subprocess.SubprocessError):
        raise SetupError("age_identity_invalid", "Verify the protected recovery identity with age-keygen; never replace it automatically.") from None
    if values.get("BACKUP_AGE_RECIPIENT", recipient) != recipient:
        raise SetupError("age_recipient_mismatch", "Recover the matching age recipient and private identity.")
    values["BACKUP_AGE_RECIPIENT"] = recipient
