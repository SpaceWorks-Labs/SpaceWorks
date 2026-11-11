"""Raw SDK callers cannot bypass free admission or credit ambiguous multipart I/O."""
from io import BytesIO
from types import SimpleNamespace

import pytest

from apps.operations.cloud_quotas import transport
from apps.storage_capabilities.contracts import CapabilityError


@pytest.fixture
def calls(monkeypatch, settings):
    settings.FREE_MAX_PROMOTION_BYTES = 1024
    calls = []
    monkeypatch.setattr(transport, "reserve_upload", lambda *args, **kwargs: calls.append(("reserve", kwargs)))
    monkeypatch.setattr(transport, "finalized_upload", lambda *args, **kwargs: calls.append(("finalize", kwargs)))
    monkeypatch.setattr(transport, "identity_for", lambda *args: "identity")
    monkeypatch.setattr(transport, "pending_key", lambda *args: None)
    monkeypatch.setattr(transport, "clear_pending", lambda *args: calls.append(("clear", args)))
    monkeypatch.setattr(transport, "_uncertain", lambda *args: calls.append(("uncertain", args)))
    monkeypatch.setattr(transport, "_claim", lambda *args: None)
    return calls


def test_put_known_stream_reserves_before_effect_and_settles_only_success(calls):
    context = {}
    stream = BytesIO(b"abcdef")
    stream.seek(2)
    transport.before(None, {"Bucket": "private", "Key": "one", "Body": stream},
                     model=SimpleNamespace(name="PutObject"), context=context)
    assert stream.tell() == 2 and calls[0][1]["max_bytes"] == 4
    transport.after(None, context=context, parsed={}, http_response=SimpleNamespace(status_code=200))
    assert [c[0] for c in calls] == ["reserve", "finalize", "clear"]


def test_unknown_stream_and_inconsistent_length_are_refused_before_write(calls):
    with pytest.raises(CapabilityError, match="stream_size_unknown"):
        transport.before(None, {"Bucket": "private", "Key": "one", "Body": object()},
                         model=SimpleNamespace(name="PutObject"), context={})
    with pytest.raises(CapabilityError, match="length_mismatch"):
        transport.before(None, {"Bucket": "private", "Key": "one", "Body": b"data", "ContentLength": 1},
                         model=SimpleNamespace(name="PutObject"), context={})
    assert calls == []


def test_multipart_parts_stay_reserved_on_success_and_failure(calls):
    for status in (200, 500):
        context = {}
        transport.before(None, {"Bucket": "private", "Key": "one", "Body": b"data",
            "UploadId": "u", "PartNumber": 1}, model=SimpleNamespace(name="UploadPart"), context=context)
        transport.after(None, context=context, parsed={}, http_response=SimpleNamespace(status_code=status))
    assert all(c[0] != "finalize" for c in calls)
    reservations = [c[1]["key"] for c in calls if c[0] == "reserve"]
    assert len(reservations) == 2 and reservations[0] != reservations[1]


def test_copy_measures_and_pins_source_without_ambient_credential_changes(calls):
    client = SimpleNamespace(head_object=lambda **kwargs: {"ContentLength": 10, "ETag": '"pinned"'})
    params = {"Bucket": "private", "Key": "two", "CopySource": {"Bucket": "source", "Key": "one"}}
    transport.before(client, params, model=SimpleNamespace(name="CopyObject"), context={})
    assert params["CopySourceIfMatch"] == '"pinned"'
    assert calls[0][1]["max_bytes"] == 10


def test_oversize_raw_put_and_presign_generation_have_no_effect(calls):
    with pytest.raises(CapabilityError, match="external_job_required"):
        transport.before(None, {"Bucket": "private", "Key": "one", "Body": b"x" * 1025},
                         model=SimpleNamespace(name="PutObject"), context={})
    transport.before(None, {"Bucket": "private", "Key": "one"},
                     model=SimpleNamespace(name="PutObject"), context={"is_presign_request": True})
    assert calls == []


def test_free_signed_put_is_create_only_and_versioned_post_is_refused(settings, monkeypatch):
    from apps.storage_capabilities import presigning
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    contract = SimpleNamespace(versioning="enabled", validate_upload_limit=lambda n: None,
                               presign_method=lambda requested: requested)
    facts = SimpleNamespace(facts={"presign_methods": ["put", "post"], "put_conditional_presign": True})
    monkeypatch.setattr(presigning, "capabilities_for", lambda *args, **kwargs: contract)
    monkeypatch.setattr(presigning, "verified_state", lambda *args: facts)
    monkeypatch.setattr("apps.storage_capabilities.runtime.require_capability", lambda *args, **kwargs: contract)
    monkeypatch.setattr("apps.operations.cloud_quotas.storage.reserve_upload", lambda *args, **kwargs: None)
    signed = []
    client = SimpleNamespace(meta=SimpleNamespace(endpoint_url="https://storage.example.org"),
        generate_presigned_url=lambda *args, **kwargs: signed.append(kwargs) or "https://signed.example.org")
    kwargs = {"backend_client": None, "bucket": "private", "key": "staging/one", "content_type": "image/png",
              "max_bytes": 100, "ttl": 60}
    result = presigning.presign_upload(client, requested="put", **kwargs)
    assert signed[0]["Params"]["IfNoneMatch"] == "*" and result["headers"]["If-None-Match"] == "*"
    with pytest.raises(CapabilityError, match="replayable_post_refused"):
        presigning.presign_upload(client, requested="post", **kwargs)
