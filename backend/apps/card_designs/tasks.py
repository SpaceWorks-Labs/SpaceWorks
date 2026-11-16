"""Celery tasks for card jobs, font fetches and result retention (#133, X-7).

Full server: each chunk dispatches the next. Free profile: `resume_card_jobs` runs on
the cloud tick and processes one chunk per job inside the bounded adapter, never by
recursion. Broker loss never loses a job: the resume sweep rediscovers it.
"""
import logging

from celery import shared_task

from apps.operations.cloud_jobs import bounded

logger = logging.getLogger(__name__)


def dispatch(job_id):
    try:
        process_card_job.delay(job_id)
    except Exception:
        logger.warning("card_job_dispatch_failed", extra={"job_id": job_id})


@shared_task
def process_card_job(job_id):
    from .job_runner import run_chunk
    more = run_chunk(job_id)
    if more:
        if bounded.active():
            bounded.defer()
        else:
            dispatch(job_id)
    return job_id


@shared_task
def resume_card_jobs(limit=25):
    from django.db.models import Q
    from django.utils import timezone
    from .cutouts import resume_stuck
    from .job_runner import run_chunk
    from .models import CardJob
    resume_stuck(limit=bounded.rows(25))
    rows = CardJob.objects.filter(state__in=("queued", "running")).filter(
        Q(lease_until__isnull=True) | Q(lease_until__lte=timezone.now())).order_by("pk")
    for job_id in bounded.items(list(rows.values_list("pk", flat=True)[:bounded.rows(limit, heavy=True)])):
        if bounded.active():
            if run_chunk(job_id):
                bounded.defer()
        else:
            dispatch(job_id)


@shared_task
def purge_expired_card_job_results(limit=200):
    """Bulk files are kept 7 days (Q-I1), then the object and its link go."""
    from django.utils import timezone
    from .models import CardJob
    from .photo_batch import purge_expired_batches
    from .photo_batch_apply import expire_stalled
    from .storage import delete_quietly
    expire_stalled(limit=bounded.rows(20))
    purge_expired_batches(limit=bounded.rows(50))
    rows = CardJob.objects.filter(result_expires_at__lte=timezone.now()).exclude(result_key="").order_by("pk")
    for job in bounded.items(list(rows[:bounded.rows(limit)])):
        delete_quietly(job.result_key)
        CardJob.objects.filter(pk=job.pk).update(result_key="", result_size=0)


def dispatch_cutout(cutout_id):
    try:
        process_photo_cutout.delay(cutout_id)
    except Exception:
        logger.warning("photo_cutout_dispatch_failed", extra={"cutout_id": cutout_id})


# Decision 332(a): one attempt is at most a 5 s connect + 60 s read to the eraser (image_adapter.contract) plus
# decoding and a private upload. Retries stay bounded by the row's own MAX_ATTEMPTS (cutouts.py), not by Celery.
CUTOUT_SOFT_SECONDS, CUTOUT_HARD_SECONDS = 150, 180


@shared_task(bind=True, max_retries=None, soft_time_limit=CUTOUT_SOFT_SECONDS, time_limit=CUTOUT_HARD_SECONDS)
def process_photo_cutout(self, cutout_id):
    """One background-removal attempt (D314c); a transient provider failure re-queues itself with backoff."""
    from celery.exceptions import SoftTimeLimitExceeded
    from .cutouts import run, timed_out
    try:
        delay = run(cutout_id)
    except SoftTimeLimitExceeded:
        delay = timed_out(cutout_id)
    if delay:
        raise self.retry(countdown=delay)
    return cutout_id


@shared_task
def process_photo_batch(batch_id):
    """Apply a reviewed bulk photo batch, one bounded chunk at a time (D314c addendum)."""
    from .photo_batch_apply import apply_chunk
    if apply_chunk(batch_id):
        process_photo_batch.delay(batch_id)
    return batch_id


@shared_task
def fetch_card_font_task(family):
    from .font_fetch import fetch_family
    return fetch_family(family)


@shared_task
def refresh_wallet_passes(limit=100):
    """Live pass updates for renewals and expiries that happen outside a card service."""
    from .wallet.service import sweep_changed
    return sweep_changed(limit=bounded.rows(limit))


@shared_task
def remind_photo_requests(limit=200):
    """Q-I4: one reminder 7 days after a "photo needs update" request, then none."""
    from .photos import send_due_reminders
    return send_due_reminders(limit=bounded.rows(limit))
