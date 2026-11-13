"""Structural allowlist validation for the signed deployment-archive manifest."""

import uuid

from apps.backup.build_errors import BackupBuildError


def component_id(capture_id, kind, makerspace_id=None):
    namespace = uuid.UUID(str(capture_id))
    tenant = "" if makerspace_id is None else str(int(makerspace_id))
    return str(uuid.uuid5(namespace, f"component:{kind}:{tenant}"))


def validate_unsigned_manifest(manifest, *, protocol_version):
    try:
        if manifest["protocol_version"] != protocol_version:
            raise ValueError
        capture_id = uuid.UUID(str(manifest["capture_id"]))
        uuid.UUID(str(manifest["artifact_id"]))
        if "backup_run_id" in manifest:
            uuid.UUID(str(manifest["backup_run_id"]))
        build_identity = manifest["build_identity"]
        postgres = manifest["postgres"]
        if (
            not isinstance(build_identity, dict)
            or set(build_identity) != {"build", "oci_digest"}
            or not isinstance(build_identity["build"], dict)
            or not isinstance(build_identity["build"].get("source_hash"), str)
            or not build_identity["build"]["source_hash"]
            or not isinstance(build_identity["oci_digest"], str)
            or not isinstance(postgres, dict)
            or set(postgres) != {
                "source_server_major", "client", "supported_source_majors"
            }
            or type(postgres["source_server_major"]) is not int
            or not 10 <= postgres["source_server_major"] <= 99
            or not isinstance(postgres["client"], str)
            or not postgres["client"]
            or not isinstance(postgres["supported_source_majors"], list)
            or postgres["supported_source_majors"]
            != sorted(set(postgres["supported_source_majors"]))
            or any(
                type(value) is not int or not 10 <= value <= 99
                for value in postgres["supported_source_majors"]
            )
            or postgres["source_server_major"]
            not in postgres["supported_source_majors"]
        ):
            raise ValueError
        population = manifest["makerspace_ids"]
        if (
            population != sorted(set(population))
            or any(type(value) is not int or value <= 0 for value in population)
        ):
            raise ValueError
        main = manifest["main_component"]
        main_fingerprints = main["recipient_fingerprints"]
        if (
            main["kind"] != "main"
            or main["component_id"] != component_id(capture_id, "main")
            or not _is_digest(main["ciphertext_sha256"])
            or not _is_digest(main["schema_catalog_digest"])
            or not _is_digest(main["semantic_digest"])
            or not main_fingerprints
            or main_fingerprints != sorted(set(main_fingerprints))
            or any(not _is_digest(value) for value in main_fingerprints)
        ):
            raise ValueError
        for ledger_name in ("object_ledgers", "content_ledgers"):
            ledger = manifest[ledger_name]
            if (
                len(ledger) != 1
                or ledger[0]["component_id"] != main["component_id"]
                or not _is_digest(ledger[0]["digest"])
            ):
                raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise BackupBuildError("The outer archive manifest structure is invalid.") from exc


def _is_digest(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
