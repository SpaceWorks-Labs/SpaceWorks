"""Small exact-version S3 objects; promotion uses conditional immutable PUT."""
from datetime import timedelta
from hashlib import sha256
import boto3
from botocore.config import Config
from django.conf import settings
from apps.makerspaces.private_upload_transport import ObjectLocator, UploadDescriptor, UploadRequest, PrivateTransportError
from apps.object_storage import delete_all_versions


def client(*, public=False):
    try:
        return boto3.client("s3", endpoint_url=settings.AWS_S3_PUBLIC_ENDPOINT_URL if public else settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME, config=Config(signature_version=settings.AWS_S3_SIGNATURE_VERSION,
            s3={"addressing_style": settings.AWS_S3_ADDRESSING_STYLE}, connect_timeout=2, read_timeout=2,
            retries={"max_attempts": 0}))
    except Exception:
        raise PrivateTransportError("storage_unavailable", 503) from None


def bucket():
    return settings.AWS_STORAGE_BUCKET_NAME


def asset_bucket(asset_id):
    from .cleanup_models import FinanceObjectCleanup
    return FinanceObjectCleanup.objects.get(asset_id=asset_id).bucket


class FinanceStorage:
    def __init__(self, sdk=None, browser=None, bucket_name=None):
        self.sdk = sdk if sdk is not None else client()
        self.browser = browser
        self.bucket = bucket_name or bucket()

    def initialize(self, request: UploadRequest) -> UploadDescriptor:
        from django.utils import timezone
        seconds = min(900, int((request.not_after - timezone.now()).total_seconds()))
        if seconds <= 0:
            raise PrivateTransportError("asset_expired", 410)
        try:
            response = (self.browser or client(public=True)).generate_presigned_post(Bucket=self.bucket,
                Key=request.staging.key, Fields={"Content-Type": request.mime},
                Conditions=[{"Content-Type": request.mime}, ["content-length-range", request.size_bytes, request.size_bytes]],
                ExpiresIn=seconds)
            return UploadDescriptor(method="POST", url=response["url"], fields=response["fields"],
                expires_at=timezone.now() + timedelta(seconds=seconds), generation=request.generation)
        except Exception:
            raise PrivateTransportError("storage_unavailable", 503) from None

    def head(self, key, version=None):
        try:
            args = {"Bucket": self.bucket, "Key": key}
            if version:
                args["VersionId"] = version
            return self.sdk.head_object(**args)
        except Exception:
            raise PrivateTransportError("storage_unavailable", 503) from None

    def read(self, key, *, version=None, etag=None, maximum):
        args = {"Bucket": self.bucket, "Key": key}
        if version:
            args["VersionId"] = version
        if etag:
            args["IfMatch"] = etag
        try:
            response = self.sdk.get_object(**args)
            body = response["Body"]
            try:
                data = body.read(maximum + 1)
            finally:
                body.close()
            if len(data) > maximum:
                raise PrivateTransportError("file_too_large", 413)
            return data
        except PrivateTransportError:
            raise
        except Exception:
            raise PrivateTransportError("storage_unavailable", 503) from None

    def promote(self, *, key, data, mime, digest):
        try:
            response = self.sdk.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=mime,
                                          IfNoneMatch="*", Metadata={"sha256": digest})
            return response.get("VersionId", "")
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if code not in ("PreconditionFailed", "412"):
                raise PrivateTransportError("storage_unavailable", 503) from None
            head = self.head(key)
            existing = self.read(key, version=head.get("VersionId"), etag=head["ETag"], maximum=len(data))
            if len(existing) != len(data) or sha256(existing).hexdigest() != digest:
                raise PrivateTransportError("final_key_collision", 409)
            return head.get("VersionId", "")

    def reader(self, locator: ObjectLocator, *, start, length, timeout_seconds):
        # The SDK is configured with the transport's maximum two-second timeout.
        args = {"Bucket": locator.bucket, "Key": locator.key, "Range": f"bytes={start}-{start + length - 1}"}
        if locator.version_id:
            args["VersionId"] = locator.version_id
        response = self.sdk.get_object(**args)
        try:
            return response["Body"].read(length)
        finally:
            response["Body"].close()

    def delete(self, key):
        delete_all_versions(self.sdk, bucket=self.bucket, key=key, require_version_listing=True)
