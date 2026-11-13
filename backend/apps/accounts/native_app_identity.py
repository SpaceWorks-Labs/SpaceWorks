"""Deployment-global app eligibility and public identity validation."""

from django.utils.translation import gettext
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.accounts.models_devices import NativeAppRegistration

VERSION_PATTERN = r"[0-9]+(?:\.[0-9]+)+"
ANDROID_PACKAGE = r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+"
APPLE_BUNDLE = r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"


def eligible_registration_q(prefix="", *, production=False):
    values = {f"{prefix}makerspace__isnull": True,
              f"{prefix}status": NativeAppRegistration.Status.APPROVED}
    if production:
        values[f"{prefix}environment"] = "production"
    return Q(**values)


def eligible_registrations(*, production=False):
    return NativeAppRegistration.objects.filter(eligible_registration_q(production=production))


def registration_is_eligible(row, *, production=False):
    return bool(row.makerspace_id is None and row.status == row.Status.APPROVED
                and (not production or row.environment == "production"))


def normalise_signing_identities(platform, values):
    if not isinstance(values, list) or not 1 <= len(values) <= 5:
        raise ValidationError(gettext("Enter a JSON list of one to five signing identities."))
    if platform == "apple":
        if len(values) != 1 or not isinstance(values[0], str) or not re.fullmatch(r"[A-Z0-9]{10}", values[0]):
            raise ValidationError(gettext("Enter exactly one 10-character App ID Prefix (A–Z, 0–9)."))
        return list(values)
    if platform != "android":
        raise ValidationError(gettext("Select Android or Apple."))
    result = []
    for value in values:
        if not isinstance(value, str) or not (
            re.fullmatch(r"[0-9a-fA-F]{64}", value)
            or re.fullmatch(r"[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){31}", value)
        ):
            raise ValidationError(gettext("Enter SHA-256 distribution signer digests as hex or colon-separated hex."))
        digest = value.replace(":", "").lower()
        if digest not in result:
            result.append(digest)
    return result


def registration_signing_identities(row):
    """Empty legacy rows alone can consult the old environment declaration."""
    if row.signing_identities != []:
        return normalise_signing_identities(row.platform, row.signing_identities)
    declarations = getattr(settings, "DEVICE_ATTESTATION_APPS", {})
    platform_entries = declarations.get(row.platform, {}) if isinstance(declarations, dict) else {}
    entry = platform_entries.get(row.verifier_config_key) if isinstance(platform_entries, dict) else None
    if (not isinstance(entry, dict) or not isinstance(entry.get("environments"), list)
            or row.environment not in entry["environments"]):
        raise ValidationError(gettext("Enter signing identities on the registration in /control/."))
    value = entry.get("signing_identity")
    if row.platform == "android":
        from apps.accounts.attestation_play_integrity import certificate_digest
        try:
            value = certificate_digest(value)
        except (ValueError, TypeError) as exc:
            raise ValidationError(gettext("The legacy signing identity is invalid.")) from exc
    return normalise_signing_identities(row.platform, [value])


def min_app_versions():
    result = {"android": None, "ios": None}
    for row in eligible_registrations(production=True).exclude(min_supported_version__isnull=True):
        value = row.min_supported_version
        if not value or not re.fullmatch(VERSION_PATTERN, value):
            continue
        key = "ios" if row.platform == "apple" else row.platform
        if key not in result:
            continue
        current = result[key]
        if current is None or version_key(value) > version_key(current):
            result[key] = value
    return result


def version_key(value):
    parts = [int(part) for part in value.split(".")]
    while parts and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def matched_signing_identity(challenge, metadata):
    """Metadata is verifier-owned and also retained in server-owned MFA context."""
    return metadata.get("signing_identity") or metadata.get("certificate_digest") or challenge.signing_identity
