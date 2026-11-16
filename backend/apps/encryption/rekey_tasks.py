"""The background half of rotation, emergency re-key and search-key rotation (X-7, #133).

One beat task advances every running ``KeyRotationJob`` by a bounded chunk per tick. Each
chunk runs inside ``fanout_tenant_write`` (the tenant's source gate and its RLS scope),
is one transaction per model batch, and is idempotent: a row already on the target
version is left alone, so a retried or resumed chunk repeats nothing. A job that keeps
failing is marked failed after ``MAX_ATTEMPTS``; the new key is already in use by then,
so a failure only leaves old versions retained, never data unreadable.
"""

import logging

from celery import shared_task
from django.apps import apps
from django.db import connection

from .models_rotation import KeyRotationJob
from .rekey_rows import labels_for, queryset_for, reencrypt_rows, reindex_rows
from .rekey_finish import fail, finish

logger = logging.getLogger(__name__)
BATCH = 200
MAX_ATTEMPTS = 5
JOBS_PER_TICK = 3
LOCK_NAMESPACE = 734_210


def _locked(job_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s, %s)", [LOCK_NAMESPACE, job_id])
        return cursor.fetchone()[0]


def _unlock(job_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_unlock(%s, %s)", [LOCK_NAMESPACE, job_id])


def advance(job, budget=BATCH):
    """Process up to ``budget`` rows inside the caller's tenant boundary; True when all are done."""
    labels = labels_for(job.kind)
    position = dict(job.cursor or {})
    index, after = position.get("i", 0), position.get("after")
    while budget > 0 and index < len(labels):
        label = labels[index]
        model = apps.get_model(label)
        rows = queryset_for(label, job.makerspace_id)
        if after is not None:
            rows = rows.filter(pk__gt=after)
        ids = list(rows.order_by("pk").values_list("pk", flat=True)[:budget])
        if not ids:
            index, after = index + 1, None
            continue
        work = reindex_rows if job.kind == KeyRotationJob.Kind.SEARCH_REINDEX else reencrypt_rows
        done, skipped = work(job, model, ids)
        job.rows_done += done
        job.rows_skipped += skipped
        after = ids[-1] if isinstance(ids[-1], int) else str(ids[-1])
        budget -= len(ids)
    job.cursor = {"i": index, "after": after}
    job.save(update_fields=["cursor", "rows_done", "rows_skipped", "updated_at"])
    return index >= len(labels)


def _record_failure(job, exc):
    logger.exception("encryption_key_job_chunk_failed", extra={"job_id": job.pk})
    job.refresh_from_db()
    job.attempts += 1
    job.error_code = exc.__class__.__name__[:64]
    job.save(update_fields=["attempts", "error_code", "updated_at"])
    if job.attempts >= MAX_ATTEMPTS:
        fail(job)
        return False
    return True


def advance_running(limit=JOBS_PER_TICK, budget=BATCH):
    """Advance a bounded number of running jobs, each inside its tenant's source-gate boundary
    (a frozen space is skipped and resumed on a later tick); return how many still have work."""
    from apps.tenant_migration.gate_runtime import fanout_tenant_write

    remaining, counts = 0, {}
    for job in KeyRotationJob.objects.filter(status=KeyRotationJob.Status.RUNNING).order_by("started_at")[:limit]:
        if not _locked(job.pk):
            continue
        try:
            job.refresh_from_db()
            finished = False
            with fanout_tenant_write(job.makerspace_id, operation="encryption.key_job", counts=counts) as admitted:
                if not admitted:
                    continue
                finished = job.status == KeyRotationJob.Status.RUNNING and advance(job, budget)
            if finished:
                finish(job)
            elif job.status == KeyRotationJob.Status.RUNNING:
                remaining += 1
        except Exception as exc:  # retried next tick, then failed
            remaining += _record_failure(job, exc)
        finally:
            _unlock(job.pk)
    return remaining


@shared_task(bind=True, max_retries=0)
def advance_key_jobs_task(self):
    """Lane L8: one bounded chunk of every running per-space key job (beat, every minute)."""
    remaining = advance_running()
    if remaining:
        try:
            advance_key_jobs_task.apply_async(countdown=5)
        except Exception:
            pass  # no broker (free profile): the next tick continues
    return remaining

