"""Exact, version-pinned S3 ranges. No implicit full-object reads or extraction."""
from .errors import FormatError

MAX_RANGE = 1024 * 1024


class S3RangeReader:
    def __init__(self, client, *, bucket, key, size, version_id=None, etag=None):
        self.client, self.bucket, self.key = client, bucket, key
        self.size, self.version_id, self.etag = size, version_id, etag
        if type(size) is not int or size < 1 or not (version_id or etag):
            raise FormatError("immutable_source_required")

    def read(self, start, length):
        if (type(start) is not int or type(length) is not int or start < 0 or
                length < 0 or length > MAX_RANGE or start + length > self.size):
            raise FormatError("invalid_container_bounds")
        if not length:
            return b""
        kwargs = {"Bucket": self.bucket, "Key": self.key,
                  "Range": f"bytes={start}-{start + length - 1}"}
        if self.version_id:
            kwargs["VersionId"] = self.version_id
        else:
            kwargs["IfMatch"] = self.etag
        try:
            response = self.client.get_object(**kwargs)
            body = response["Body"]
            try:
                data = body.read(length + 1)
            finally:
                body.close()
            expected = f"bytes {start}-{start + length - 1}/{self.size}"
            if (response.get("ContentRange") != expected or len(data) != length or
                    response.get("ContentLength") != length):
                raise FormatError("invalid_storage_range", 503)
            return data
        except FormatError:
            raise
        except Exception as exc:
            raise FormatError("storage_unavailable", 503) from exc

    def chunks(self, chunk_size=MAX_RANGE):
        for offset in range(0, self.size, chunk_size):
            yield self.read(offset, min(chunk_size, self.size - offset))


class BytesReader:
    """Small fixtures and already bounded canonical image buffers only."""
    def __init__(self, data):
        self.data, self.size = data, len(data)

    def read(self, start, length):
        if start < 0 or length < 0 or start + length > self.size:
            raise FormatError("invalid_container_bounds")
        return self.data[start:start + length]

    def chunks(self, chunk_size=MAX_RANGE):
        for offset in range(0, self.size, chunk_size):
            yield self.read(offset, min(chunk_size, self.size - offset))
