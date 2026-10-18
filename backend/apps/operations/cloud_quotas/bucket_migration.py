"""Empty-bucket handoff under a proved deployment-wide drain.

The source must first be emptied by an audited transfer/retention workflow. This
service refuses data-bearing buckets rather than silently rebinding their keys.
Permanent late-delete receipts keep the old credential reference forever.
"""
import hashlib
import uuid
from dataclasses import asdict

from django.db import transaction

from apps.audit import services as audit
from apps.operations.models import CloudStorageMigrationReceipt, StorageCapabilityState
from apps.storage_capabilities.contracts import CapabilityError
from apps.storage_capabilities.runtime import client_identity


def migrate_empty_binding(*, actor, role, source_contract, destination_contract,
                          source_client, destination_client, retired_destination, owner, guard):
    from apps.backup.managed.writers import assert_capture_drained
    from apps.evidence.models import EvidenceAbandonedUploadReceipt
    from apps.storage_capabilities.verification import verify_and_save, _unbound_migration_probe, verified_state
    from .operator import require_operator
    actor = require_operator(actor)
    if source_contract.identity == destination_contract.identity:
        raise CapabilityError("storage_migration_identity_unchanged")
    if retired_destination.enabled:
        raise CapabilityError("storage_retired_destination_must_be_disabled")
    assert_capture_drained(owner, guard)
    _assert_no_application_references(role)
    source = StorageCapabilityState.objects.get(logical_role=role)
    if source.identity_fingerprint != source_contract.identity.fingerprint:
        raise CapabilityError("storage_migration_source_mismatch")
    if EvidenceAbandonedUploadReceipt.objects.filter(storage_identity="").exists():
        raise CapabilityError("storage_legacy_receipt_binding_required")
    from apps.backup.offsite_client import destination_client as retired_client
    old_client = retired_client(retired_destination)
    try:
        if client_identity(old_client, retired_destination.bucket) != source_contract.identity:
            raise CapabilityError("storage_retired_identity_mismatch")
    finally:
        old_client.close()
    if client_identity(source_client, source_contract.identity.bucket) != source_contract.identity:
        raise CapabilityError("storage_migration_source_mismatch")
    # Refresh the OLD contract while the old configuration is still installed.
    from apps.storage_clients import qualification
    with qualification():
        verify_and_save(source_client, source_contract)
        bucket = source_contract.identity.bucket
        from apps.storage_capabilities.deletion import version_pages
        if source_contract.versioning == "never_versioned":
            if source_client.list_objects_v2(Bucket=bucket, MaxKeys=1).get("Contents"):
                raise CapabilityError("storage_migration_source_not_empty")
        else:
            for page in version_pages(source_client, bucket=bucket, prefix="", max_keys=1):
                if page.get("Versions") or page.get("DeleteMarkers"):
                    raise CapabilityError("storage_migration_source_not_empty")
        if source_client.list_multipart_uploads(Bucket=bucket, MaxUploads=1).get("Uploads"):
            raise CapabilityError("storage_migration_incomplete_uploads_remain")
        token = _unbound_migration_probe.set(True)
        try:
            verify_and_save(destination_client, destination_contract)
        finally:
            _unbound_migration_probe.reset(token)
    assert_capture_drained(owner, guard)
    _assert_no_application_references(role)
    digest = hashlib.sha256(f"empty:{source.identity_fingerprint}:{source.generation}".encode()).hexdigest()
    with transaction.atomic():
        source = StorageCapabilityState.objects.select_for_update().get(pk=source.pk)
        target = StorageCapabilityState.objects.select_for_update().get(identity_fingerprint=destination_contract.identity.fingerprint)
        if source.logical_role != role or target.logical_role is not None:
            raise CapabilityError("storage_migration_binding_changed")
        receipt = CloudStorageMigrationReceipt.objects.create(role=role, source_identity=source.identity_fingerprint,
            destination_identity=target.identity_fingerprint, inventory_digest=digest, retired_destination=retired_destination,
            source_contract=_descriptor(source_contract), pause_owner=uuid.UUID(str(owner)))
        source.logical_role = None
        source.save(update_fields=["logical_role"])
        target.logical_role = role
        target.save(update_fields=["logical_role"])
        audit.record(actor, "storage.bucket_binding_migrated", target=receipt,
            meta={"receipt_id": receipt.pk, "inventory_sha256": digest, "role": role})
    return receipt


def _descriptor(contract):
    values = asdict(contract)
    identity = values.pop("identity")
    values["presign_methods"] = sorted(values["presign_methods"])
    return {**identity, **values}


def _assert_no_application_references(role):
    """Physical absence cannot certify a populated application's new bucket."""
    from django.apps import apps
    if role == "anchor":
        if apps.get_model("audit", "AuditBatch").objects.exists():
            raise CapabilityError("storage_empty_deployment_handoff_required")
        return
    from apps.backup.object_ownership_registry import BucketRule, validate_object_reference_registry
    for rule in validate_object_reference_registry():
        if rule.bucket != role and rule.bucket != BucketRule.FROM_ROW:
            continue
        if rule.model_label == "evidence.EvidenceAbandonedUploadReceipt":
            continue  # Permanent old-bucket deletion authority travels separately.
        model = apps.get_model(rule.model_label)
        rows = model._base_manager.exclude(**{rule.field_name: ""}).exclude(**{rule.field_name: None})
        if rule.bucket == BucketRule.FROM_ROW:
            rows = rows.filter(bucket_kind=role)
        if rule.retention_aware:
            rows = rows.exclude(object_retention_state__status="expired",
                                object_retention_state__object_expired_at__isnull=False)
        if rule.model_label == "backup.ManagedStagedObject":
            rows = rows.filter(deleted_at__isnull=True)
        if rule.model_label == "backup.BackupArchive":
            rows = rows.exclude(status="expired")
        if rows.exists():
            raise CapabilityError("storage_live_application_references_remain")
    if role == "private":
        if apps.get_model("audit", "AuditLog").objects.filter(meta__has_key="object_key").exists():
            raise CapabilityError("storage_audit_object_references_remain")
        certificates = apps.get_model("events", "EventAttendanceCertificate").objects.filter(
            layout_snapshot__has_key="artwork_object_key").exclude(layout_snapshot__artwork_object_key="").exclude(
            layout_snapshot__artwork_object_key=None)
        if certificates.exists():
            raise CapabilityError("storage_certificate_object_references_remain")
