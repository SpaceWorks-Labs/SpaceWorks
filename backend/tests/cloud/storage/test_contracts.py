import json
from dataclasses import replace

import pytest

from apps.storage_capabilities.configuration import read_configuration
from apps.storage_capabilities.contracts import CapabilityError, StorageCapabilities, StorageIdentity


def contract(**changes):
    value = StorageCapabilities(
        StorageIdentity.build("https://s3.example.test/", "auto", "private"), 1,
        frozenset({"put"}), "never_versioned", False, True, True, False,
        False, False, "private", "private", 1024,
    )
    return replace(value, **changes)


def configuration():
    common = {
        "endpoint": "https://s3.example.test", "region": "auto", "generation": 1,
        "presign_methods": ["put"], "versioning": "never_versioned",
        "list_delete_versions": False, "conditional_create": True, "copy": True,
        "multipart": False, "object_lock": False, "cors_management": False,
        "staging_policy": "private", "public_delivery": "private",
    }
    return {"version": 1, "buckets": {
        "private": {**common, "bucket": "private"},
        "public_image": {**common, "bucket": "images", "public_delivery": "public"},
    }}


def test_endpoint_and_fingerprint_are_stable_and_credential_independent():
    identity = StorageIdentity.build("HTTPS://S3.Example.Test:443/", "auto", "private")
    assert identity == contract().identity
    assert identity.fingerprint == contract().identity.fingerprint
    assert replace(contract(), generation=2).fingerprint != contract().fingerprint
    assert replace(contract(), presign_methods=frozenset({"put", "post"})).fingerprint != contract().fingerprint


@pytest.mark.parametrize("endpoint", ["https://user:secret@host", "https://host?key=secret", "https://host/#x", "file:///bucket"])
def test_endpoint_refuses_credentials_and_non_api_urls(endpoint):
    with pytest.raises(CapabilityError):
        StorageIdentity.build(endpoint, "auto", "bucket")


def test_explicit_post_never_falls_back_to_put():
    assert contract().presign_method("auto") == "put"
    with pytest.raises(CapabilityError, match="unsupported"):
        contract().presign_method("post")
    assert replace(contract(), presign_methods=frozenset({"put", "post"})).presign_method("auto") == "post"


@pytest.mark.parametrize("field,value", [
    ("generation", True), ("versioning", []), ("versioning", "unversioned"),
    ("presign_methods", [["put"]]), ("list_delete_versions", "false"),
    ("staging_policy", "public"), ("max_object_bytes", -1), ("public_delivery", []),
])
def test_configuration_boundary_returns_typed_refusals(tmp_path, field, value):
    document = configuration()
    document["buckets"]["private"][field] = value
    path = tmp_path / "storage.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(CapabilityError):
        read_configuration(path)


def test_per_bucket_config_and_generation(tmp_path):
    path = tmp_path / "storage.json"
    path.write_text(json.dumps(configuration()), encoding="utf-8")
    result = read_configuration(path)
    assert result["private"].identity.bucket == "private"
    assert result["public_image"].staging_policy == "private"
    assert result["public_image"].public_delivery == "public"


def test_duplicate_json_field_is_rejected(tmp_path):
    path = tmp_path / "storage.json"
    path.write_text('{"version":1,"version":1,"buckets":{}}', encoding="utf-8")
    with pytest.raises(CapabilityError, match="duplicate"):
        read_configuration(path)


def test_provider_object_limit_is_not_silently_reduced():
    with pytest.raises(CapabilityError, match="provider_object_limit"):
        contract().validate_upload_limit(1025)


def test_public_bucket_cannot_be_used_as_private_staging(monkeypatch):
    from apps.storage_capabilities import runtime

    private = contract()
    public = replace(private, identity=StorageIdentity.build("https://s3.example.test", "auto", "images"),
                     public_delivery="public")
    monkeypatch.setattr(runtime, "configured_contracts", lambda: {"private": private, "public_image": public})
    monkeypatch.setattr(runtime, "client_identity", lambda *args: public.identity)
    with pytest.raises(CapabilityError, match="bucket_role_mismatch"):
        runtime.capabilities_for(object(), "images", required=True, role="private")
