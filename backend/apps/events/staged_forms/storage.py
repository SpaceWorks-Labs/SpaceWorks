"""Private S3 adapter for the existing model-free transport seam; no ORM."""
from datetime import datetime, UTC
import hashlib
from django.conf import settings
from apps.makerspaces.private_upload_transport import ObjectLocator, UploadDescriptor, PrivateTransportError


def storage():
    import boto3
    from botocore.config import Config
    options = dict(aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
        config=Config(signature_version=settings.AWS_S3_SIGNATURE_VERSION,
            s3={"addressing_style": settings.AWS_S3_ADDRESSING_STYLE}, connect_timeout=2, read_timeout=2,
            retries={"max_attempts": 0}))
    return StageStorage(boto3.client("s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL, **options),
        boto3.client("s3", endpoint_url=settings.AWS_S3_PUBLIC_ENDPOINT_URL, **options), settings.AWS_STORAGE_BUCKET_NAME)


class StageStorage:
    def __init__(self, client, browser_client, bucket):
        self.client, self.browser_client, self.bucket = client, browser_client, bucket

    def initialize(self, request):
        seconds = min(900, int((request.not_after - datetime.now(UTC)).total_seconds()))
        if seconds <= 0:
            raise PrivateTransportError("asset_expired", 410)
        try:
            value = self.browser_client.generate_presigned_post(Bucket=self.bucket, Key=request.staging.key,
                Fields={"Content-Type": request.mime}, Conditions=[{"Content-Type": request.mime},
                    ["content-length-range", request.size_bytes, request.size_bytes]], ExpiresIn=seconds)
        except Exception as exc:
            raise PrivateTransportError("storage_unavailable", 503) from exc
        return UploadDescriptor(method="POST", url=value["url"], fields=value["fields"],
                                expires_at=request.not_after, generation=request.generation)

    def read_uploaded(self, asset):
        try:
            head = self.client.head_object(Bucket=self.bucket, Key=asset.staging_key)
            if head["ContentLength"] != asset.expected_bytes or head.get("ContentType") != asset.declared_mime:
                raise PrivateTransportError("stage_file_size_mismatch", 400)
            version = head.get("VersionId")
            kwargs = {"VersionId": version} if version else {"IfMatch": head["ETag"]}
            result = self.client.get_object(Bucket=self.bucket, Key=asset.staging_key, **kwargs)
            body = result["Body"]
            try:
                data = body.read(asset.expected_bytes + 1)
            finally:
                body.close()
            if len(data) != asset.expected_bytes:
                raise PrivateTransportError("stage_file_size_mismatch", 400)
            return data, version or ""
        except PrivateTransportError:
            raise
        except Exception as exc:
            raise PrivateTransportError("storage_unavailable", 503) from exc

    def promote_bytes(self, asset, data, sha256):
        try:
            try:
                value = self.client.put_object(Bucket=self.bucket, Key=asset.object_key, Body=data,
                    ContentType=asset.declared_mime, IfNoneMatch="*", Metadata={"sha256": sha256})
                return value.get("VersionId", "")
            except Exception as exc:
                if getattr(exc, "response", {}).get("Error", {}).get("Code") not in ("PreconditionFailed", "412"):
                    raise
                value = self.client.get_object(Bucket=self.bucket, Key=asset.object_key)
                body = value["Body"]
                try:
                    prior = body.read(asset.expected_bytes + 1)
                finally:
                    body.close()
                if len(prior) != asset.expected_bytes or hashlib.sha256(prior).hexdigest() != sha256:
                    raise PrivateTransportError("stage_final_collision", 409)
                return value.get("VersionId", "")
        except PrivateTransportError:
            raise
        except Exception as exc:
            raise PrivateTransportError("storage_unavailable", 503) from exc

    def read_range(self, locator, *, start, length, timeout_seconds):
        try:
            kwargs = {"VersionId": locator.version_id} if locator.version_id else {}
            result = self.client.get_object(Bucket=locator.bucket, Key=locator.key,
                Range=f"bytes={start}-{start + length - 1}", **kwargs)
            body = result["Body"]
            try:
                return body.read(length + 1)
            finally:
                body.close()
        except Exception as exc:
            raise PrivateTransportError("storage_unavailable", 503) from exc

    def delete(self, keys):
        # Shared Events implementation deletes versions, markers and multipart
        # state and proves exact-key absence. No account/finance dependencies.
        from apps.events.submissions.storage_cleanup import delete_keys
        delete_keys(self, keys)


class ScanReader:
    def __init__(self, data):
        self.data, self.size = data, len(data)

    def chunks(self, chunk_size=65536):
        for start in range(0, self.size, chunk_size):
            yield self.data[start:start + chunk_size]
