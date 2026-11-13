"""Versioned, ranged, conditional, multipart S3 fake for Lane B race tests."""
from io import BytesIO
import hashlib
from uuid import uuid4


class StorageError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}
        super().__init__(code)


class FakeS3:
    def __init__(self):
        self.objects, self.multipart, self.calls = {}, {}, []

    def put_object(self, *, Bucket, Key, Body, IfNoneMatch=None, **kwargs):
        if IfNoneMatch == "*" and self.objects.get(Key):
            raise StorageError("PreconditionFailed")
        body = Body if isinstance(Body, bytes) else Body.read()
        version = str(uuid4())
        self.objects.setdefault(Key, []).append((version, body))
        return {"VersionId": version}

    def _object(self, key, version=None):
        rows = self.objects.get(key, [])
        if version is None and rows:
            return rows[-1]
        for item in rows:
            if item[0] == version:
                return item
        raise StorageError("NoSuchKey")

    def head_object(self, *, Bucket, Key, VersionId=None):
        version, body = self._object(Key, VersionId)
        return {"ContentLength": len(body), "ETag": hashlib.md5(body).hexdigest(), "VersionId": version}

    def get_object(self, *, Bucket, Key, Range, VersionId=None, IfMatch=None):
        version, body = self._object(Key, VersionId)
        if IfMatch and IfMatch != hashlib.md5(body).hexdigest():
            raise StorageError("PreconditionFailed")
        start, end = map(int, Range.removeprefix("bytes=").split("-"))
        block = body[start:end+1]
        self.calls.append((Key, start, end))
        return {"Body": BytesIO(block), "ContentLength": len(block),
                "ContentRange": f"bytes {start}-{end}/{len(body)}", "VersionId": version}

    def copy_object(self, *, Bucket, Key, CopySource, CopySourceIfMatch, **kwargs):
        _, body = self._object(CopySource["Key"], CopySource.get("VersionId"))
        if hashlib.md5(body).hexdigest() != CopySourceIfMatch:
            raise StorageError("PreconditionFailed")
        return self.put_object(Bucket=Bucket, Key=Key, Body=body)

    def create_multipart_upload(self, *, Bucket, Key, **kwargs):
        upload_id = str(uuid4())
        self.multipart[upload_id] = {"key": Key, "parts": {}}
        return {"UploadId": upload_id}

    def upload_part(self, *, Bucket, Key, UploadId, PartNumber, Body):
        self.multipart[UploadId]["parts"][PartNumber] = Body
        return {"ETag": hashlib.md5(Body).hexdigest()}

    def upload_part_copy(self, *, Bucket, Key, UploadId, PartNumber, CopySource, CopySourceIfMatch, CopySourceRange):
        _, body = self._object(CopySource["Key"], CopySource.get("VersionId"))
        if hashlib.md5(body).hexdigest() != CopySourceIfMatch:
            raise StorageError("PreconditionFailed")
        start, end = map(int, CopySourceRange.removeprefix("bytes=").split("-"))
        part = self.upload_part(Bucket=Bucket, Key=Key, UploadId=UploadId, PartNumber=PartNumber, Body=body[start:end+1])
        return {"CopyPartResult": part}

    def list_parts(self, *, Bucket, Key, UploadId, PartNumberMarker=0):
        parts = self.multipart[UploadId]["parts"]
        return {"Parts": [{"PartNumber": n, "Size": len(b), "ETag": hashlib.md5(b).hexdigest()}
                          for n, b in sorted(parts.items()) if n > PartNumberMarker], "IsTruncated": False}

    def complete_multipart_upload(self, *, Bucket, Key, UploadId, MultipartUpload, IfNoneMatch=None):
        parts = self.multipart[UploadId]["parts"]
        numbers = [part["PartNumber"] for part in MultipartUpload["Parts"]]
        if numbers != sorted(parts):
            raise StorageError("InvalidPart")
        for part in MultipartUpload["Parts"]:
            if part["ETag"] != hashlib.md5(parts[part["PartNumber"]]).hexdigest():
                raise StorageError("InvalidPart")
        result = self.put_object(Bucket=Bucket, Key=Key, Body=b"".join(parts[n] for n in numbers), IfNoneMatch=IfNoneMatch)
        del self.multipart[UploadId]
        return result

    def abort_multipart_upload(self, *, Bucket, Key, UploadId):
        self.multipart.pop(UploadId, None)

    def delete_object(self, *, Bucket, Key, VersionId=None):
        rows = self.objects.get(Key, [])
        self.objects[Key] = [r for r in rows if r[0] != VersionId] if VersionId else []
        return {}

    def delete_objects(self, *, Bucket, Delete):
        for row in Delete["Objects"]:
            self.delete_object(Bucket=Bucket, **row)
        return {}

    def get_paginator(self, name):
        fake = self
        class Paginator:
            def paginate(self, *, Bucket, Prefix):
                if name == "list_object_versions":
                    yield {"Versions": [{"Key": key, "VersionId": version} for key, rows in fake.objects.items()
                                         for version, _ in rows if key.startswith(Prefix)]}
                elif name == "list_multipart_uploads":
                    yield {"Uploads": [{"Key": row["key"], "UploadId": ident} for ident, row in fake.multipart.items()
                                        if row["key"].startswith(Prefix)]}
                else:
                    raise AssertionError(name)
        return Paginator()

    def generate_presigned_post(self, **kwargs):
        self.signed = kwargs
        return {"url": "https://storage.example", "fields": {"key": kwargs["Key"], **kwargs["Fields"]}}

    def generate_presigned_url(self, operation, *, Params, ExpiresIn, HttpMethod):
        assert operation == "upload_part" and HttpMethod == "PUT"
        return "https://storage.example/staging-part"
