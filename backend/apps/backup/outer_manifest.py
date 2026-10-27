"""Construction and host-key verification for the signed deployment-archive manifest."""

import base64
import hashlib
import json

from django.conf import settings

from apps.backup.compound_protocol import PROTOCOL_VERSION
from apps.backup.outer_manifest_facts import main_component_fact
from apps.backup.build_errors import BackupBuildError
from apps.backup.outer_manifest_validation import (
    component_id,  # noqa: F401  re-exported: outer_manifest is component_id's public home
    validate_unsigned_manifest,
)
from apps.ed25519 import (
    Ed25519Error,
    decode_key,
    fingerprint_public_key,
    sign_bytes,
    verify_bytes,
)


SIGNATURE_DOMAIN = b"spaceworks-lane-e-outer-manifest-v1\x00"


def build_outer_manifest(*, archive, capture, detailed_manifest, root):
    main = main_component_fact(capture, root)
    main_id = main["component_id"]
    detailed_postgres = detailed_manifest["postgres"]
    objects = detailed_manifest.get("storage", {}).get("objects", ())
    content_entries = detailed_manifest.get("contents", ())
    population = list(capture.population_ids)
    manifest = {
        "format": detailed_manifest["format"],
        "protocol_version": PROTOCOL_VERSION,
        "artifact_id": str(archive.pk),
        "capture_id": str(capture.capture_id),
        "source_timestamp": detailed_manifest["snapshot_at"],
        "build_identity": {
            "build": detailed_manifest["build"],
            "oci_digest": detailed_manifest.get("oci_digest", ""),
        },
        "postgres": {
            "source_server_major": detailed_postgres["source_server_major"],
            "client": detailed_postgres["client"],
            "supported_source_majors": list(
                detailed_postgres["supported_source_majors"]
            ),
        },
        "makerspace_ids": population,
        "main_component": main,
        "object_ledgers": [{
            "component_id": main_id,
            "count": len(objects),
            "digest": _digest_json(objects),
        }],
        "content_ledgers": [{
            "component_id": main_id,
            "count": len(content_entries),
            "digest": _digest_json(content_entries),
        }],
    }
    # Compatibility names expose only duplicate allowlisted facts. They keep the
    # Phase 5A serializers and the legacy restore path able to read a deployment
    # archive without carrying the old detailed storage/settings manifest.
    manifest.update({
        "archive_id": manifest["artifact_id"],
        "scope": "deployment",
        "age_encrypted": True,
        "snapshot_at": manifest["source_timestamp"],
        "build": manifest["build_identity"]["build"],
        "oci_digest": manifest["build_identity"]["oci_digest"],
        "covered_makerspace_ids": population,
        "excluded_makerspace_ids": [],
        "partial": False,
        "recipient_fingerprints": list(main["recipient_fingerprints"]),
        "contents": [{
            "path": main["path"],
            "size": main["size_bytes"],
            "sha256": main["ciphertext_sha256"],
        }],
    })
    if detailed_manifest.get("backup_run_id") is not None:
        manifest["backup_run_id"] = detailed_manifest["backup_run_id"]
    validate_unsigned_manifest(manifest, protocol_version=PROTOCOL_VERSION)
    manifest["archive_signature"] = _signature(manifest, [main])
    return manifest


def verify_outer_manifest(manifest):
    signature = manifest.get("archive_signature")
    if not isinstance(signature, dict) or set(signature) != {
        "algorithm", "signer_fingerprint", "value"
    }:
        raise BackupBuildError("The outer archive signature is malformed.")
    if signature["algorithm"] != "ed25519":
        raise BackupBuildError("The outer archive signature algorithm is unsupported.")
    public = _public_key()
    if signature["signer_fingerprint"] != fingerprint_public_key(public):
        raise BackupBuildError("The host archive verification key does not match the manifest signer.")
    unsigned = dict(manifest)
    unsigned.pop("archive_signature", None)
    validate_unsigned_manifest(unsigned, protocol_version=PROTOCOL_VERSION)
    ledger = [unsigned["main_component"]]
    try:
        raw_signature = base64.b64decode(signature["value"], validate=True)
        verify_bytes(_signature_payload(unsigned, ledger), raw_signature, public)
    except (Ed25519Error, ValueError, KeyError) as exc:
        raise BackupBuildError("The outer archive signature is invalid.") from exc
    return True


def manifest_digest(manifest):
    return hashlib.sha256(_canonical_json(manifest)).hexdigest()


def _signature(manifest, component_ledger):
    private = _private_key()
    public = _public_key()
    try:
        value = sign_bytes(_signature_payload(manifest, component_ledger), private)
    except Ed25519Error as exc:
        raise BackupBuildError("The host archive signing key is invalid.") from exc
    return {
        "algorithm": "ed25519",
        "signer_fingerprint": fingerprint_public_key(public),
        "value": base64.b64encode(value).decode("ascii"),
    }


def _signature_payload(manifest, component_ledger):
    manifest_bytes = _canonical_json(manifest)
    ledger_bytes = _canonical_json(component_ledger)
    return (
        SIGNATURE_DOMAIN
        + len(manifest_bytes).to_bytes(8, "big") + manifest_bytes
        + len(ledger_bytes).to_bytes(8, "big") + ledger_bytes
    )


def _private_key():
    try:
        return decode_key(
            settings.BACKUP_ARCHIVE_SIGNING_PRIVATE_KEY,
            label="private key",
            length=32,
        )
    except Ed25519Error as exc:
        raise BackupBuildError("The host archive signing key is unavailable.") from exc


def _public_key():
    try:
        return decode_key(
            settings.BACKUP_ARCHIVE_VERIFY_PUBLIC_KEY,
            label="public key",
            length=32,
        )
    except Ed25519Error as exc:
        raise BackupBuildError("The host archive verification key is unavailable.") from exc


def _canonical_json(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest_json(value):
    return hashlib.sha256(_canonical_json(value)).hexdigest()
