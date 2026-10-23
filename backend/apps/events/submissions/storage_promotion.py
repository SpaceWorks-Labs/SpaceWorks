"""Immutable final creation and crash reconciliation; never presign these keys."""
from .errors import SubmissionError
from .storage import FrozenObject, DEFAULT_PART


def existing(storage, key):
    try:
        row = storage.client.head_object(Bucket=storage.bucket, Key=key)
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise SubmissionError("storage_unavailable", 503) from exc
    return FrozenObject(key, row["ContentLength"], row["ETag"], row.get("VersionId"))


def promote(storage, *, source, target_key, sha256, canonical_bytes=None, mime):
    prior = existing(storage, target_key)
    if prior:
        if storage.digest(prior) != sha256:
            raise SubmissionError("final_key_collision", 409)
        return prior
    upload_id = None
    try:
        if canonical_bytes is not None:
            storage.client.put_object(Bucket=storage.bucket, Key=target_key, Body=canonical_bytes,
                ContentType=mime, IfNoneMatch="*", Metadata={"sha256": sha256})
        else:
            result = storage.client.create_multipart_upload(Bucket=storage.bucket, Key=target_key,
                ContentType=mime, Metadata={"sha256": sha256})
            upload_id = result["UploadId"]
            parts = []
            copy_source = {"Bucket": storage.bucket, "Key": source.key}
            if source.version_id:
                copy_source["VersionId"] = source.version_id
            for number, start in enumerate(range(0, source.size, DEFAULT_PART), 1):
                response = storage.client.upload_part_copy(Bucket=storage.bucket, Key=target_key,
                    UploadId=upload_id, PartNumber=number, CopySource=copy_source,
                    CopySourceIfMatch=source.etag,
                    CopySourceRange=f"bytes={start}-{min(start + DEFAULT_PART, source.size) - 1}")
                parts.append({"PartNumber": number, "ETag": response["CopyPartResult"]["ETag"]})
            storage.client.complete_multipart_upload(Bucket=storage.bucket, Key=target_key,
                UploadId=upload_id, MultipartUpload={"Parts": parts}, IfNoneMatch="*")
        result = storage.head(target_key)
        if storage.digest(result) != sha256:
            raise SubmissionError("final_checksum_mismatch", 409)
        return result
    except SubmissionError:
        raise
    except Exception as exc:
        raise SubmissionError("storage_unavailable", 503) from exc
    finally:
        if upload_id:
            try:
                storage.client.abort_multipart_upload(Bucket=storage.bucket, Key=target_key, UploadId=upload_id)
            except Exception:
                # Cleanup enumerates multipart uploads for every owned prefix; a
                # crash/failed abort must never cause reservation release.
                pass
