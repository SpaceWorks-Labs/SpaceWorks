"""Finance upload allocation/presign port. Claim parents are owned by R."""
from datetime import timedelta
from uuid import uuid4
from django.db import connection
from django.utils import timezone
from apps.accounts.staff_identity import is_person
from apps.audit.services import record
from apps.makerspaces.private_upload_transport import ObjectLocator, UploadRequest, bounded_not_after
from .attachment_models import FinanceAttachment
from .cleanup_models import FinanceObjectCleanup
from .attachment_policy import validate_upload, reserve_locked, policy_snapshot
from .attachment_storage import FinanceStorage, bucket, asset_bucket
from .errors import require


def create_locked(*, makerspace, event_id, event_title, owner, binding_kind, binding_uuid,
                  data, actor, obligation=None):
    """Caller holds source/fences/host and claim-or-obligation parents; no I/O."""
    require(connection.in_atomic_block, "locked_transaction_required")
    from .scan_policy import current
    scanner_policy = current()
    purpose = "reimbursement_receipt" if binding_kind == "claim" else "reimbursement_payee_document"
    require(binding_kind in ("claim", "payee"), "invalid_attachment_binding", status=400)
    require(owner is not None and is_person(owner), "invalid_attachment_owner")
    if obligation is not None:
        require(obligation.makerspace_id == makerspace.pk and obligation.event_id_snapshot == event_id
            and obligation.owner_member_id == owner.pk, "attachment_scope_mismatch")
        require(binding_kind != "claim" or obligation.source_uuid == binding_uuid, "invalid_attachment_binding")
    validate_upload(data, purpose=purpose)
    reserve_locked(makerspace_id=makerspace.pk, event_id=event_id, owner_id=owner.pk,
        binding_uuid=binding_uuid, question_id=data["question_id"], size=data["bytes"])
    if binding_kind == "payee":
        require(obligation is not None and obligation.state == "open" and obligation.owner_member_id == owner.pk,
                "payee_not_requested")
        payee = obligation.payee_revisions.filter(pk=binding_uuid, state="current").first()
        require(payee is not None and data["question_id"] == "routing_document", "not_found", status=404)
        from .templates import configured_templates
        _, documents = configured_templates(makerspace.pk)
        require((payee.country, payee.method) in documents, "routing_document_not_requested")
    policy, days = policy_snapshot(makerspace.pk, purpose)
    opaque = uuid4().hex
    row = FinanceAttachment.objects.create(makerspace=makerspace, event_id=obligation.event_id if obligation else event_id,
        event_id_snapshot=event_id, event_title_snapshot=event_title, owner_member=owner, purpose=purpose,
        binding_kind=binding_kind, binding_uuid=binding_uuid, question_id=data["question_id"],
        expected_bytes=data["bytes"], declared_mime=data["mime"], original_filename=data["filename"].strip(),
        staging_key=f"finance/{makerspace.pk}/staging/{opaque}", object_key=f"finance/{makerspace.pk}/final/{opaque}",
        scanner_policy=scanner_policy.backend, obligation=obligation,
        retention_policy_revision=policy, retention_days_snapshot=days)
    FinanceObjectCleanup.objects.create(source_makerspace_id=makerspace.pk, asset_id=row.pk, bucket=bucket(),
        staging_key=row.staging_key, object_key=row.object_key)
    record(actor, "finance.attachment.initiated", makerspace=makerspace, target=row,
           meta={"asset_id": row.pk, "purpose": purpose, "generation": row.generation})
    return row


def presign(row, *, deadline=None, storage=None):
    require(not connection.in_atomic_block, "storage_io_in_transaction")
    require(row.state == "initiated", "upload_not_initiated")
    now = timezone.now()
    expires = bounded_not_after(now=now, purpose_max_seconds=900,
        limits=(deadline, row.created_at + timedelta(hours=24)))
    bucket_name = asset_bucket(row.pk)
    upload = (storage or FinanceStorage(bucket_name=bucket_name)).initialize(UploadRequest(staging=ObjectLocator(bucket=bucket_name, key=row.staging_key),
        generation=row.generation, mime=row.declared_mime, size_bytes=row.expected_bytes, not_after=expires))
    return {"asset_id": row.pk, "generation": row.generation, "state": row.state,
        "upload": {"method": upload.method, "url": upload.url, "fields": upload.fields, "expires_at": upload.expires_at}}
