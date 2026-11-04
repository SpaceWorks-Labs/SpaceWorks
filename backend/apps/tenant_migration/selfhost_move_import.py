"""Target side of a self-host move: import one PORTABLE archive on a fresh install (#128 C-23).

The operator copied the encrypted archive (made with this server's
``TENANT_MIGRATION_AGE_RECIPIENT`` as the one-shot key) and its SHA-256 from the source
superadmin. This runs the ORDINARY import pipeline, in order, as this server's superadmin:
admission (``accept_import_upload``) -> staging (decrypt, format and digest checks) ->
identity decisions -> claim -> materialization and finalization -> activation.

Identity decisions default to creating every person (a fresh server has nobody to link);
staff therefore keep their staff roles ACTIVE and everyone keeps their sign-in from U-D's
credential block (#137 Q-B1, #160). An email this server already holds refuses the
import (#160(3)): pass ``decisions`` naming the person to link instead. Activation uses the
same object verification and readiness gates as a paired cutover, without the pairing
receipt a file handed over offline cannot carry.
"""
import shutil
import uuid
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit

from .models_import_job import ImportIdentityDecision, TenantImportJob

Resolution = ImportIdentityDecision.IdentityResolution
Disposition = ImportIdentityDecision.MembershipDisposition


class SelfHostImportError(RuntimeError):
    def __init__(self, code, detail):
        self.code = code
        super().__init__(detail)


def default_decisions(job):
    from .archive_stream import PortableArchive
    from .import_staging import decrypted_archive
    from .services_import_staging import rows_archive_path

    rows_path = rows_archive_path(job)
    with decrypted_archive(rows_path, require_carried_keys=str(rows_path) == job.archive_path) as (root, _carried):
        users = list(PortableArchive(root).rows("accounts.User"))
    return [{"source_user_id": str(row["id"]), "identity_resolution": Resolution.CREATE_WALK_IN,
             "membership_disposition": Disposition.IMPORT_MEMBERSHIP} for row in users]


def import_selfhost_move(actor, archive, sha256, *, slug=None, decisions=None, activate=True):
    from .services_import_job import claim_import_job, run_import_job, submit_identity_decisions
    from .services_import_staging import accept_import_upload, stage_import_job

    root = Path(settings.BACKUP_OPS_DIR, "tenant-imports")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    copy = root / f"{uuid.uuid4()}.tar.age"
    shutil.copyfile(archive, copy)  # the pipeline owns and later unlinks its own copy
    copy.chmod(0o600)
    job = accept_import_upload(actor=actor, archive_path=copy, size=copy.stat().st_size,
                               source_archive_digest=sha256, expires_at=timezone.now() + timezone.timedelta(
                                   seconds=settings.DATA_EXPORT_RETENTION_SECONDS))
    job = stage_import_job(job.pk, actor_id=actor.pk)
    if job.status == TenantImportJob.Status.FAILED:
        raise SelfHostImportError(job.failure_code or "invalid_archive", job.failure_detail or "Staging failed.")
    if job.status == TenantImportJob.Status.AWAITING_IDENTITY:
        decisions = decisions or default_decisions(job)
        job = submit_identity_decisions(actor=actor, job=job, decisions=decisions)
    target_identity = {"slug": slug} if slug else {}
    job = claim_import_job(actor=actor, job=job, target_identity=target_identity)
    job = run_import_job(job.pk, actor_id=actor.pk, target_identity=target_identity)
    if job.status != TenantImportJob.Status.COMPLETED:
        raise SelfHostImportError(job.failure_code or "import_failed", job.failure_detail or "The import failed.")
    if activate:
        _activate(job)
    job.refresh_from_db()
    audit.record(actor, "selfhost_move.imported", makerspace=job.target_makerspace, target=job, meta={
        "status": "active" if activate else "importing", "source_archive_digest": sha256,
        "people": len(decisions or [])})
    return job


def _activate(job):
    from . import target_state
    from .object_import import delete_staging_objects
    from .object_verification import verify_import_objects
    from .target_cutover import _require_activation_ready

    job = TenantImportJob.objects.select_related("target_makerspace").get(pk=job.pk)
    verify_import_objects(job)
    _require_activation_ready(job)
    with transaction.atomic():
        if target_state.transition_target(job.target_makerspace_id, target_state.IMPORTING, target_state.ACTIVE) != 1:
            raise SelfHostImportError("not_importing", "The imported space is not waiting for activation.")
    delete_staging_objects(job)
