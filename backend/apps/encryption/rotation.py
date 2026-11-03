"""Per-space key rotation, emergency re-key and search-key rotation (#120, #128 C-26).

All three are started from ``/control/`` by a superadmin after recent re-authentication
and are audited in the space, so its managers see them (``key-events`` API). Each starts
one ``KeyRotationJob`` that ``rekey_tasks`` advances in bounded, retried, idempotent
chunks (X-7) under the space's own RLS scope.

* Rotation and emergency re-key both make a NEW DEK version the write key immediately
  (``services.rotate_dek``), then re-encrypt the space's envelopes to it in the
  background and retire (disable) each old version once nothing references it. The
  emergency form also tells the space's Space Managers when it starts and finishes.
* Search-key rotation makes a BUILDING per-space search key that writes use at once,
  re-indexes the space, then activates it and retires the previous one.

The platform key always works (#120): archives keep their own wrapped copies of every
DEK version, so an old archive still restores after the version is retired here.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.audit import services as audit

from .models import MakerspaceEncryptionKey
from .models_rotation import KeyRotationJob

Kind = KeyRotationJob.Kind


def running_job(makerspace):
    return KeyRotationJob.objects.filter(makerspace=makerspace, status=KeyRotationJob.Status.RUNNING).first()


def _refuse_if_busy(makerspace):
    if running_job(makerspace) is not None:
        raise ValidationError("A key job is already running for this makerspace; wait for it to finish.")


def _create_job(makerspace, **fields):
    try:
        with transaction.atomic():
            return KeyRotationJob.objects.create(makerspace=makerspace, **fields)
    except IntegrityError as exc:  # the one-running-job constraint lost a race
        raise ValidationError("A key job is already running for this makerspace.") from exc


def _enqueue():
    def send():
        try:
            from .rekey_tasks import advance_key_jobs_task
            advance_key_jobs_task.delay()
        except Exception:  # the beat tick (or the free-profile tick) picks it up instead
            pass
    transaction.on_commit(send)


def start_dek_rotation(actor, makerspace, *, emergency=False):
    """Make a new DEK version the write key now, then re-encrypt in the background."""
    from .services import rotate_dek

    from .crypto import PiiUnavailable

    _refuse_if_busy(makerspace)
    current = MakerspaceEncryptionKey.objects.filter(makerspace=makerspace, status="active").first()
    if current is None:
        raise ValidationError("This makerspace has no encryption key yet; nothing to rotate.")
    kind = Kind.EMERGENCY_REKEY if emergency else Kind.ROTATION
    with transaction.atomic():
        try:
            new = rotate_dek(makerspace.pk).key
        except PiiUnavailable as exc:
            raise ValidationError("Encryption is not available on this deployment; nothing to rotate.") from exc
        job = _create_job(makerspace, kind=kind, from_version=current.version, to_version=new.version)
        action = "encryption.emergency_rekey_started" if emergency else "encryption.key_rotated"
        audit.record(actor, action, makerspace=makerspace, target=job,
                     meta={"job_id": job.pk, "from_version": current.version, "to_version": new.version})
    if emergency:
        from .key_notifications import notify
        notify(job)
    _enqueue()
    return job


def start_search_key_rotation(actor, makerspace):
    """Make a new per-space search key the write key now, then re-index the space."""
    from django.conf import settings
    from .search_keys import start_building

    if not settings.PII_ENCRYPTION_ENABLED:
        raise ValidationError("Scoped PII encryption is off on this deployment; there is no search index to rotate.")
    _refuse_if_busy(makerspace)
    with transaction.atomic():
        key = start_building(makerspace.pk)
        job = _create_job(makerspace, kind=Kind.SEARCH_REINDEX, from_version=key.version - 1 or None,
                          to_version=key.version)
        audit.record(actor, "encryption.search_key_rotation_started", makerspace=makerspace, target=job,
                     meta={"job_id": job.pk, "to_version": key.version})
    _enqueue()
    return job
