"""Native age recipients: canonical form, fingerprints and the platform recipient.

The superadmin platform key (``BACKUP_AGE_RECIPIENT``) opens every archive this
deployment builds, whatever its scope. There are no per-makerspace archive
recipients: owner decision #110b removed recipient custody entirely.
"""

import hashlib

from django.conf import settings
from django.core.exceptions import ValidationError

from .build_errors import BackupBuildError
from .recipients_bech32 import Bech32DecodeError, convert_bits, decode, encode


PLATFORM_RECIPIENT_LABEL = "Platform backup recipient"
_BECH32_MESSAGES = {
    "invalid_bech32": "The recipient is not valid Bech32.",
    "bech32m_checksum": "Bech32m recipients are not supported by age.",
    "invalid_checksum": "The recipient checksum is invalid.",
}


def canonical_recipient(raw) -> str:
    """Validate and return the canonical lowercase native age recipient."""
    if not isinstance(raw, str):
        raise ValidationError("The recipient must be text.", code="recipient_type")

    value = raw.strip()
    if any(character.isspace() for character in value):
        raise ValidationError(
            "The recipient cannot contain internal whitespace.",
            code="recipient_whitespace",
        )
    if value.upper().startswith("AGE-SECRET-KEY"):
        raise ValidationError(
            "A private age identity cannot be used as a public recipient.",
            code="private_key",
        )

    if value == value.lower():
        value = value.lower()
    elif value == value.upper():
        value = value.lower()
    else:
        raise ValidationError(
            "Bech32 recipients cannot use mixed case.", code="mixed_case"
        )

    if value.startswith("age-plugin-"):
        raise ValidationError(
            "Plugin recipients are not supported.", code="plugin_recipient"
        )

    try:
        hrp, payload = decode(value)
    except Bech32DecodeError as exc:
        raise ValidationError(_BECH32_MESSAGES[exc.code], code=exc.code) from exc
    if hrp != "age":
        raise ValidationError(
            "The recipient must use the age human-readable prefix.",
            code="invalid_hrp",
        )
    decoded = convert_bits(payload, 5, 8, pad=False)
    if decoded is None or len(decoded) != 32:
        raise ValidationError(
            "The recipient payload must decode to 32 bytes.",
            code="invalid_payload_length",
        )
    return encode("age", convert_bits(decoded, 8, 5, pad=True))


def fingerprint_for(canonical: str) -> str:
    return hashlib.sha256(canonical.encode()).hexdigest()


def platform_recipient():
    """Return the platform recipient every archive is encrypted to."""
    public_recipient = settings.BACKUP_AGE_RECIPIENT
    if not public_recipient:
        raise BackupBuildError(
            "BACKUP_AGE_RECIPIENT is required before backups can run."
        )
    return {
        "label": PLATFORM_RECIPIENT_LABEL,
        "public_recipient": public_recipient,
    }


def selection_for(archive) -> list[dict]:
    """Return the recipients one archive is encrypted to: the platform key only."""
    del archive
    return [platform_recipient()]
