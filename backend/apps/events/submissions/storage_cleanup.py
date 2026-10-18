"""Delete every owned object version and multipart upload, then prove absence."""
from .errors import SubmissionError


def delete_keys(storage, keys):
    wanted = set(keys)
    try:
        for key in wanted:
            paginator = storage.client.get_paginator("list_object_versions")
            for page in paginator.paginate(Bucket=storage.bucket, Prefix=key):
                versions = [{"Key": v["Key"], "VersionId": v["VersionId"]}
                            for name in ("Versions", "DeleteMarkers") for v in page.get(name, []) if v["Key"] == key]
                for start in range(0, len(versions), 1000):
                    result = storage.client.delete_objects(Bucket=storage.bucket,
                        Delete={"Objects": versions[start:start + 1000], "Quiet": True})
                    if result.get("Errors"):
                        raise SubmissionError("storage_cleanup_pending", 503)
            storage.client.delete_object(Bucket=storage.bucket, Key=key)
            uploads = storage.client.get_paginator("list_multipart_uploads")
            for page in uploads.paginate(Bucket=storage.bucket, Prefix=key):
                for upload in page.get("Uploads", []):
                    if upload["Key"] == key:
                        storage.client.abort_multipart_upload(Bucket=storage.bucket, Key=key, UploadId=upload["UploadId"])
            # A normal delete in a versioned bucket creates a marker. Remove it
            # too and fail closed if any concurrent/new version remains.
            for page in paginator.paginate(Bucket=storage.bucket, Prefix=key):
                for marker in page.get("DeleteMarkers", []):
                    if marker["Key"] == key:
                        storage.client.delete_object(Bucket=storage.bucket, Key=key, VersionId=marker["VersionId"])
                if any(v["Key"] == key for v in page.get("Versions", [])):
                    raise SubmissionError("storage_cleanup_pending", 503)
            for page in uploads.paginate(Bucket=storage.bucket, Prefix=key):
                if any(v["Key"] == key for v in page.get("Uploads", [])):
                    raise SubmissionError("storage_cleanup_pending", 503)
    except SubmissionError:
        raise
    except Exception as exc:
        raise SubmissionError("storage_cleanup_pending", 503) from exc
