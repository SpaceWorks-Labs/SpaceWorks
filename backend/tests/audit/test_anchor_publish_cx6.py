"""Publish protocols against external HTTP/S3 doubles; signatures and sink logic are real."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta
import io
import json

import pytest
import requests
from botocore.exceptions import ClientError
from django.utils import timezone

from apps.audit.anchors_base import AnchorConfigurationError, AnchorConflict, AnchorTransportError
from apps.audit.anchors_budget import AnchorReadBudget, AnchorReadBudgetExceeded
from apps.audit.anchors_http import HttpCollectorAnchorSink
from apps.audit.anchors_object_storage import ObjectStorageAnchorSink
from apps.audit.batch_format import ROTATION_DOMAIN, canonical_payload_bytes
from apps.ed25519 import encode_key, fingerprint_public_key, generate_keypair, sign_bytes


def anchor(signer="a" * 64, seq=0, root="11" * 32):
    return {"payload": {"deployment_id": "cx6-deployment", "scope": "makerspace:1",
        "signer_fingerprint": signer, "batch_seq": seq, "merkle_root": root, "anchor_protocol_version": 2}}


def rotation(old, new, *, seq=0, root="11" * 32):
    payload = {"deployment_id": "cx6-deployment", "scope": "makerspace:1", "entry_type": "key_rotation",
        "anchor_protocol_version": 2, "domain": ROTATION_DOMAIN,
        "old_fingerprint": fingerprint_public_key(old[1]), "new_fingerprint": fingerprint_public_key(new[1]),
        "new_public_key": encode_key(new[1]), "old_version": 1, "new_version": 2,
        "last_old_batch_seq": seq, "last_old_batch_root": root}
    raw = canonical_payload_bytes(payload)
    return {"payload": payload, "old_public_key": encode_key(old[1]), "new_public_key": encode_key(new[1]),
            "old_signature": sign_bytes(raw, old[0]).hex(), "new_signature": sign_bytes(raw, new[0]).hex()}


def stored(envelope):
    return {**deepcopy(envelope), "anchored_at": "2026-11-14T00:00:00+00:00"}


class HttpResponse:
    def __init__(self, status, data):
        self.status_code, self.data = status, data

    def json(self):
        return self.data


@pytest.fixture
def http_sink(settings):
    settings.AUDIT_ATTESTATION_HTTP_URL = "https://collector.test/anchors"
    settings.AUDIT_ATTESTATION_HTTP_BEARER_TOKEN = "collector-token"
    return HttpCollectorAnchorSink()


@pytest.mark.parametrize("kind", ["batch", "rotation"])
@pytest.mark.parametrize("status", [200, 201])
def test_http_publish_accepts_the_exact_stored_envelope_and_sends_protocol_headers(http_sink, monkeypatch, kind, status):
    envelope = anchor() if kind == "batch" else rotation(generate_keypair(), generate_keypair())
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return HttpResponse(status, stored(envelope))

    monkeypatch.setattr(requests, "post", post)
    result = http_sink.publish(envelope) if kind == "batch" else http_sink.publish_rotation(envelope)
    assert result == stored(envelope)
    assert calls == [("https://collector.test/anchors", {"json": envelope, "timeout": 10.0, "headers": {
        "Accept": "application/json", "X-SpaceWorks-Audit-Anchor-Protocol": "2",
        "Authorization": "Bearer collector-token", "Content-Type": "application/json"}})]


@pytest.mark.parametrize("kind", ["batch", "rotation"])
@pytest.mark.parametrize("status,error_type", [(409, AnchorConflict), (429, AnchorTransportError),
    (503, AnchorTransportError), (403, AnchorConfigurationError)])
def test_http_publish_classifies_provider_refusal(http_sink, monkeypatch, kind, status, error_type):
    envelope = anchor() if kind == "batch" else rotation(generate_keypair(), generate_keypair())
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: HttpResponse(status, None))
    with pytest.raises(error_type) as error:
        (http_sink.publish if kind == "batch" else http_sink.publish_rotation)(envelope)
    assert type(error.value) is error_type


@pytest.mark.parametrize("kind", ["batch", "rotation"])
def test_http_transport_failure_keeps_provider_details_out_of_the_public_error(http_sink, monkeypatch, kind):
    def post(*args, **kwargs):
        raise requests.Timeout("provider-secret")

    monkeypatch.setattr(requests, "post", post)
    envelope = anchor() if kind == "batch" else rotation(generate_keypair(), generate_keypair())
    with pytest.raises(AnchorTransportError) as error:
        (http_sink.publish if kind == "batch" else http_sink.publish_rotation)(envelope)
    assert str(error.value) == ("The HTTP anchor could not be persisted." if kind == "batch"
                                else "The HTTP rotation anchor could not be persisted.")


def test_http_success_status_with_changed_content_is_still_a_conflict(http_sink, monkeypatch):
    envelope = anchor()
    altered = stored(envelope)
    altered["payload"]["merkle_root"] = "22" * 32
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: HttpResponse(201, altered))
    with pytest.raises(AnchorConflict) as error:
        http_sink.publish(envelope)
    assert str(error.value) == "The collector stored content other than the submission."


class ObjectStore:
    """External S3 API double: persist immutable JSON and expose real prefix scans."""
    def __init__(self):
        self.objects, self.puts = {}, []
        self.failure, self.concurrent = None, None

    def get_object(self, *, Bucket, Key):
        if self.failure == "get":
            raise ClientError({"Error": {"Code": "AccessDenied"}, "ResponseMetadata": {"HTTPStatusCode": 403}}, "GetObject")
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}, "ResponseMetadata": {"HTTPStatusCode": 404}}, "GetObject")
        return {"Body": io.BytesIO(json.dumps(self.objects[Key]).encode())}

    def list_objects_v2(self, *, Bucket, Prefix, **kwargs):
        if self.failure == "list":
            raise OSError("offline")
        return {"Contents": [{"Key": key} for key in sorted(self.objects) if key.startswith(Prefix)]}

    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        if self.failure == "put":
            raise ClientError({"Error": {"Code": "SlowDown"}, "ResponseMetadata": {"HTTPStatusCode": 503}}, "PutObject")
        if self.concurrent is not None:
            self.objects[kwargs["Key"]] = self.concurrent
            raise ClientError({"Error": {"Code": "PreconditionFailed"}, "ResponseMetadata": {"HTTPStatusCode": 412}}, "PutObject")
        self.objects[kwargs["Key"]] = json.loads(kwargs["Body"])


@pytest.fixture
def object_sink(settings, monkeypatch):
    settings.AUDIT_ATTESTATION_S3_BUCKET = "cx6-anchors"
    settings.AUDIT_ATTESTATION_S3_PREFIX = "anchors"
    settings.AUDIT_ATTESTATION_RETENTION_DAYS = 7
    settings.AUDIT_ATTESTATION_S3_OBJECT_LOCK_MODE = ""
    settings.STORAGE_CAPABILITIES_FILE = ""
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    store = ObjectStore()
    monkeypatch.setattr("apps.audit.anchors_object_storage.s3_client", lambda *args, **kwargs: store)
    return ObjectStorageAnchorSink(), store


def test_object_publish_is_immutable_compliance_locked_and_replay_adds_no_write(object_sink, monkeypatch):
    sink, store = object_sink
    envelope = anchor()
    at = datetime(2026, 11, 14, 10, 30, tzinfo=UTC)
    monkeypatch.setattr(timezone, "now", lambda: at)
    result = sink.publish(envelope)
    assert result["payload"] == envelope["payload"]
    assert result["anchored_at"] == at.isoformat()
    monkeypatch.setattr(timezone, "now", lambda: at + timedelta(minutes=1))
    assert sink.publish(envelope) == result
    assert len(store.puts) == 1
    write = store.puts[0]
    assert (write["Bucket"], write["IfNoneMatch"], write["ObjectLockMode"], write["ContentType"]) == (
        "cx6-anchors", "*", "COMPLIANCE", "application/json")
    assert write["ObjectLockRetainUntilDate"] == at + timedelta(days=7)
    different = anchor(root="22" * 32)
    with pytest.raises(AnchorConflict) as error:
        sink.publish(different)
    assert str(error.value) == "This anchor sequence already has other content."
    assert len(store.puts) == 1


def test_object_scope_sequence_refuses_gaps_and_accepts_the_next_batch(object_sink):
    sink, store = object_sink
    sink.publish(anchor())
    with pytest.raises(AnchorConflict) as error:
        sink.publish(anchor(seq=2))
    assert str(error.value) == "The anchor sequence does not continue the scope-global head."
    assert len(store.puts) == 1
    assert sink.publish(anchor(seq=1))["payload"]["batch_seq"] == 1
    assert sink.fetch_scope_head("cx6-deployment", "makerspace:1") == (1, "a" * 64, bytes.fromhex("11" * 32))


@pytest.mark.parametrize("same", [True, False])
def test_concurrent_conditional_put_returns_only_identical_winners(object_sink, same):
    sink, store = object_sink
    store.concurrent = stored(anchor(root="11" * 32 if same else "22" * 32))
    if same:
        assert sink.publish(anchor()) == store.concurrent
    else:
        with pytest.raises(AnchorConflict) as error:
            sink.publish(anchor())
        assert str(error.value) == "A concurrent conflicting anchor won."
    assert len(store.puts) == 1


@pytest.mark.parametrize("operation,error_type,message", [
    ("get", AnchorConfigurationError, "The object anchor could not be fetched."),
    ("list", AnchorTransportError, "The scope-global anchor head could not be read."),
    ("put", AnchorTransportError, "The object anchor could not be persisted."),
])
def test_storage_failures_keep_the_sink_error_taxonomy(object_sink, operation, error_type, message):
    sink, store = object_sink
    store.failure = operation
    with pytest.raises(error_type) as error:
        sink.publish(anchor())
    assert type(error.value) is error_type
    assert str(error.value) == message
    assert store.objects == {}


def test_signed_rotation_switches_scope_authority_and_replay_adds_no_write(object_sink):
    sink, store = object_sink
    old, new = generate_keypair(), generate_keypair()
    old_id, new_id = fingerprint_public_key(old[1]), fingerprint_public_key(new[1])
    sink.publish(anchor(old_id))
    transition = rotation(old, new)
    published = sink.publish_rotation(transition)
    assert sink.publish_rotation(transition) == published
    assert len(store.puts) == 2
    assert sink.fetch_scope_head("cx6-deployment", "makerspace:1") == (0, new_id, bytes.fromhex("11" * 32))
    with pytest.raises(AnchorConflict) as error:
        sink.publish(anchor(old_id, seq=1))
    assert str(error.value) == "The new signer has no anchored cross-key transition."
    assert sink.publish(anchor(new_id, seq=1))["payload"]["signer_fingerprint"] == new_id


def test_rotation_with_a_different_root_cannot_be_published(object_sink):
    sink, store = object_sink
    old, new = generate_keypair(), generate_keypair()
    sink.publish(anchor(fingerprint_public_key(old[1])))
    with pytest.raises(AnchorConflict) as error:
        sink.publish_rotation(rotation(old, new, root="22" * 32))
    assert str(error.value) == "The key transition does not bind the scope-global head."
    assert len(store.puts) == 1


def test_scope_head_reads_share_the_same_budget(object_sink):
    sink, store = object_sink
    sink.publish(anchor())
    sink.read_budget = AnchorReadBudget(1)
    with pytest.raises(AnchorReadBudgetExceeded) as error:
        sink.fetch_scope_head("cx6-deployment", "makerspace:1")
    assert sink.read_budget.used == 1
    assert str(error.value) == "The anchor read budget of 1 operations is exhausted."
