"""Round-eight regressions run against both configured upload transports."""
from io import BytesIO

import pytest
from botocore.exceptions import ClientError
from PIL import Image

from tests.p3_wire.conftest import isolated_notifications, world  # noqa: F401


@pytest.fixture(autouse=True, params=["post", "put"])
def presign_mode(request, settings):
    settings.STORAGE_PRESIGN_METHOD = request.param
    return request.param


def png(color="red"):
    output = BytesIO()
    Image.new("RGB", (3, 3), color).save(output, format="PNG")
    return output.getvalue()


class ImageStore:
    """Only the S3 operations used by real presign/validation/promotion code."""
    def __init__(self):
        self.objects = {}
        self.signed = []
        self.writes = []
        self.before_put = None

    def get_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"},
                               "ResponseMetadata": {"HTTPStatusCode": 404}}, "GetObject")
        data, mime = self.objects[Key]
        return {"Body": BytesIO(data), "ContentType": mime, "ContentLength": len(data)}

    def put_object(self, *, Bucket, Key, Body, ContentType, IfNoneMatch):
        assert IfNoneMatch == "*"
        if self.before_put:
            callback, self.before_put = self.before_put, None
            callback(Key)
        if Key in self.objects:
            raise ClientError({"Error": {"Code": "PreconditionFailed"},
                               "ResponseMetadata": {"HTTPStatusCode": 412}}, "PutObject")
        self.objects[Key] = (Body, ContentType)
        self.writes.append(Key)
        return {}

    def generate_presigned_post(self, **kwargs):
        self.signed.append(kwargs)
        return {"url": "https://objects.example.test", "fields": {"key": kwargs["Key"], **kwargs["Fields"]}}

    def generate_presigned_url(self, operation, *, Params, ExpiresIn):
        assert operation == "put_object"
        self.signed.append(Params)
        return "https://objects.example.test/staging"


@pytest.fixture
def image_store(monkeypatch, settings):
    from apps.bookings import storage as bookings
    from apps.inventory import public_image_storage as shared
    from apps.makerspaces import limits

    settings.PUBLIC_IMAGE_ALLOWED_MIME = {"image/png": [".png"], "image/jpeg": [".jpg", ".jpeg"]}
    settings.PUBLIC_IMAGE_MAX_BYTES = 1024
    store = ImageStore()
    def delete(key):
        store.objects.pop(key, None)
        return True
    for storage in (bookings, shared):
        monkeypatch.setattr(storage, "_client", lambda: store)
        monkeypatch.setattr(storage, "_public_client", lambda: store)
        monkeypatch.setattr(storage, "delete_object", delete)
        monkeypatch.setattr(storage, "object_size", lambda key: len(store.objects[key][0]) if key in store.objects else None)
    monkeypatch.setattr("apps.inventory.public_image_sniff._client", lambda: store)
    monkeypatch.setattr(limits, "is_self_host", lambda: False)
    return store
