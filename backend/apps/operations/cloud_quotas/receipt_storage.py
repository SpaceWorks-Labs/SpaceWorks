"""Permanent late deletion follows its recorded bucket through a role migration."""
from django.conf import settings
from django.db import connection, transaction

from apps.audit import services as audit
from apps.operations.models import CloudStorageMigrationReceipt, StorageCapabilityState
from apps.storage_capabilities.contracts import CapabilityError
from apps.storage_capabilities.runtime import client_identity


def bind_legacy_receipts(*, actor):
    from .operator import require_operator
    actor = require_operator(actor)
    from apps.evidence import storage
    from apps.evidence.models import EvidenceAbandonedUploadReceipt
    client = storage._client()
    try:
        identity = client_identity(client, settings.AWS_STORAGE_BUCKET_NAME).fingerprint
    finally:
        client.close()
    count = 0
    # No provider calls or credentials occur inside these short row transactions.
    for pk in EvidenceAbandonedUploadReceipt.objects.filter(storage_identity="").values_list("pk", flat=True).iterator(chunk_size=100):
        with transaction.atomic():
            row = EvidenceAbandonedUploadReceipt.objects.select_for_update().get(pk=pk)
            if row.storage_identity:
                continue
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.evidence_receipt_bind_id', %s, true)", [str(pk)])
                cursor.execute("UPDATE evidence_evidenceabandoneduploadreceipt SET storage_identity=%s WHERE id=%s", [identity, pk])
                cursor.execute("SELECT set_config('app.evidence_receipt_bind_id', '', true)")
            audit.record(actor, "storage.legacy_receipt_bound", target=row,
                         meta={"receipt_id": pk, "identity_fingerprint": identity})
            count += 1
    return count


def delete_receipt_keys(receipt):
    from apps.evidence import storage
    from apps.object_storage import delete_all_versions
    if not receipt.storage_identity:
        # Full legacy deployments keep existing behavior until a binding has ever
        # been persisted; managed rebinds require the explicit backfill first.
        if getattr(settings, "SPACEWORKS_DEPLOYMENT_MODE", "host") != "managed":
            storage.delete_object_strict(receipt.object_key)
            storage.delete_object_strict(storage.staging_key(receipt.object_key))
            return
        raise CapabilityError("storage_legacy_receipt_binding_required")
    state = StorageCapabilityState.objects.get(identity_fingerprint=receipt.storage_identity)
    if state.logical_role == "private":
        client, bucket = storage._client(), state.identity["bucket"]
    else:
        migration = CloudStorageMigrationReceipt.objects.filter(source_identity=receipt.storage_identity).order_by("pk").first()
        if not migration:
            raise CapabilityError("storage_retired_credentials_required")
        from apps.backup.offsite_client import destination_client
        destination = migration.retired_destination
        client, bucket = destination_client(destination), destination.bucket
        if client_identity(client, bucket).fingerprint != receipt.storage_identity:
            client.close()
            raise CapabilityError("storage_retired_identity_mismatch")
    try:
        retired_contract = None
        if state.logical_role != "private":
            from apps.storage_capabilities.configuration import _contract
            from apps.storage_capabilities.probes import inspect_bucket
            retired_contract = _contract(migration.source_contract, allow_no_upload=True)
            inspect_bucket(client, retired_contract)
        for key in (receipt.object_key, storage.staging_key(receipt.object_key)):
            # Late re-deletion repairs physical absence; it is not a new credit.
            if retired_contract is None:
                delete_all_versions(client, bucket=bucket, key=key)
            else:
                from apps.storage_capabilities.deletion import delete_exact_key
                delete_exact_key(client, bucket=bucket, key=key,
                    never_versioned=not state.history_possible and retired_contract.versioning == "never_versioned")
    finally:
        client.close()
