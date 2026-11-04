"""S3 upload transport; clients must use two-second connect/read timeouts.

Keys are server generated, staging is the only signed write destination. This
adapter contains no authorization or ORM work. Conditional-copy failures retry;
they never fall back to copying a mutable latest source.
"""
from dataclasses import dataclass
from datetime import timedelta, datetime, UTC
import hashlib
import math

from apps.maker_formats.range_reader import S3RangeReader
from .errors import SubmissionError

SINGLE_LIMIT = 25 * 1024 ** 2
DEFAULT_PART = 16 * 1024 ** 2


@dataclass(frozen=True)
class FrozenObject:
    key: str
    size: int
    etag: str
    version_id: str | None


class EventAssetStorage:
    def __init__(self, client, browser_client, bucket):
        self.client, self.browser_client, self.bucket = client, browser_client, bucket

    def head(self, key):
        try:
            row = self.client.head_object(Bucket=self.bucket, Key=key)
            return FrozenObject(key, row["ContentLength"], row["ETag"], row.get("VersionId"))
        except Exception as exc:
            raise SubmissionError("storage_unavailable", 503) from exc

    def reader(self, obj):
        reader = S3RangeReader(self.client, bucket=self.bucket, key=obj.key, size=obj.size,
                               version_id=obj.version_id, etag=obj.etag)
        if getattr(self, "on_progress", None):
            return ProgressReader(reader, self.on_progress)
        return reader

    def initialize(self, asset, *, now):
        seconds = self.write_ttl(asset, now=now)
        try:
            if asset.declared_bytes < SINGLE_LIMIT:
                result = self.browser_client.generate_presigned_post(
                    Bucket=self.bucket, Key=asset.staging_key,
                    Fields={"Content-Type": asset.declared_mime},
                    Conditions=[{"Content-Type": asset.declared_mime},
                                ["content-length-range", asset.declared_bytes, asset.declared_bytes]],
                    ExpiresIn=seconds,
                )
                return {"method": "POST", **result, "expires_at": (now + timedelta(seconds=seconds)).isoformat()}, "", 0
            part_size = max(DEFAULT_PART, math.ceil(asset.declared_bytes / 10000 / 1024 ** 2) * 1024 ** 2)
            result = self.client.create_multipart_upload(Bucket=self.bucket, Key=asset.staging_key,
                                                          ContentType=asset.declared_mime)
            return {"method": "MULTIPART", "part_size": part_size, "part_count": math.ceil(asset.declared_bytes / part_size),
                    "expires_at": (now + timedelta(seconds=seconds)).isoformat()}, result["UploadId"], part_size
        except Exception as exc:
            raise SubmissionError("storage_unavailable", 503) from exc

    def sign_parts(self, asset, numbers):
        seconds = self.write_ttl(asset, now=datetime.now(UTC))
        count = math.ceil(asset.declared_bytes / asset.part_size) if asset.part_size else 0
        if (not asset.multipart_upload_id or not isinstance(numbers, list) or not 1 <= len(numbers) <= 100 or
                any(type(n) is not int or not 1 <= n <= count for n in numbers) or len(set(numbers)) != len(numbers)):
            raise SubmissionError("invalid_parts")
        try:
            return [{"part_number": n, "size_bytes": min(asset.part_size, asset.declared_bytes - (n - 1) * asset.part_size),
                     "url": self.browser_client.generate_presigned_url("upload_part", Params={
                         "Bucket": self.bucket, "Key": asset.staging_key, "UploadId": asset.multipart_upload_id,
                         "PartNumber": n}, ExpiresIn=seconds, HttpMethod="PUT")} for n in numbers]
        except Exception as exc:
            raise SubmissionError("storage_unavailable", 503) from exc

    def list_parts(self, asset):
        parts, marker = [], 0
        try:
            while True:
                response = self.client.list_parts(Bucket=self.bucket, Key=asset.staging_key,
                                                   UploadId=asset.multipart_upload_id, PartNumberMarker=marker)
                page = response.get("Parts", [])
                parts.extend(page)
                if len(parts) > 10000:
                    raise SubmissionError("invalid_parts")
                if not response.get("IsTruncated"):
                    break
                next_marker = response.get("NextPartNumberMarker", 0)
                if next_marker <= marker:
                    raise SubmissionError("invalid_parts")
                marker = next_marker
        except SubmissionError:
            raise
        except Exception as exc:
            raise SubmissionError("storage_unavailable", 503) from exc
        expected = math.ceil(asset.declared_bytes / asset.part_size)
        if len(parts) != expected:
            raise SubmissionError("missing_upload_parts", 409)
        for number, part in enumerate(parts, 1):
            if (part.get("PartNumber") != number or not part.get("ETag") or
                    part.get("Size") != min(asset.part_size, asset.declared_bytes - (number - 1) * asset.part_size)):
                raise SubmissionError("invalid_parts")
        return [{"PartNumber": p["PartNumber"], "ETag": p["ETag"]} for p in parts]

    def complete(self, asset):
        if asset.multipart_upload_id:
            parts = self.list_parts(asset)  # Never accepts the browser's ETag list.
            try:
                self.client.complete_multipart_upload(Bucket=self.bucket, Key=asset.staging_key,
                    UploadId=asset.multipart_upload_id, MultipartUpload={"Parts": parts})
            except Exception as exc:
                raise SubmissionError("storage_unavailable", 503) from exc
        source = self.head(asset.staging_key)
        if source.size != asset.declared_bytes or source.size > asset.effective_cap:
            raise SubmissionError("upload_size_mismatch", 413)
        return source

    def freeze(self, source, target_key):
        copy_source = {"Bucket": self.bucket, "Key": source.key}
        if source.version_id:
            copy_source["VersionId"] = source.version_id
        try:
            response = self.client.copy_object(Bucket=self.bucket, Key=target_key,
                CopySource=copy_source, CopySourceIfMatch=source.etag, MetadataDirective="COPY")
            head = self.head(target_key)
            version = response.get("VersionId")
            if head.size != source.size or version and version != head.version_id:
                raise SubmissionError("upload_source_changed", 409)
            return head
        except SubmissionError:
            raise
        except Exception as exc:
            raise SubmissionError("upload_source_changed", 409) from exc

    def digest(self, obj):
        digest = hashlib.sha256()
        for chunk in self.reader(obj).chunks():
            digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def write_ttl(asset, *, now):
        deadline = getattr(asset, "upload_not_after", None)
        seconds = min(900, int((deadline - now).total_seconds())) if deadline else 0
        if seconds <= 0:
            raise SubmissionError("uploads_closed", 409)
        return seconds


class ProgressReader:
    def __init__(self, reader, progress):
        self.reader, self.progress, self.size = reader, progress, reader.size

    def read(self, start, length):
        self.progress()
        return self.reader.read(start, length)

    def chunks(self, chunk_size=1024 ** 2):
        for start in range(0, self.size, chunk_size):
            yield self.read(start, min(chunk_size, self.size - start))
