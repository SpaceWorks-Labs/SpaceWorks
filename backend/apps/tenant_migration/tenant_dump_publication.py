"""Irreversible Lane D publication of a sealed tenant-exit artifact."""

import hashlib
import hmac
import secrets
from datetime import timedelta
from pathlib import Path

from .cloud_audit_guard import capture_scope
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.audit.batches import _scope_lock as acquire_audit_scope_lock
from apps.backup import storage
from apps.backup.digests import sha256_file
from apps.makerspaces.models import Makerspace

from .models import TenantDumpCapture
from .tenant_dump_audit_anchors import prove_no_external_anchor
from .tenant_dump_errors import (
    TenantDumpBuildError,
    TenantDumpPublicationRefused,
    TenantDumpVerificationError,
)
from .money_digest import MoneyDriftRefused, assert_money_unchanged
from .tenant_dump_lineage import verify_artifact_lineage
from .tenant_dump_outer_artifact import read_outer_manifest
from .tenant_dump_staging import delete_owned_root


def register_unpublished_artifact(capture_id, encrypted_path):
    """Upload sealed bytes under a non-discoverable key for final publication."""
    encrypted_path = Path(encrypted_path)
    outer_manifest = read_outer_manifest(encrypted_path)
    if (
        outer_manifest["artifact_id"] != str(capture_id)
        or outer_manifest["capture_id"] != str(capture_id)
    ):
        raise TenantDumpBuildError(
            "The readable Lane D outer manifest names another capture."
        )
    try:
        size = encrypted_path.stat().st_size
        digest = sha256_file(encrypted_path)
    except OSError as exc:
        raise TenantDumpBuildError("The sealed Lane D artifact is unavailable.") from exc
    if size <= 0:
        raise TenantDumpBuildError("The sealed Lane D artifact is empty.")
    if not TenantDumpCapture.objects.filter(
        pk=capture_id,
        status=TenantDumpCapture.Status.PENDING_PUBLICATION,
    ).exists():
        raise TenantDumpBuildError("The Lane D capture is not pending publication.")
    key = f"tenant-dumps/unpublished/{capture_id}.tar.age"
    storage.upload_archive(key, encrypted_path)
    try:
        with transaction.atomic():
            capture = TenantDumpCapture.objects.select_for_update().get(pk=capture_id)
            if capture.status != TenantDumpCapture.Status.PENDING_PUBLICATION:
                raise TenantDumpBuildError(
                    "The Lane D capture is not pending publication."
                )
            capture.unpublished_object_key = key
            capture.artifact_sha256 = digest
            capture.artifact_size_bytes = size
            capture.save(
                update_fields=(
                    "unpublished_object_key",
                    "artifact_sha256",
                    "artifact_size_bytes",
                    "updated_at",
                )
            )
    except Exception:
        _discard_failed_registration(capture_id, key)
        raise
    return key, digest


@capture_scope
def publish_tenant_dump(capture_id):
    """Atomically expose bytes and create their single-use download state."""
    raw_token = secrets.token_urlsafe(32)
    refusal = ""
    with transaction.atomic():
        makerspace = Makerspace.objects.select_for_update().get(
            pk=_makerspace_id(capture_id)
        )
        acquire_audit_scope_lock(makerspace.pk)
        prove_no_external_anchor(makerspace.pk)
        capture = TenantDumpCapture.objects.select_for_update().get(pk=capture_id)
        if capture.status != TenantDumpCapture.Status.PENDING_PUBLICATION:
            raise TenantDumpBuildError("The Lane D capture is not pending publication.")
        try:
            _verify_publication_lineage(capture)
            # Pending charges travel in the artifact now, and the capture REOPENED
            # the source -- so between the freeze and this moment the space may have
            # settled a captured debt or raised a new one. Publishing then would hand
            # out an artifact that bills a member for money already taken. This is
            # the last source-side moment before the bytes become fetchable, and it
            # runs under the same makerspace row lock.
            assert_money_unchanged(capture)
        except TenantDumpPublicationRefused as exc:
            refusal = str(exc)
            _refuse_locked(capture, refusal, "lineage_mismatch")
        except MoneyDriftRefused as exc:
            refusal = str(exc)
            _refuse_locked(capture, refusal, "money_drift")
        else:
            if not capture.unpublished_object_key or not capture.artifact_sha256:
                raise TenantDumpBuildError(
                    "The Lane D artifact has no sealed unpublished bytes."
                )
            now = timezone.now()
            capture.status = TenantDumpCapture.Status.PUBLISHED
            capture.object_key = capture.unpublished_object_key
            capture.unpublished_object_key = ""
            capture.download_token_digest = _token_digest(raw_token)
            capture.download_token_expires_at = now + timedelta(
                seconds=settings.BACKUP_DOWNLOAD_TTL_SECONDS
            )
            capture.download_token_consumed_at = None
            capture.published_at = now
            capture.save()
            audit.record(
                capture.requested_by,
                "tenant_migration.tenant_dump_published",
                makerspace=capture.makerspace,
                target=capture,
                meta={
                    "artifact_sha256": capture.artifact_sha256,
                    "artifact_size_bytes": capture.artifact_size_bytes,
                    "recipient_fingerprints": [
                        item["fingerprint"]
                        for item in capture.tenant_recipients
                    ],
                },
            )
            transaction.on_commit(
                lambda cid=capture.pk: _delete_capture_staging(cid),
                robust=True,
            )
    if refusal:
        raise TenantDumpPublicationRefused(refusal)
    return TenantDumpCapture.objects.get(pk=capture_id), raw_token


def _verify_publication_lineage(capture):
    if (
        capture.parent_database_sha256 != capture.database_image_sha256
        or capture.parent_object_ledger_sha256 != capture.object_ledger_sha256
    ):
        raise TenantDumpPublicationRefused(
            "The Lane D artifact parent lineage no longer matches its capture."
        )
    try:
        verify_artifact_lineage(capture, capture.manifest)
    except TenantDumpVerificationError as exc:
        raise TenantDumpPublicationRefused(
            "The Lane D artifact lineage verification failed."
        ) from exc


def _refuse_locked(capture, detail, code):
    if capture.status == TenantDumpCapture.Status.PUBLISHED:
        raise TenantDumpPublicationRefused("A published Lane D capture is immutable.")
    unpublished_key = capture.unpublished_object_key
    capture.status = TenantDumpCapture.Status.REFUSED
    capture.refusal_code = code
    capture.refusal_detail = detail[:500]
    capture.download_token_digest = ""
    capture.download_token_expires_at = None
    capture.save()
    audit.record(
        capture.requested_by,
        "tenant_migration.tenant_dump_publication_refused",
        makerspace=capture.makerspace,
        target=capture,
        meta={"reason_code": code, "detail": detail[:500]},
    )
    transaction.on_commit(
        lambda key=unpublished_key, cid=capture.pk: _delete_unpublished(key, cid),
        robust=True,
    )


def _delete_unpublished(key, capture_id):
    deleted = not key or storage.delete_archive(key)
    if deleted and key:
        TenantDumpCapture.objects.filter(
            pk=capture_id,
            status=TenantDumpCapture.Status.REFUSED,
            unpublished_object_key=key,
        ).update(unpublished_object_key="", updated_at=timezone.now())
    _delete_capture_staging(capture_id)


def _discard_failed_registration(capture_id, key):
    """Delete an unregistered upload or durably journal it for retry."""
    with transaction.atomic():
        capture = TenantDumpCapture.objects.select_for_update().get(pk=capture_id)
        if capture.status == TenantDumpCapture.Status.PUBLISHED:
            return
        if storage.delete_archive(key):
            return
        capture.status = TenantDumpCapture.Status.FAILED
        capture.unpublished_object_key = key
        capture.refusal_code = "artifact_registration_failed"
        capture.refusal_detail = (
            "The unpublished artifact could not be registered or deleted."
        )
        capture.save()
        audit.record(
            capture.requested_by,
            "tenant_migration.tenant_dump_artifact_cleanup_required",
            makerspace=capture.makerspace,
            target=capture,
            meta={"object_key": key},
        )


def _delete_capture_staging(capture_id):
    try:
        delete_owned_root(capture_id)
    except (FileNotFoundError, RuntimeError):
        return


def _makerspace_id(capture_id):
    return TenantDumpCapture.objects.only("makerspace_id").get(pk=capture_id).makerspace_id


def _token_digest(raw_token):
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
