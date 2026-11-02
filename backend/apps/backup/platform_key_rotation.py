"""Platform key rotation (release 2 L11, BK-68; superadmin only).

The operator rotates a key on the HOST: a new ``BACKUP_AGE_RECIPIENT`` (platform key) or
a new ``TENANT_MIGRATION_AGE_RECIPIENT`` + identity (this server's restore key), then
records the rotation here (``/control/`` behind re-authentication, or
``manage.py backup_keys rotate``). Recording retires every earlier fingerprint of that
kind (the previously current one, plus any a retained archive is still encrypted to),
and ``assert_not_retired`` refuses a retired key for every later build, so an old key
is never used again. Retained archives still encrypted to a retired key are listed;
the operator re-encrypts them (``archive_reencrypt``) or purges them.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.audit import services as audit

from .age_recipients import PLATFORM_RECIPIENT_LABEL, SERVER_RECIPIENT_LABEL, canonical_recipient, fingerprint_for
from .build_errors import BackupBuildError
from .models import BackupArchive
from .models_keys import BackupKeyFingerprint

Kind = BackupKeyFingerprint.Kind
SETTING = {Kind.PLATFORM: "BACKUP_AGE_RECIPIENT", Kind.SERVER: "TENANT_MIGRATION_AGE_RECIPIENT"}
LABEL = {PLATFORM_RECIPIENT_LABEL: Kind.PLATFORM, SERVER_RECIPIENT_LABEL: Kind.SERVER}


class KeyRotationError(APIException):
    status_code = 409
    default_code = "key_rotation_refused"

    def __init__(self, code, detail):
        super().__init__({"detail": detail, "code": code}, code)
        self.code = code


def fingerprint_of(recipient):
    try:
        return fingerprint_for(canonical_recipient(recipient))
    except ValidationError:
        return fingerprint_for(str(recipient).strip())


def current_fingerprint(kind):
    value = getattr(settings, SETTING[kind], "") or ""
    return fingerprint_of(value) if value else None


def archive_fingerprints(row):
    """{kind: {fingerprint}} an archive is encrypted to, from its recorded manifest."""
    found = {Kind.PLATFORM: set(), Kind.SERVER: set()}
    manifest = row.manifest or {}
    for item in manifest.get("recipients") or ():
        kind = LABEL.get(item.get("label"))
        if kind and item.get("public_recipient"):
            found[kind].add(fingerprint_of(item["public_recipient"]))
    _collect_outer(manifest, found[Kind.PLATFORM])
    return found


def _collect_outer(value, into):
    # A deployment archive's signed outer manifest names only platform fingerprints.
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "recipient_fingerprints" and isinstance(item, list):
                into.update(str(entry) for entry in item)
            else:
                _collect_outer(item, into)
    elif isinstance(value, list):
        for item in value:
            _collect_outer(item, into)


def retired(kind):
    return set(BackupKeyFingerprint.objects.filter(kind=kind, retired_at__isnull=False)
               .values_list("fingerprint", flat=True))


def assert_not_retired(selected):
    """Refuse a build to a key that has been rotated out (called by the archive builder)."""
    for item in selected:
        kind = LABEL.get(item.get("label"))
        if kind and fingerprint_of(item["public_recipient"]) in retired(kind):
            raise BackupBuildError(
                f"{SETTING[kind]} names a key that was rotated out; configure a new key before backing up.")


def stale_archives():
    """Available archives still encrypted to a retired fingerprint, newest first."""
    gone = {kind: retired(kind) for kind in Kind.values}
    rows = BackupArchive.objects.filter(status=BackupArchive.Status.AVAILABLE).order_by("-created_at")
    return [row for row in rows.iterator() if any(found & gone[kind] for kind, found in archive_fingerprints(row).items())]


@transaction.atomic
def record_rotation(actor, kind):
    _require_superadmin(actor)
    kind = Kind(kind)
    current = current_fingerprint(kind)
    if current is None:
        raise KeyRotationError("key_missing", f"{SETTING[kind]} is not configured.")
    rows = BackupKeyFingerprint.objects.select_for_update().filter(kind=kind)
    if rows.filter(fingerprint=current, retired_at__isnull=False).exists():
        raise KeyRotationError("key_reused", "This key was rotated out before; a retired key is never reused.")
    previous = set(rows.filter(retired_at__isnull=True).exclude(fingerprint=current).values_list("fingerprint", flat=True))
    for row in BackupArchive.objects.filter(status=BackupArchive.Status.AVAILABLE).iterator():
        previous |= archive_fingerprints(row)[kind] - {current}
    if not previous:
        raise KeyRotationError("key_unchanged", "No earlier key is known; change the configured key first.")
    now = timezone.now()
    for fingerprint in sorted(previous):
        row, _ = BackupKeyFingerprint.objects.get_or_create(kind=kind, fingerprint=fingerprint)
        if row.retired_at is None:
            row.retired_at, row.retired_by = now, actor
            row.save(update_fields=["retired_at", "retired_by"])
    BackupKeyFingerprint.objects.get_or_create(kind=kind, fingerprint=current)
    stale = len(stale_archives())
    audit.record(actor, "backup.platform_key_rotated", meta={
        "kind": kind.value, "new_fingerprint": current, "retired_count": len(previous), "stale_archives": stale,
    })
    return {"kind": kind.value, "fingerprint": current, "retired": sorted(previous), "stale_archives": stale}


def _require_superadmin(actor):
    from apps.tenant_migration.services_import_job import _require_superadmin as require

    require(actor)
