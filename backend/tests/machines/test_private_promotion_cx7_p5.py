"""Legacy document promotion must not replace a final after quota was charged."""
from io import BytesIO
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from apps.evidence.storage import StorageUnavailable
from apps.private_uploads import legacy_promote

pytestmark = [pytest.mark.area_machines, pytest.mark.area_machine_service, pytest.mark.area_inventory]


@pytest.mark.parametrize("raced", [False, True])
def test_private_promotion_pins_staging_and_uses_create_only_final(raced):
    objects = {"staging/key": b"uploaded"}
    calls = []
    def head(**kwargs):
        return {"ContentLength": len(objects[kwargs["Key"]]), "ETag": "snapshot"}
    def read(**kwargs):
        assert kwargs["IfMatch"] == "snapshot"
        return {"Body": BytesIO(objects[kwargs["Key"]]), "ContentType": "application/pdf"}
    def put(**kwargs):
        calls.append(kwargs)
        assert kwargs["IfNoneMatch"] == "*"
        if raced:
            objects["final/key"] = b"first-canonical-file"
            raise ClientError({"Error": {"Code": "PreconditionFailed"}, "ResponseMetadata": {"HTTPStatusCode": 412}}, "PutObject")
        objects["final/key"] = kwargs["Body"].read()
    sdk = SimpleNamespace(head_object=head, get_object=read, put_object=put)
    storage = SimpleNamespace(_client=lambda: sdk, object_size=lambda key: len(objects[key]))
    size = legacy_promote(storage, "staging/key", "final/key", 100)
    expected = b"first-canonical-file" if raced else b"uploaded"
    assert objects["final/key"] == expected
    assert size == len(expected)
    assert len(calls) == 1


def test_private_promotion_storage_failure_keeps_the_typed_unavailable_boundary():
    def fail(**kwargs):
        raise EndpointConnectionError(endpoint_url="https://unavailable.example.test")
    sdk = SimpleNamespace(head_object=fail)
    with pytest.raises(StorageUnavailable) as failure:
        legacy_promote(SimpleNamespace(_client=lambda: sdk), "staging/key", "final/key", 100)
    assert isinstance(failure.value.__cause__, EndpointConnectionError)
