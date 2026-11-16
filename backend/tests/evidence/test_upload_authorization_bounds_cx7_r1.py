"""Authorization bounds apply at storage admission, before any finalization."""
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
from xml.etree import ElementTree

import pytest
import requests
from botocore.exceptions import ClientError

from apps.evidence import services_upload, storage
from apps.makerspaces.models import StorageQuotaReservation
from apps.storage_capabilities import presigning
from apps.storage_capabilities.contracts import CapabilityError
from tests.return_helpers import make_member, make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_evidence_uploads, pytest.mark.area_inventory]


def signer(settings, monkeypatch):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    monkeypatch.setattr(presigning, "capabilities_for", lambda *args, **kwargs: None)
    return Mock(meta=SimpleNamespace(endpoint_url="https://storage.test"))


def test_declared_put_binds_actual_length_in_signature_and_upload_headers(settings, monkeypatch):
    client = signer(settings, monkeypatch)
    result = presigning.presign_upload(client, backend_client=client, bucket="private", key="staging/key",
        content_type="image/png", max_bytes=4, exact_bytes=4, ttl=60, requested="put")
    client.generate_presigned_url.assert_called_once_with("put_object", Params={
        "Bucket": "private", "Key": "staging/key", "ContentType": "image/png", "ContentLength": 4}, ExpiresIn=60)
    assert result["headers"] == {"Content-Type": "image/png", "Content-Length": "4"}
    assert result["method"] == "PUT"
    client.generate_presigned_post.assert_not_called()


@pytest.mark.parametrize("requested", ["put", "post", "auto"])
def test_undeclared_length_uses_a_provider_enforced_range(settings, monkeypatch, requested):
    client = signer(settings, monkeypatch)
    if requested == "put":
        from rest_framework.exceptions import ValidationError
        with pytest.raises(ValidationError) as refused:
            presigning.presign_upload(client, backend_client=client, bucket="private", key="staging/key",
                content_type="image/png", max_bytes=4, ttl=60, requested=requested)
        assert (refused.value.status_code, str(refused.value.detail["code"])) == (400, "upload_size_required")
        client.generate_presigned_url.assert_not_called()
        client.generate_presigned_post.assert_not_called()
        return
    from tests.cloud.storage.test_contracts import contract
    value = contract(presign_methods=frozenset({"put", "post"}))
    monkeypatch.setattr(presigning, "capabilities_for", lambda *a, **kw: value)
    monkeypatch.setattr(presigning, "verified_state", lambda *a: SimpleNamespace(facts={"presign_methods": ["put", "post"]}))
    presigning.presign_upload(client, backend_client=client, bucket="private", key="staging/key",
        content_type="image/png", max_bytes=4, ttl=60, requested=requested)
    client.generate_presigned_post.assert_called_once_with(Bucket="private", Key="staging/key",
        Fields={"Content-Type": "image/png"}, Conditions=[{"Content-Type": "image/png"},
        ["content-length-range", 1, 4]], ExpiresIn=60)
    client.generate_presigned_url.assert_not_called()


def test_exact_length_cannot_exceed_the_reservation(settings, monkeypatch):
    client = signer(settings, monkeypatch)
    with pytest.raises(CapabilityError) as refused:
        presigning.presign_upload(client, backend_client=client, bucket="private", key="staging/key",
            content_type="image/png", max_bytes=4, exact_bytes=5, ttl=60, requested="put")
    assert refused.value.code == "storage_upload_limit_invalid"
    client.generate_presigned_url.assert_not_called()
    client.generate_presigned_post.assert_not_called()


@pytest.mark.parametrize("declared", [None, 4])
def test_evidence_reservation_and_real_signer_share_the_fitting_bound(declared, settings, monkeypatch):
    client = signer(settings, monkeypatch)
    settings.STORAGE_PRESIGN_METHOD = "post" if declared is None else "put"
    settings.MANAGED_PLANS_ENABLED = False
    monkeypatch.setattr(storage, "_client", lambda: client)
    monkeypatch.setattr(storage, "_public_client", lambda: client)
    client.generate_presigned_url.return_value = "https://storage.test/put"
    client.generate_presigned_post.return_value = {"url": "https://storage.test/post", "fields": {}}
    space = make_space("r1-authorized-bound")
    space.resource_limit_overrides = {"storage": 4, "storage_evidence_bytes": 4}
    space.save(update_fields=["resource_limit_overrides"])
    photo, result = services_upload.issue_upload(space, actor=make_member("r1-signer", space),
        evidence_type="return", content_type="image/png", size_bytes=declared)
    assert StorageQuotaReservation.objects.get(object_key=photo.object_key).size_bytes == 4
    if declared is None:
        assert client.generate_presigned_post.call_args.kwargs["Conditions"][-1] == ["content-length-range", 1, 4]
    else:
        assert result["headers"]["Content-Length"] == "4"
        assert client.generate_presigned_url.call_args.kwargs["Params"]["ContentLength"] == 4


def test_harness_oversized_put_is_rejected_before_storage_accepts_any_bytes(settings, monkeypatch):
    # Real isolated-harness provider boundary: no signer or HTTP transport fake.
    settings.STORAGE_CAPABILITIES_FILE = ""
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    client = storage._s3_client(settings.AWS_S3_ENDPOINT_URL)
    bucket, key = settings.AWS_STORAGE_BUCKET_NAME, "staging/cx7-bound/" + uuid4().hex
    signed = presigning.presign_upload(client, backend_client=client, bucket=bucket, key=key,
        content_type="image/png", max_bytes=4, exact_bytes=4, ttl=60, requested="put")
    query = parse_qs(urlsplit(signed["url"]).query)
    assert "content-length" in query["X-Amz-SignedHeaders"][0].split(";")
    try:
        refused = requests.put(signed["url"], data=b"12345", headers={"Content-Type": "image/png"}, timeout=20)
        assert refused.status_code == 403
        assert ElementTree.fromstring(refused.content).findtext("Code") == "SignatureDoesNotMatch"
        with pytest.raises(ClientError) as missing:
            client.head_object(Bucket=bucket, Key=key)
        assert missing.value.response["ResponseMetadata"]["HTTPStatusCode"] == 404
        assert missing.value.response["Error"]["Code"] == "404"
        accepted = requests.put(signed["url"], data=b"1234", headers=signed["headers"], timeout=20)
        assert accepted.status_code == 200
        assert client.head_object(Bucket=bucket, Key=key)["ContentLength"] == 4
    finally:
        from apps.object_storage import delete_all_versions
        assert delete_all_versions(client, bucket=bucket, key=key).absence_confirmed is True


@pytest.mark.parametrize("size", [0, -1, True])
def test_invalid_declared_evidence_size_is_typed_before_any_reservation(size, settings):
    from rest_framework.exceptions import ValidationError
    space = make_space("r1-invalid-upload-size")
    provider = Mock()
    with pytest.raises(ValidationError) as refused:
        services_upload.issue_upload(space, actor=make_member("r1-invalid-size", space),
            evidence_type="return", content_type="image/png", size_bytes=size, presigner=provider)
    assert (refused.value.status_code, str(refused.value.detail["code"])) == (400, "upload_limit")
    assert StorageQuotaReservation.objects.filter(makerspace=space).count() == 0
    provider.assert_not_called()
