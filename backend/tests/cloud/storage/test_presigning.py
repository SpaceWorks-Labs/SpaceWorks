from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from apps.storage_capabilities import presigning
from apps.storage_capabilities.contracts import CapabilityError
from tests.cloud.storage.test_contracts import contract


@pytest.fixture(autouse=True)
def saved_presign_proof(monkeypatch):
    monkeypatch.setattr(presigning, "verified_state", lambda *args: SimpleNamespace(facts={"presign_methods": ["put", "post"]}))


def test_put_signature_binds_mime_and_private_staging(monkeypatch):
    monkeypatch.setattr(presigning, "capabilities_for", lambda *args, **kwargs: contract())
    s3 = Mock(meta=SimpleNamespace(endpoint_url="https://reachable.s3.example"))
    s3.generate_presigned_url.return_value = "https://reachable.s3.example/signed"
    result = presigning.presign_upload(s3, backend_client=Mock(), bucket="private",
        key="staging/final", content_type="image/png", max_bytes=1024, ttl=60, requested="auto")
    assert result == {"url": "https://reachable.s3.example/signed", "method": "PUT", "headers": {"Content-Type": "image/png"}}
    assert s3.generate_presigned_url.call_args.kwargs["Params"] == {
        "Bucket": "private", "Key": "staging/final", "ContentType": "image/png",
    }


def test_post_has_exact_mime_and_finite_byte_policy(monkeypatch):
    value = contract(presign_methods=frozenset({"put", "post"}))
    monkeypatch.setattr(presigning, "capabilities_for", lambda *args, **kwargs: value)
    s3 = Mock(meta=SimpleNamespace(endpoint_url="https://api.example"))
    presigning.presign_upload(s3, backend_client=Mock(), bucket="private", key="staging/final",
        content_type="image/png", max_bytes=1024, ttl=60, requested="post")
    assert s3.generate_presigned_post.call_args.kwargs["Conditions"] == [
        {"Content-Type": "image/png"}, ["content-length-range", 1, 1024],
    ]


def test_public_image_staging_and_legacy_locator_are_distinct_buckets():
    new, legacy = presigning.public_image_staging_candidates("images/final", private_bucket="private", public_bucket="public")
    assert (new.bucket, new.key) == ("private", "staging/public-images/images/final")
    assert (legacy.bucket, legacy.key) == ("public", "staging/images/final")


def test_r2_public_delivery_hostname_is_never_used_for_signing():
    s3 = Mock(meta=SimpleNamespace(endpoint_url="https://public.r2.dev"))
    with pytest.raises(CapabilityError, match="api_endpoint"):
        presigning.presign_upload(s3, backend_client=Mock(), bucket="private", key="staging/final",
            content_type="image/png", max_bytes=1024, ttl=60, requested="put")
    s3.generate_presigned_url.assert_not_called()


@pytest.mark.parametrize("maximum,ttl", [(0, 60), (1024, 0), (1024, 604801)])
def test_invalid_boundary_never_signs(maximum, ttl):
    s3 = Mock()
    with pytest.raises(CapabilityError):
        presigning.presign_upload(s3, backend_client=Mock(), bucket="private", key="staging/final",
            content_type="image/png", max_bytes=maximum, ttl=ttl, requested="put")
