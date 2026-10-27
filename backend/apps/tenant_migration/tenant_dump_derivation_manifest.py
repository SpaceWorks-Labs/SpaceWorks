"""Pure Lane D derivation manifest assembly."""
from .tenant_dump_lineage import FORMAT
from .tenant_dump_key_inventory import manifest_key_inventory
from .tenant_dump_envelope import TENANT_DEKS_MEMBER

def _manifest(
    capture,
    build,
    objects,
    projection,
    policy_digest,
    *,
    pii_mode,
    pii_findings,
    retained_keys,
    key_envelope,
):
    return {
        "format": FORMAT,
        "capture_id": str(capture.pk),
        "source_pii_mode": pii_mode,
        "source": {
            "deployment_identity": capture.source_deployment_identity,
            "makerspace_id": capture.source_makerspace_id,
            "makerspace_slug": capture.source_makerspace_slug,
            "request_actor_id": capture.requested_by_id,
            "gate_owner_id": str(capture.gate_owner_id),
            "gate_fencing_token": capture.gate_fencing_token,
            "tenant_recipients": capture.tenant_recipients,
            "database_snapshot_at": capture.database_snapshot_at.isoformat(),
            "postgres_major": capture.source_postgres_major,
            "encryption_mode": capture.source_encryption_mode,
            "source_pii_mode": pii_mode,
            "catalog_digest": capture.catalog_digest,
            "capture_completed_at": capture.capture_completed_at.isoformat(),
        },
        "lineage": {
            "database_image_sha256": capture.database_image_sha256,
            "object_ledger_sha256": capture.object_ledger_sha256,
            "derivation_policy_sha256": policy_digest,
        },
        "database": {
            "member_path": "database.dump",
            "mapped_raw_sha256": build.mapped_raw_sha256,
            "sequence_state": build.sequence_state,
        },
        "objects": list(objects),
        "encryption": {
            "source_pii_mode": pii_mode,
            "mapped_column_findings": pii_findings.as_manifest(),
            "retained_key_inventory": manifest_key_inventory(retained_keys),
            "tenant_dek_envelope": key_envelope or {
                "path": TENANT_DEKS_MEMBER,
                "present": False,
            },
        },
        "machine_operator_manifest": list(projection.machine_operator_manifest),
        "user_closure": projection.user_closure.manifest(),
        "cross_tenant_lost_edges": list(projection.cross_tenant_lost_edges),
    }

