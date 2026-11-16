"""Canonical facts for the deployment archive's single main component."""

import hashlib
import json

from apps.backup.age_recipients import fingerprint_for
from apps.backup.digests import sha256_file
from apps.backup.outer_manifest_validation import component_id


def main_component_fact(capture, root):
    main_path = root / "database.dump"
    return {
        "component_id": component_id(capture.capture_id, "main"),
        "kind": "main",
        "path": "database.dump",
        "size_bytes": main_path.stat().st_size,
        "ciphertext_sha256": sha256_file(main_path),
        "schema_catalog_digest": capture.source_catalog_digest,
        "semantic_digest": digest_json(capture.expected_main_ledger),
        "recipient_fingerprints": sorted(
            fingerprint_for(value) for value in capture.platform_recipients
        ),
    }


def digest_json(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        default=str,
    ).encode("utf-8")).hexdigest()
