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
    from .job_runner import run_chunk
    from .models import CardJob
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
    from .storage import delete_quietly
    rows = CardJob.objects.filter(result_expires_at__lte=timezone.now()).exclude(result_key="").order_by("pk")
    for job in bounded.items(list(rows[:bounded.rows(limit)])):
        delete_quietly(job.result_key)
        CardJob.objects.filter(pk=job.pk).update(result_key="", result_size=0)


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
