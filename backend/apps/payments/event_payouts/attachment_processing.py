"""Leased validation outside database transactions, exact-version promotion."""
from datetime import timedelta
from hashlib import sha256
from uuid import uuid4
from django.utils import timezone
from apps.audit.services import record
from apps.makerspaces.private_upload_transport import PrivateTransportError
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from .attachment_models import FinanceAttachment
from .attachment_storage import FinanceStorage, asset_bucket
from .attachment_content import ContentError, validate, scan
from .worker_boundary import locked_asset
from .errors import require


def complete_locked(row, *, generation, actor):
    require(row.generation == generation, "attachment_generation_changed")
    if row.state in ("uploaded", "validating", "ready", "attached"):
        return row
    require(row.state == "initiated" and timezone.now() < row.created_at + timedelta(hours=24), "upload_expired")
    row.state, row.version = "uploaded", row.version + 1
    row.save(update_fields=["state", "version"])
    record(actor, "finance.attachment.upload_completed", makerspace=row.makerspace, target=row,
           meta={"asset_id": row.pk, "generation": generation})
    return row


def process(asset_id, *, storage=None):
    storage = storage or FinanceStorage(bucket_name=asset_bucket(asset_id))
    seed = FinanceAttachment.objects.get(pk=asset_id)
    # Hold the source lock-only boundary across I/O; no DB row lock across I/O.
    with boundary_tenant_write(seed.makerspace_id):
        token, now = uuid4(), timezone.now()
        from .scan_policy import current
        policy = current()
        with locked_asset(asset_id) as (row, obligation):
            if row.state not in ("uploaded", "validating") or row.lease_until and row.lease_until > now:
                return False
            if row.created_at + timedelta(hours=24) <= now:
                return False
            row.state, row.lease_token, row.lease_until = "validating", token, now + timedelta(minutes=5)
            row.scanner_policy = policy.backend
            row.attempts, row.version = row.attempts + 1, row.version + 1
            row.save()
            record(None, "finance.attachment.validation_started", makerspace=row.makerspace, target=row,
                   meta={"asset_id": row.pk, "generation": row.generation})
        try:
            head = storage.head(row.staging_key, row.staging_version_id or None)
            if head["ContentLength"] != row.expected_bytes:
                raise ContentError("upload_size_mismatch", 413)
            # Pin the server-observed source version before any long validation.
            # For a non-versioned store IfMatch protects the exact read below.
            with locked_asset(asset_id) as (fresh, obligation):
                require(fresh.state == "validating" and fresh.lease_token == token, "upload_lease_changed")
                fresh.staging_version_id = head.get("VersionId", "")
                fresh.version += 1
                fresh.save(update_fields=["staging_version_id", "version"])
            data = storage.read(row.staging_key, version=head.get("VersionId"), etag=head["ETag"], maximum=row.expected_bytes)
            if len(data) != row.expected_bytes:
                raise ContentError("upload_size_mismatch", 413)
            mime = validate(data, declared_mime=row.declared_mime, purpose=row.purpose)
            result = scan(data, backend=policy.backend, host=policy.host, port=policy.port)
            if result.status == "infected":
                raise ContentError("file_infected")
            digest = sha256(data).hexdigest()
            version = storage.promote(key=row.object_key, data=data, mime=mime, digest=digest)
        except (ContentError, PrivateTransportError) as exc:
            with locked_asset(asset_id) as (fresh, obligation):
                if fresh.lease_token != token or fresh.state != "validating":
                    return False
                retry = exc.status == 503
                fresh.state, fresh.error_code = ("uploaded" if retry else "failed"), exc.code
                fresh.scan_status = "infected" if exc.code == "file_infected" else "failed"
                fresh.lease_until = timezone.now() + timedelta(minutes=min(60, 2 ** min(fresh.attempts, 6))) if retry else None
                fresh.version += 1
                fresh.save()
                record(None, "finance.attachment.validation_failed", makerspace=fresh.makerspace, target=fresh,
                    meta={"asset_id": fresh.pk, "code": exc.code, "retry": retry})
            return False
        with locked_asset(asset_id) as (fresh, obligation):
            require(fresh.lease_token == token and fresh.state == "validating"
                and fresh.lease_until > timezone.now(), "upload_lease_changed")
            duplicate = FinanceAttachment.objects.filter(makerspace_id=fresh.makerspace_id,
                binding_uuid=fresh.binding_uuid, sha256=digest, state__in=("ready", "attached")).exclude(pk=fresh.pk).exists()
            fresh.actual_bytes, fresh.canonical_mime, fresh.sha256 = len(data), mime, digest
            fresh.final_version_id, fresh.scan_status, fresh.scanner_version = version, result.status, result.version
            fresh.state, fresh.error_code = ("failed", "receipt_duplicate") if duplicate else ("ready", "")
            fresh.lease_token = fresh.lease_until = None
            fresh.version += 1
            fresh.save()
            record(None, "finance.attachment.ready" if not duplicate else "finance.attachment.duplicate",
                makerspace=fresh.makerspace, target=fresh, meta={"asset_id": fresh.pk, "generation": fresh.generation})
        return not duplicate
