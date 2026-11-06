"""One space's backup archives on a retired key, from the web console (#190 follow-up).

The per-space half of ``manage.py backup_keys`` and the /control/ keys page: re-encrypt a
one-space archive to today's keys, or purge it. Both run as a Celery job (re-encryption
downloads, rewraps and re-uploads the whole archive, far too long for a request) through
the same ``archive_reencrypt`` services the host command calls.

Durable truth is the archive itself: once re-encrypted it is no longer stale, once purged
it is gone, and both services write their own audit row (``backup.reencrypted`` /
``backup.purged``). The job's progress between "queued" and that outcome is a short-lived
cache entry the console polls. Platform-wide archives and the platform/server key
rotations stay on the server.
"""

import logging

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException

from apps.audit import services as audit

from .models import BackupArchive

logger = logging.getLogger(__name__)
ACTIONS = ("reencrypt", "purge")
TTL = 24 * 60 * 60


class ArchiveKeyConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "archive_key_conflict"

    def __init__(self, code, detail):
        super().__init__({"code": code, "detail": detail})


def _key(archive_id):
    return f"backup:space-archive-key-job:{archive_id}"


def job_state(archive_id):
    return cache.get(_key(archive_id))


def _set(archive_id, action, state, error_code=""):
    cache.set(_key(archive_id), {"action": action, "state": state, "error_code": error_code,
                                 "updated_at": timezone.now().isoformat()}, TTL)


def stale_space_archives(space):
    """This space's one-space archives still encrypted to a retired key, newest first."""
    from .archive_reencrypt import can_reencrypt
    from .platform_key_rotation import stale_archives
    return [{"archive": row, "reencryptable": can_reencrypt(row), "job": job_state(row.pk)}
            for row in stale_archives() if row.scope == BackupArchive.Scope.MAKERSPACE and row.makerspace_id == space.pk]


def queue(actor, space, archive_id, action):
    from .archive_reencrypt import can_reencrypt
    from .platform_key_rotation import stale_archives
    row = next((row for row in stale_archives() if str(row.pk) == str(archive_id)
                and row.scope == BackupArchive.Scope.MAKERSPACE and row.makerspace_id == space.pk), None)
    if row is None:
        raise ArchiveKeyConflict("archive_not_stale", "That archive is not one of this space's archives on a retired key.")
    if (job_state(row.pk) or {}).get("state") in {"queued", "running"}:
        raise ArchiveKeyConflict("archive_job_running", "A job for this archive is already running.")
    if action == "reencrypt" and not can_reencrypt(row):
        raise ArchiveKeyConflict("not_reencryptable", "This server cannot open that archive: purge it or let it expire.")
    _set(row.pk, action, "queued")
    audit.record(actor, "backup.archive_key_job_queued", makerspace=space, target=row,
                 meta={"via": "console", "job": action})

    def send():
        from .tasks_space_keys import space_archive_key_task
        try:
            space_archive_key_task.delay(str(row.pk), action, actor.pk)
        except Exception:  # broker down: say so in the console instead of a silent "queued"
            logger.warning("space_archive_key_job_not_queued", extra={"action": action})
            _set(row.pk, action, "failed", "not_queued")
    transaction.on_commit(send)
    return row


def run(archive_id, action, actor_id):
    """The Celery job's body: one re-encryption or purge, state kept for the console."""
    from apps.accounts.models import User
    from .archive_reencrypt import purge_archive, reencrypt_archive
    row = BackupArchive.objects.filter(pk=archive_id).first()
    if row is None or action not in ACTIONS:
        return None
    _set(row.pk, action, "running")
    try:
        (reencrypt_archive if action == "reencrypt" else purge_archive)(row, actor=User.objects.filter(pk=actor_id).first())
    except Exception as exc:  # every failure becomes a code the console can show; never a raw message
        code = str(getattr(exc, "code", "") or "failed")  # KeyRotationError carries its code
        logger.warning("space_archive_key_job_failed", extra={"action": action, "error_code": code})
        _set(row.pk, action, "failed", code[:64])
        return "failed"
    _set(row.pk, action, "done")
    return "done"
