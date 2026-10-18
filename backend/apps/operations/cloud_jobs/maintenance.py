"""The same storage maintenance callbacks serve full schedulers and free ticks."""
import time
from uuid import uuid4

from celery import shared_task

from .contracts import ChunkContext, JobsUnavailable, admit, chunk_for


def _run(key):
    callback = chunk_for(key)
    if callback is None:
        raise JobsUnavailable("storage_maintenance_adapter_unavailable")
    result = callback(ChunkContext(time.monotonic() + 45, admit, {}, uuid4(), 0, limit=25))
    return {"processed": result.processed, "remaining": not result.complete}


@shared_task(name="apps.operations.cloud_jobs.maintenance.refresh_storage")
def refresh_storage():
    return _run("cloud-storage-qualification")


@shared_task(name="apps.operations.cloud_jobs.maintenance.sample_storage")
def sample_storage():
    return _run("cloud-storage-usage")


@shared_task(name="apps.operations.cloud_jobs.maintenance.cleanup_staging")
def cleanup_staging():
    return _run("cloud-private-staging-cleanup")
