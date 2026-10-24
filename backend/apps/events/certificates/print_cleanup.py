"""Durable cleanup adapter, including expired/revoked jobs and failed reservations."""
from apps.operations.cloud_jobs import bounded
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from apps.audit.services import record
from apps.events.tasks_retention import _retention_event
from apps.makerspaces import limits
from .print_models import BadgePrintJob, BadgePrintResource
from . import print_storage


def cleanup_job(job_id, *, force=False):
    job = BadgePrintJob.objects.get(pk=job_id)
    if not force and job.expires_at > timezone.now() and job.state != "cancelled":
        return False
    # All versions are removed before quota is released. Repeated cleanup is safe.
    with _retention_event(job.event_id) as event:
        locked = BadgePrintJob.objects.select_for_update().get(pk=job.pk)
        if not force and locked.expires_at > timezone.now() and locked.state != "cancelled":
            return False
        if locked.state != "cancelled":
            locked.state = "cancelled"
            locked.save(update_fields=("state",))
            record(None, "event.badge_print_cancelled", makerspace=event.makerspace, target=locked)
    # Repeat deletion on later passes to catch a bounded storage write which was
    # already in flight when cancellation won. Quota is still freed only once.
    rows = list(job.resources.all())
    for row in rows:
        if row.object_key:
            print_storage.delete(row.object_key)
    if job.object_key:
        print_storage.delete(job.object_key)
    with _retention_event(job.event_id) as event:
        locked = BadgePrintJob.objects.select_for_update().get(pk=job.pk)
        for resource in BadgePrintResource.objects.select_for_update().filter(job=locked, cleaned_at__isnull=True):
            limits.free_storage(event.makerspace, resource.size_bytes)
            resource.cleaned_at = timezone.now()
            resource.save(update_fields=("cleaned_at",))
        if locked.cleaned_at is None:
            limits.free_storage(event.makerspace, locked.size_bytes)
            locked.cleaned_at, locked.state = timezone.now(), "cancelled"
            locked.save(update_fields=("cleaned_at", "state"))
            record(None, "event.badge_print_cleaned", makerspace=event.makerspace, target=locked)
        locked.next_cleanup_at = timezone.now()+timedelta(hours=6)
        locked.save(update_fields=("next_cleanup_at",))
    return True


def cleanup_expired(limit=100):
    import logging
    from apps.events.tasks_sweeps import take_ids
    eligible = BadgePrintJob.objects.filter(Q(next_cleanup_at__isnull=True) | Q(next_cleanup_at__lte=timezone.now())).filter(
        Q(expires_at__lte=timezone.now()) | Q(state="cancelled"))
    ids = take_ids("badge-print-cleanup", eligible, limit=limit)
    for pk in bounded.items(ids):
        try:
            cleanup_job(pk)
        except Exception:
            logging.getLogger(__name__).warning("event_badge_cleanup_deferred", extra={"job_id": pk})
    return len(ids)


from .print_custody import capture_purge_locked  # Explicit purge integration entry point.
