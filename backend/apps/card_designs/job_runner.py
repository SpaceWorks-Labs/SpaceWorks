"""Run one chunk of a card job: lease, check switches, work, record progress (#133).

Each call processes at most one chunk (50 cards) and returns whether work remains, so
a full server re-dispatches the next chunk and a free-profile tick resumes it. A
chunk that raises is retried up to 3 times before the job fails. Cancelling between
chunks stops the job; switching the governing feature off cancels it.
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit

from .holders import registered
from .jobs import RESULT_TTL, holder_kind
from .models import CardJob

logger = logging.getLogger(__name__)
LEASE = timedelta(minutes=5)
MAX_ATTEMPTS = 3


def _claim(job_id):
    with transaction.atomic():
        job = CardJob.objects.select_for_update(skip_locked=True).filter(pk=job_id).first()
        now = timezone.now()
        if job is None or job.finished or (job.lease_until and job.lease_until > now):
            return None
        job.lease_until = now + LEASE
        if job.state == CardJob.State.QUEUED:
            job.state, job.started_at = CardJob.State.RUNNING, now
        job.save(update_fields=["lease_until", "state", "started_at"])
        return job


def _finish(job, state, *, error="", result=None):
    job.state, job.finished_at, job.lease_until, job.error_code = state, timezone.now(), None, error
    fields = ["state", "finished_at", "lease_until", "error_code"]
    if result:
        job.result_key, job.result_size, job.result_content_type = result
        job.result_expires_at = timezone.now() + RESULT_TTL
        fields += ["result_key", "result_size", "result_content_type", "result_expires_at"]
    job.save(update_fields=fields)
    if state == CardJob.State.SUCCEEDED:
        audit.record(None, "card_job.succeeded", makerspace=job.makerspace, target=job,
                     meta={"job_id": job.pk, "kind": job.kind, "done": job.done, "failed": job.failed})
    elif state == CardJob.State.FAILED:
        audit.record(None, "card_job.failed", makerspace=job.makerspace, target=job,
                     meta={"job_id": job.pk, "kind": job.kind, "done": job.done, "failed": job.failed})
    else:
        audit.record(None, "card_job.cancelled", makerspace=job.makerspace, target=job,
                     meta={"job_id": job.pk, "kind": job.kind, "done": job.done, "failed": job.failed})
    from .notifications import job_finished
    transaction.on_commit(lambda: job_finished(job.pk), robust=True)


def _switched_on(job, kind):
    from .switches import scope_enabled
    return kind in registered() and scope_enabled(job)


def _cards(kind, ids):
    model = registered()[kind].model()
    rows = {row.pk: row for row in model.objects.filter(pk__in=ids)}
    return [rows[pk] for pk in ids if pk in rows]


def _do_chunk(job, kind, batch):
    from . import job_outputs
    if job.kind in ("bulk_sheet", "bulk_per_person", "zip"):
        cards = _cards(kind, batch)
        data, content_type, failed = job_outputs.render_chunk(job, kind, cards)
        if data:
            job.parts = [*job.parts, job_outputs.store_part(job, len(job.parts), data, content_type)]
        return len(cards) - len(failed), len(failed) + len(batch) - len(cards)
    if job.kind == "email":
        from .email import send_card_email
        sent = sum(1 for card in _cards(kind, batch) if send_card_email(kind, card, actor=job.requested_by,
                                                                       explicit=job.params.get("explicit", False)))
        return sent, len(batch) - sent
    if job.kind == "wallet_update":
        from .wallet.service import refresh
        for card in _cards(kind, batch):
            refresh(kind, card)
        return len(batch), 0
    if job.kind == "photo_cleanup":
        from .photo_cleanup import run_cleanup
        return (1, 0) if run_cleanup(job) else (0, 1)
    if job.kind == "wallet_issue":
        from .wallet.service import issue_from_job
        return (1, 0) if issue_from_job(job) else (0, 1)
    return 0, len(batch)


def run_chunk(job_id):
    """-> True while the job still has work left."""
    job = _claim(job_id)
    if job is None:
        return False
    kind = holder_kind(job)
    if not _switched_on(job, kind):
        _finish(job, CardJob.State.CANCELLED, error="switched_off")
        return False
    position = job.done + job.failed
    first = None
    if job.kind == "bulk_sheet":
        head = _cards(kind, job.targets[:1])
        if head:
            from .cards import document_for
            first = document_for(kind, head[0])
    from .job_outputs import CHUNK, chunk_size
    size = chunk_size(job, first) if first else CHUNK
    batch = job.targets[position:position + size]
    try:
        if batch:
            done, failed = _do_chunk(job, kind, batch)
            job.done, job.failed, job.attempts = job.done + done, job.failed + failed, 0
            job.save(update_fields=["done", "failed", "attempts", "parts"])
    except Exception:
        logger.warning("card_job_chunk_failed", extra={"job_id": job.pk, "kind": job.kind})
        job.attempts += 1
        job.lease_until = None
        job.save(update_fields=["attempts", "lease_until"])
        if job.attempts >= MAX_ATTEMPTS:
            _finish(job, CardJob.State.FAILED, error="chunk_failed")
            return False
        return True
    job.refresh_from_db(fields=["state"])
    if job.state == CardJob.State.CANCELLED:
        return False
    if job.done + job.failed < job.total:
        CardJob.objects.filter(pk=job.pk).update(lease_until=None)
        return True
    result = None
    direct = {CardJob.Kind.PHOTO_CLEANUP: "image/png", CardJob.Kind.WALLET_ISSUE: "application/vnd.apple.pkpass"}
    if job.kind in direct and job.parts:
        # A single built object (a cleaned photo, a pass) is the result as it is.
        result = (job.parts[0], 0, direct[job.kind])
        CardJob.objects.filter(pk=job.pk).update(parts=[])
    elif job.parts:
        from .job_outputs import assemble, discard_parts
        result = assemble(job)
        transaction.on_commit(lambda: discard_parts(job.pk), robust=True)
    if job.kind in ("bulk_sheet", "bulk_per_person", "zip", "photo_cleanup") and not result:
        _finish(job, CardJob.State.FAILED, error="nothing_rendered")
    else:
        _finish(job, CardJob.State.SUCCEEDED, result=result)
    return False
