"""Explicit temporary-prefix qualification of copy and multipart primitives."""

from datetime import timedelta
import uuid

from botocore.exceptions import BotoCoreError, ClientError
from django.utils import timezone

from .contracts import CapabilityError
from .budget import checkpoint
from .deletion import delete_exact_key


def probe_object_operations(client, contract):
    bucket = contract.identity.bucket
    prefix = f"spaceworks-capability-probes/{uuid.uuid4().hex}/"
    source, copied, multipart = (prefix + name for name in ("source", "copy", "multipart"))
    keys = []
    upload_id = None
    facts = {}
    payload = uuid.uuid4().bytes
    try:
        if contract.copy is True:
            keys.extend((source, copied))
            checkpoint()
            client.put_object(Bucket=bucket, Key=source, Body=payload)
            checkpoint()
            client.copy_object(Bucket=bucket, Key=copied, CopySource={"Bucket": bucket, "Key": source})
            _assert_bytes(client, bucket, copied, payload)
            facts["copy"] = True
        if contract.multipart is True:
            keys.append(multipart)
            checkpoint()
            upload_id = client.create_multipart_upload(Bucket=bucket, Key=multipart)["UploadId"]
            checkpoint()
            part = client.upload_part(Bucket=bucket, Key=multipart, UploadId=upload_id,
                                      PartNumber=1, Body=payload)
            checkpoint()
            client.complete_multipart_upload(
                Bucket=bucket, Key=multipart, UploadId=upload_id,
                MultipartUpload={"Parts": [{"PartNumber": 1, "ETag": part["ETag"]}]},
            )
            upload_id = None
            _assert_bytes(client, bucket, multipart, payload)
            facts["multipart"] = True
    except CapabilityError:
        raise
    except (BotoCoreError, ClientError, KeyError, OSError):
        raise CapabilityError("storage_operation_probe_unknown") from None
    finally:
        cleanup_failed = False
        try:
            if upload_id is not None:
                checkpoint()
                client.abort_multipart_upload(Bucket=bucket, Key=multipart, UploadId=upload_id)
        except (BotoCoreError, ClientError):
            cleanup_failed = True
        for key in keys:
            try:
                delete_exact_key(client, bucket=bucket, key=key,
                                 never_versioned=contract.versioning == "never_versioned")
            except (BotoCoreError, ClientError):
                cleanup_failed = True
        if cleanup_failed:
            raise CapabilityError("storage_probe_cleanup_failed") from None
    return facts


def probe_object_lock(client, contract, *, mode, retention_seconds=60):
    """Explicit qualification leaves one intentionally locked test object.

    Return its exact locator/version/expiry for the operator's cleanup inventory.
    Never invoke this merely because an ordinary evidence bucket supports locks.
    """
    if mode not in {"COMPLIANCE", "GOVERNANCE"} or type(retention_seconds) is not int or not 60 <= retention_seconds <= 100 * 366 * 86400:
        raise CapabilityError("storage_object_lock_probe_invalid")
    if contract.object_lock is not True or contract.versioning != "enabled":
        raise CapabilityError("storage_object_lock_unavailable")
    bucket = contract.identity.bucket
    key = f"spaceworks-capability-probes/locked/{uuid.uuid4().hex}"
    until = (timezone.now() + timedelta(seconds=retention_seconds)).replace(microsecond=0)
    from apps.audit import services as audit

    audit.record(None, "storage.object_lock_probe_requested", target_type="storage_capabilities.probe", meta={
        "identity_fingerprint": contract.identity.fingerprint, "probe_key": key,
        "mode": mode, "retained_until": until.isoformat(),
    })
    try:
        checkpoint()
        response = client.put_object(
            Bucket=bucket, Key=key, Body=b"SpaceWorks Object Lock qualification",
            IfNoneMatch="*", ObjectLockMode=mode, ObjectLockRetainUntilDate=until,
        )
        version = response["VersionId"]
        checkpoint()
        retention = client.get_object_retention(Bucket=bucket, Key=key, VersionId=version)["Retention"]
        if retention.get("Mode") != mode or retention.get("RetainUntilDate") != until:
            raise CapabilityError("storage_object_lock_retention_mismatch")
        try:
            checkpoint()
            client.delete_object(Bucket=bucket, Key=key, VersionId=version)
        except ClientError as exc:
            # AWS answers AccessDenied; MinIO answers InvalidRequest ("Object is WORM
            # protected"). The head_object below still proves the version survived.
            if exc.response.get("Error", {}).get("Code") not in {"AccessDenied", "InvalidRequest"}:
                raise
        else:
            raise CapabilityError("storage_object_lock_delete_not_denied")
        checkpoint()
        client.head_object(Bucket=bucket, Key=key, VersionId=version)
    except (BotoCoreError, ClientError, KeyError):
        raise CapabilityError("storage_object_lock_unproven") from None
    return {"object_lock": True, "lock_probe_key": key, "lock_probe_version": version,
            "lock_probe_mode": mode, "lock_probe_retained_until": until.isoformat(),
            "lock_probe_retention_seconds": retention_seconds}


def _assert_bytes(client, bucket, key, expected):
    checkpoint()
    body = client.get_object(Bucket=bucket, Key=key)["Body"]
    try:
        if body.read(len(expected) + 1) != expected:
            raise CapabilityError("storage_operation_readback_mismatch")
    finally:
        body.close()
