"""The same storage maintenance callbacks serve full schedulers and free ticks."""
import time
from uuid import uuid4

from celery import shared_task

from .contracts import ChunkContext, JobsUnavailable, admit, chunk_for


def _run(key, *, drain=False):
    callback = chunk_for(key)
    if callback is None:
        raise JobsUnavailable("storage_maintenance_adapter_unavailable")
    deadline, attempt = time.monotonic() + 45, uuid4()
    checkpoint, processed = {}, 0
    while True:
        context = ChunkContext(deadline, admit, checkpoint, attempt, 0, limit=25)
        context.check()
        result = callback(context)
        processed += result.processed
        if result.complete or not drain:
            return {"processed": processed, "remaining": not result.complete}
        if not result.checkpoint or result.checkpoint == checkpoint:
            raise JobsUnavailable("storage_maintenance_no_progress")
        checkpoint = result.checkpoint


@shared_task(name="apps.operations.cloud_jobs.maintenance.refresh_storage")
def refresh_storage():
    # Full schedulers have no persisted chunk cursor. Finish every binding within
    # the same deadline; free ticks call refresh_chunk with their durable cursor.
    return _run("cloud-storage-qualification", drain=True)


@shared_task(name="apps.operations.cloud_jobs.maintenance.sample_storage")
def sample_storage():
    return _run("cloud-storage-usage")


@shared_task(name="apps.operations.cloud_jobs.maintenance.cleanup_staging")
def cleanup_staging():
    return _run("cloud-private-staging-cleanup")
