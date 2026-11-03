"""Finishing a key job: retire what nothing references any more, record it, tell the managers."""

from django.apps import apps
from django.utils import timezone

from apps.audit import services as audit

from .crypto import PiiUnavailable
from .models import MakerspaceEncryptionKey
from .models_rotation import KeyRotationJob
from .registry import fields_for_label, registered_labels

Kind = KeyRotationJob.Kind


def version_referenced(makerspace_id, version):
    """True while any mapped envelope of the space still names ``version``."""
    prefix = f"pii:gcm:v1:{version}:"
    for label in registered_labels():
        try:
            model = apps.get_model(label)
        except LookupError:
            continue
        fields = fields_for_label(label)
        path = fields[0].makerspace_path.replace(".", "__")
        rows = model._base_manager.filter(**{path: makerspace_id})
        if any(rows.filter(**{f"{field.field_name}__startswith": prefix}).exists() for field in fields):
            return True
    return False


def _retire_old_versions(job):
    from .services import disable_dek

    retained = []
    old = MakerspaceEncryptionKey.objects.filter(
        makerspace_id=job.makerspace_id, version__lt=job.to_version).exclude(status="disabled").order_by("version")
    for key in old:
        if version_referenced(job.makerspace_id, key.version):
            retained.append(key.version)
            continue
        try:
            disable_dek(job.makerspace_id, key.version)
        except PiiUnavailable:
            retained.append(key.version)
    return retained


def _close(job, status):
    job.status = status
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "completed_at", "retained_versions", "error_code", "updated_at"])


def finish(job):
    makerspace = job.makerspace
    if job.kind == Kind.SEARCH_REINDEX:
        from .search_keys import activate
        activate(job.makerspace_id, job.to_version)
        _close(job, KeyRotationJob.Status.COMPLETED)
        audit.record(None, "encryption.search_reindexed", makerspace=makerspace, target=job,
                     meta={"job_id": job.pk, "to_version": job.to_version, "rows": job.rows_done})
        return
    job.retained_versions = _retire_old_versions(job)
    _close(job, KeyRotationJob.Status.COMPLETED)
    action = ("encryption.emergency_rekey_completed" if job.kind == Kind.EMERGENCY_REKEY
              else "encryption.key_rotation_completed")
    audit.record(None, action, makerspace=makerspace, target=job, meta={
        "job_id": job.pk, "to_version": job.to_version, "rows": job.rows_done,
        "skipped": job.rows_skipped, "retained_versions": job.retained_versions})
    if job.kind == Kind.EMERGENCY_REKEY:
        from .key_notifications import notify
        notify(job)


def fail(job):
    _close(job, KeyRotationJob.Status.FAILED)
    audit.record(None, "encryption.key_job_failed", makerspace=job.makerspace, target=job,
                 meta={"job_id": job.pk, "kind": job.kind, "error": job.error_code})
    if job.kind == Kind.EMERGENCY_REKEY:
        from .key_notifications import notify
        notify(job)
