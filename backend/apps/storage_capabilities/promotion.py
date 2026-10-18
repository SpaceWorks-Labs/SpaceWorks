"""Create-only promotion from a bounded immutable snapshot, never HEAD then PUT."""

import hashlib
import hmac
import tempfile

from botocore.exceptions import ClientError

from .contracts import CapabilityError
from .budget import checkpoint
from .runtime import require_capability

CHUNK_SIZE = 1024 * 1024


def promote(client, *, source_bucket, source_key, destination_bucket, destination_key,
            max_bytes, content_type=None, validate=None, expected_etag=None):
    """Spool privately, validate that snapshot, then atomically create the final.

    Caller supplies scratch admission/lease fencing before invoking this helper.
    A version or ETag pins staging. The stream is bounded even if HEAD is wrong.
    No whole object is held in memory; no StreamingBody reaches put_object.
    """
    if type(max_bytes) is not int or max_bytes < 1:
        raise CapabilityError("storage_promotion_limit_invalid")
    require_capability(client, destination_bucket, "conditional_create")
    params = {"Bucket": source_bucket, "Key": source_key}
    checkpoint()
    head = client.head_object(**params)
    if not 1 <= head["ContentLength"] <= max_bytes:
        raise CapabilityError("storage_promotion_size_invalid")
    if expected_etag is not None and head.get("ETag") != expected_etag:
        raise CapabilityError("storage_staging_changed")
    if head.get("VersionId") and head["VersionId"] != "null":
        params["VersionId"] = head["VersionId"]
    elif head.get("ETag"):
        params["IfMatch"] = head["ETag"]
    else:
        raise CapabilityError("storage_staging_snapshot_unavailable")
    checkpoint()
    response = client.get_object(**params)
    body = response["Body"]
    size = 0
    digest = hashlib.sha256()
    try:
        with tempfile.TemporaryFile(prefix="spaceworks-promote-") as spool:
            while chunk := body.read(min(CHUNK_SIZE, max_bytes - size + 1)):
                checkpoint()
                size += len(chunk)
                if size > max_bytes:
                    raise CapabilityError("storage_promotion_size_invalid")
                spool.write(chunk)
                digest.update(chunk)
            if size != head["ContentLength"]:
                raise CapabilityError("storage_staging_changed")
            body.close()
            spool.seek(0)
            validated_mime = None
            if validate is not None:
                validated_mime = validate(spool, size)
                spool.seek(0)
            mime = validated_mime or content_type or response.get("ContentType", "application/octet-stream")
            try:
                checkpoint()
                written = client.put_object(
                    Bucket=destination_bucket, Key=destination_key, Body=spool,
                    ContentLength=size, ContentType=mime, IfNoneMatch="*",
                    Metadata=response.get("Metadata", {}),
                )
            except ClientError as exc:
                if (exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") in {409, 412}
                    or exc.response.get("Error", {}).get("Code") in {"PreconditionFailed", "ConditionalRequestConflict"}):
                    raise CapabilityError("storage_final_already_exists") from None
                raise
        checkpoint()
        final_params = {"Bucket": destination_bucket, "Key": destination_key}
        if written.get("VersionId") and written["VersionId"] != "null":
            final_params["VersionId"] = written["VersionId"]
        final_body = client.get_object(**final_params)["Body"]
        final_size = 0
        final_digest = hashlib.sha256()
        try:
            while chunk := final_body.read(min(CHUNK_SIZE, size - final_size + 1)):
                checkpoint()
                final_size += len(chunk)
                if final_size > size:
                    raise CapabilityError("storage_promotion_readback_mismatch")
                final_digest.update(chunk)
        finally:
            final_body.close()
        if final_size != size or not hmac.compare_digest(final_digest.digest(), digest.digest()):
            raise CapabilityError("storage_promotion_readback_mismatch")
        return {"size": size, "sha256": digest.hexdigest(), "content_type": mime}
    finally:
        body.close()
