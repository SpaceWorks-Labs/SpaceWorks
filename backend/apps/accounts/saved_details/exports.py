"""Owner-only short-lived archives contain vault values and independently owned files."""
from datetime import timedelta
import hashlib
import tempfile
from uuid import uuid4
import zipfile

from django.utils import timezone

from apps.audit.services import record
from apps.encryption.account_mappers import account_key_context
from apps.encryption.account_services import prepare_account_key
from apps.encryption.account_write_fence import account_write
from apps.makerspaces.private_upload_transport import ObjectLocator, resolve_range, stream_private

from . import storage
from .access import owner_read_gate, require_owner
from .commands import remember, replay, request_digest
from .crypto import canonical
from .downloads import own_export
from .errors import SavedDetailsError
from .models import AccountSavedDetailsExportJob, MemberSavedAsset, SavedDetailsObjectCleanup
from .workflow import list_details


def project(job):
    return {"job_id": str(job.job_uuid), "state": job.state, "expires_at": job.expires_at.isoformat()}


def create_export(actor_id, operation_id):
    require_owner(actor_id)
    digest = request_digest("export", {})
    previous = replay(actor_id, operation_id, digest)
    if previous is not None:
        return previous
    key = prepare_account_key(actor_id)
    with account_write(actor_id), account_key_context(key):
        actor = require_owner(actor_id, lock=True)
        previous = replay(actor_id, operation_id, digest, key=key)
        if previous is not None:
            return previous
        if AccountSavedDetailsExportJob.objects.filter(user=actor, state__in=["queued", "building"]).exists():
            raise SavedDetailsError("export_pending", "An export is already being prepared.", 409)
        job = AccountSavedDetailsExportJob.objects.create(user=actor,
            object_key=f"account-export/{uuid4()}.zip", expires_at=timezone.now() + timedelta(hours=24))
        record(actor, "account.saved_details_export_requested", target=job)
        return remember(actor_id, operation_id, digest, {"job_id": str(job.job_uuid), "state": "queued",
            "status_url": f"/api/v1/member/saved-details/export/{job.job_uuid}/"}, key)


def build_export(job_id):
    pending = AccountSavedDetailsExportJob.objects.filter(pk=job_id).first()
    if not pending or pending.state not in {"queued", "building"}:
        return
    with account_write(pending.user_id):
        actor = require_owner(pending.user_id, lock=True)
        job = AccountSavedDetailsExportJob.objects.select_for_update().get(pk=job_id)
        if job.state != "queued" and not (job.state == "building" and job.started_at and job.started_at < timezone.now() - timedelta(minutes=15)):
            return
        job.state, job.claim_uuid = "building", uuid4()
        job.started_at = timezone.now()
        output_key = f"account-export/{job.job_uuid}/{job.claim_uuid}.zip"
        job.cleanup_keys.append(output_key)
        job.save(update_fields=["state", "claim_uuid", "started_at", "cleanup_keys"])
        # Registered before storage I/O so erase/crash/late losing workers cannot
        # orphan an archive. The winner removes its receipt in the final CAS.
        cleanup = SavedDetailsObjectCleanup.objects.create(object_keys=[output_key], next_attempt_at=job.expires_at)
        record(actor, "account.saved_details_export_started", target=job)
    try:
        authorize_key = owner_read_gate(actor.pk)
        with tempfile.SpooledTemporaryFile(max_size=8 * 1024**2) as archive:
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
                details = list_details(actor.pk)
                zipped.writestr("saved-details.json", canonical(details))
                for asset in MemberSavedAsset.objects.filter(user=actor, state="ready").order_by("pk"):
                    def authorize():
                        authorize_key()
                        own_export(actor.pk, job.job_uuid)
                        if not MemberSavedAsset.objects.filter(pk=asset.pk, user=actor, state="ready", version=asset.version).exists():
                            raise SavedDetailsError("asset_not_ready", "A résumé changed during export.", 409)
                        from .asset_policy import require_ready
                        require_ready(asset)
                    with zipped.open(f"resumes/{asset.public_id}.pdf", "w") as target:
                        for chunk in stream_private(locator=ObjectLocator(bucket=storage.bucket(), key=asset.object_key,
                            version_id=asset.final_version_id or None), byte_range=resolve_range(None, asset.size_bytes),
                            reader=storage.read_range, authorize=authorize, clock=timezone.now, not_after=job.expires_at):
                            target.write(chunk)
            size = archive.tell()
            archive.seek(0)
            checksum = hashlib.file_digest(archive, "sha256").hexdigest()
            archive.seek(0)
            require_owner(actor.pk)
            storage.put_archive(output_key, archive)
        code = ""
    except Exception:
        size, checksum, code = 0, "", "export_build_failed"
    with account_write(actor.pk):
        actor = require_owner(actor.pk, lock=True)
        current = AccountSavedDetailsExportJob.objects.select_for_update().filter(
            pk=job_id, claim_uuid=job.claim_uuid, state="building", expires_at__gt=timezone.now()).first()
        if current is None:
            return
        current.state = "failed" if code else "ready"
        current.failure_code, current.size_bytes, current.sha256 = code, size, checksum
        if not code:
            current.object_key = output_key
            cleanup.delete()
        current.save()
        record(actor, "account.saved_details_export_completed", target=current, meta={"state": current.state})
