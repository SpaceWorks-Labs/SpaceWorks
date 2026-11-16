"""Immutable private ciphertext with primary-DB locators and deletion receipts.

An upload intent commits before remote I/O. A crash cannot lose its cleanup key.
Only a digest-verified upload becomes readable; retries use a fresh attempt key.
"""
from contextlib import contextmanager
from datetime import timedelta
from dataclasses import asdict
import hashlib
from pathlib import Path
import tempfile
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.backup import storage
from apps.backup.digests import sha256_file
from apps.audit.services import record
from apps.storage_capabilities import capabilities_for
from .models_staging import ManagedStagedObject

PREFIX = "cloud-stage:"


def is_locator(value):
    return str(value).startswith(PREFIX)


def _row(locator):
    try:
        return ManagedStagedObject.objects.get(pk=uuid.UUID(str(locator).removeprefix(PREFIX)))
    except (ValueError, ManagedStagedObject.DoesNotExist):
        raise ValueError("The private staging locator is invalid.") from None


def _client(row=None):
    client = storage.private_client()
    contract = capabilities_for(client, settings.AWS_STORAGE_BUCKET_NAME, required=True, role="private")
    identity = asdict(contract.identity)
    if row is not None and row.identity != identity:
        client.close()
        raise ValueError("The staging bucket identity changed; use its retained migration inventory.")
    return client, identity


def store(path, *, owner, label, expires_at=None):
    from apps.operations.cloud_runtime import writer
    from apps.operations.cloud_quotas.storage import reserve_upload, finalized_upload
    path = Path(path)
    size, digest = path.stat().st_size, sha256_file(path)
    if size < 1:
        raise ValueError("Private staged ciphertext cannot be empty.")
    if settings.SPACEWORKS_DEPLOYMENT_PROFILE == "free" and size > settings.FREE_MAX_PROMOTION_BYTES:
        raise ValueError("This ciphertext requires an external export job.")
    with writer("job") as check:
        client, identity = _client()
        try:
            from apps.storage_capabilities.runtime import require_capability
            require_capability(client, settings.AWS_STORAGE_BUCKET_NAME, "conditional_create", role="private")
            row_id, attempt = uuid.uuid4(), uuid.uuid4()
            with transaction.atomic():
                row = ManagedStagedObject.objects.create(
                    id=row_id, owner=owner, label=label, attempt=attempt, identity=identity,
                    object_key=f"managed-staging/{owner}/{row_id}/{attempt}.age",
                    expires_at=expires_at or timezone.now() + timedelta(days=7), size=size, sha256=digest,
                )
                record(None, "deployment.staging_created", target=row, meta={"stage_id": str(row.pk)})
            reserve_upload(client, bucket=settings.AWS_STORAGE_BUCKET_NAME, key=row.object_key,
                           max_bytes=size, ttl=60, server_owned=True)
            check()
            with path.open("rb") as source:
                client.put_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=row.object_key,
                                  Body=source, ContentLength=size, IfNoneMatch="*",
                                  ContentType="application/octet-stream")
            check()
            _download(client, row, None)
            finalized_upload(client, bucket=settings.AWS_STORAGE_BUCKET_NAME, key=row.object_key,
                             size=size, operation_key=str(row.id))
            check()
            with transaction.atomic():
                if not ManagedStagedObject.objects.filter(pk=row.id, available=False, delete_requested_at=None).update(available=True):
                    raise ValueError("The staging attempt was retired during upload.")
                record(None, "deployment.staging_available", target=row, meta={"stage_id": str(row.pk)})
            return PREFIX + str(row.id)
        finally:
            client.close()


def _download(client, row, destination):
    from apps.operations.cloud_runtime import check
    response = client.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=row.object_key)
    body, digest, size = response["Body"], hashlib.sha256(), 0
    output = destination.open("xb") if destination is not None else None
    try:
        while chunk := body.read(1024 * 1024):
            check()
            size += len(chunk)
            if size > row.size:
                raise ValueError("Staged ciphertext exceeds its immutable size.")
            digest.update(chunk)
            if output:
                output.write(chunk)
        if size != row.size or digest.hexdigest() != row.sha256:
            raise ValueError("Staged ciphertext failed its digest check.")
    finally:
        body.close()
        if output:
            output.close()


@contextmanager
def materialize(value):
    if not is_locator(value):
        yield Path(value)
        return
    row = _row(value)
    if not row.available or row.deleted_at or row.delete_requested_at or row.expires_at <= timezone.now():
        raise ValueError("The staged ciphertext is unavailable or expired.")
    client, _identity = _client(row)
    try:
        with tempfile.TemporaryDirectory(prefix="spaceworks-stage-") as directory:
            path = Path(directory, "payload.age")
            _download(client, row, path)
            path.chmod(0o600)
            yield path
    finally:
        client.close()


def latest(owner, label):
    row = ManagedStagedObject.objects.filter(owner=owner, label=label, available=True, selected=True,
        delete_requested_at=None, deleted_at=None, expires_at__gt=timezone.now()).order_by("-created_at").first()
    return PREFIX + str(row.id) if row else None


def select(locator):
    row = _row(locator)
    if not ManagedStagedObject.objects.filter(pk=row.pk, available=True,
            delete_requested_at=None, deleted_at=None, expires_at__gt=timezone.now()).update(selected=True):
        raise ValueError("The staged ciphertext cannot be selected.")


def retire(locator):
    ManagedStagedObject.objects.filter(pk=_row(locator).pk, delete_requested_at=None).update(delete_requested_at=timezone.now())


def retire_owner(owner):
    with transaction.atomic():
        count = ManagedStagedObject.objects.filter(owner=owner, delete_requested_at=None).update(delete_requested_at=timezone.now())
        if count:
            record(None, "deployment.staging_retired", meta={"count": count})


def cleanup(*, limit=5, check=lambda: None):
    from django.db.models import Q
    from apps.object_storage import delete_all_versions
    now = timezone.now()
    rows = ManagedStagedObject.objects.filter(Q(expires_at__lte=now) |
        Q(delete_requested_at__isnull=False)).filter(Q(retry_at=None) | Q(retry_at__lte=now)).order_by("retry_at", "created_at")[:limit]
    deleted = 0
    for row in rows:
        check()
        client = None
        try:
            client, bucket, retired = cleanup_client(row)
            # Receipts survive and are re-deleted: a late in-flight PUT cannot resurrect bytes.
            if retired is None:
                delete_all_versions(client, bucket=bucket, key=row.object_key, operation_key="managed-stage-delete:" + str(row.pk))
            else:
                from apps.storage_capabilities.deletion import delete_exact_key
                delete_exact_key(client, bucket=bucket, key=row.object_key, never_versioned=retired)
            check()
            ManagedStagedObject.objects.filter(pk=row.pk).update(deleted_at=timezone.now(), retry_at=now + timedelta(minutes=360))
            record(None, "deployment.staging_deleted", target=row, meta={"stage_id": str(row.pk)})
            deleted += 1
        except Exception:
            ManagedStagedObject.objects.filter(pk=row.pk).update(retry_at=now + timedelta(minutes=720))
        finally:
            if client is not None:
                client.close()
    return deleted


def cleanup_client(row):
    from apps.operations.models import CloudStorageMigrationReceipt, StorageCapabilityState
    from apps.storage_capabilities.contracts import fingerprint
    identity = fingerprint(row.identity)
    migration = CloudStorageMigrationReceipt.objects.filter(source_identity=identity).order_by("pk").first()
    if migration is None:
        client, _identity = _client(row)
        return client, settings.AWS_STORAGE_BUCKET_NAME, None
    from apps.backup.offsite_client import destination_client
    from apps.storage_capabilities.runtime import client_identity
    from apps.storage_capabilities.configuration import _contract
    from apps.storage_capabilities.probes import inspect_bucket
    client = destination_client(migration.retired_destination)
    try:
        bucket = migration.retired_destination.bucket
        if client_identity(client, bucket).fingerprint != identity:
            raise ValueError("Retired staging identity mismatch.")
        contract = _contract(migration.source_contract, allow_no_upload=True)
        inspect_bucket(client, contract)
        state = StorageCapabilityState.objects.get(identity_fingerprint=identity)
        return client, bucket, not state.history_possible and contract.versioning == "never_versioned"
    except BaseException:
        client.close()
        raise


def cleanup_chunk(context):
    from apps.operations.cloud_jobs.contracts import ChunkResult
    from apps.storage_capabilities.budget import storage_budget
    with storage_budget(deadline=context.deadline, check_active=context.check):
        count = cleanup(limit=min(5, context.limit), check=context.check)
    context.check()
    return ChunkResult(count < min(5, context.limit), {}, count)
