"""One-shot tenant recipients and the two separate Lane D recipient sets (#111 Q7).

A tenant-exit export is sealed to public age keys the operator supplies for that
export only (`export_portable_tenant_dump --recipient ...`). The outer envelope adds
the platform key, because the superadmin is always on; the tenant DEK envelope is
sealed to the tenant keys alone, so the platform never gains DEK custody.
"""

from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError

from apps.backup.age_recipients import canonical_recipient, fingerprint_for

from .tenant_dump_errors import TenantDumpCustodyError


@dataclass(frozen=True)
class TenantDumpRecipientSets:
    outer_recipients: tuple[str, ...]
    tenant_dek_recipients: tuple[str, ...]


def one_shot_tenant_recipients(raw_recipients):
    """Canonical, de-duplicated, fingerprint-sorted tenant recipients for one export."""
    if isinstance(raw_recipients, str) or not raw_recipients:
        raise TenantDumpCustodyError(
            "A tenant-exit export requires at least one --recipient key."
        )
    # The build requires the platform key (recipient_sets); the request only needs to
    # refuse a tenant key that IS the platform key, when one is configured.
    platform = _platform_recipient() if settings.BACKUP_AGE_RECIPIENT else None
    result = {}
    for raw in raw_recipients:
        try:
            canonical = canonical_recipient(raw)
        except ValidationError as exc:
            raise TenantDumpCustodyError(
                "A --recipient value is not a valid native age public key."
            ) from exc
        if canonical == platform:
            raise TenantDumpCustodyError(
                "The platform key cannot be a tenant recipient."
            )
        fingerprint = fingerprint_for(canonical)
        if fingerprint in result:
            raise TenantDumpCustodyError("A --recipient key was supplied twice.")
        result[fingerprint] = {"public_recipient": canonical, "fingerprint": fingerprint}
    return tuple(result[key] for key in sorted(result))


def recipient_sets(capture):
    """Derive envelope recipients without ever promoting the platform to DEK custody."""
    try:
        tenant_dek_recipients = tuple(
            item["public_recipient"] for item in capture.tenant_recipients
        )
    except (KeyError, TypeError):
        raise TenantDumpCustodyError(
            "The Lane D tenant recipient set is invalid."
        ) from None
    if not tenant_dek_recipients or len(tenant_dek_recipients) != len(
        set(tenant_dek_recipients)
    ):
        raise TenantDumpCustodyError("The Lane D tenant recipient set is invalid.")
    platform = _platform_recipient()
    if platform in tenant_dek_recipients:
        raise TenantDumpCustodyError(
            "The Lane D platform and tenant recipient identities overlap."
        )
    return TenantDumpRecipientSets(
        outer_recipients=(*tenant_dek_recipients, platform),
        tenant_dek_recipients=tenant_dek_recipients,
    )


def _platform_recipient():
    configured = settings.BACKUP_AGE_RECIPIENT
    if not configured:
        raise TenantDumpCustodyError(
            "The Lane D outer platform recipient is not configured."
        )
    try:
        return canonical_recipient(configured)
    except ValidationError:
        raise TenantDumpCustodyError(
            "The Lane D outer platform recipient is invalid."
        ) from None
