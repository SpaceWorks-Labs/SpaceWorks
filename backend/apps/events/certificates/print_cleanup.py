"""Durable cleanup adapter, including expired/revoked jobs and failed reservations."""
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from apps.audit.services import record
from apps.events.credentials.boundary import event_command
from apps.makerspaces import limits
from .print_models import BadgePrintJob, BadgePrintResource
from . import print_storage


def cleanup_job(job_id, *, force=False):
    job = BadgePrintJob.objects.get(pk=job_id)
    if not force and job.expires_at > timezone.now() and job.state != "cancelled":
        return False
    # All versions are removed before quota is released. Repeated cleanup is safe.
    with event_command(job.event_id) as (event, _):
        locked = BadgePrintJob.objects.select_for_update().get(pk=job.pk)
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
    print_storage.delete(job.object_key)
    with event_command(job.event_id) as (event, _):
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
    ids = list(BadgePrintJob.objects.filter(Q(next_cleanup_at__isnull=True) | Q(next_cleanup_at__lte=timezone.now()),
                                           expires_at__lte=timezone.now())
               .order_by("pk").values_list("pk", flat=True)[:limit])
    for pk in ids:
        cleanup_job(pk)
    return len(ids)
