import logging
from celery import shared_task

from apps.operations.cloud_jobs import bounded

logger = logging.getLogger(__name__)


def dispatch_batch(batch_id):
    try:
        process_batch.delay(batch_id)
    except Exception:
        # The committed batch remains discoverable by resume_batches after broker loss.
        logger.warning("event_certificate_batch_dispatch_failed", extra={"batch_id": batch_id})


@shared_task
def process_batch(batch_id):
    from .batches import run_chunk
    from .lifecycle import render_certificate
    from apps.events.tasks_sweeps import batch as rows_for
    batch = run_chunk(batch_id)
    for item in bounded.items(batch.items.filter(certificate__status__in=("pending", "failed")).select_related(
            "certificate").order_by("certificate__render_attempts", "pk")[:rows_for(100, heavy=True)]):
        try:
            render_certificate(item.certificate)
        except Exception:
            logger.warning("event_certificate_batch_render_deferred", extra={"certificate_id": item.certificate_id})
    if batch.state != "completed":
        if bounded.active():
            bounded.defer()  # A free tick resumes it through resume_batches, never by recursion.
        else:
            dispatch_batch(batch.pk)
    return batch.pk


@shared_task
def resume_batches(limit=100):
    from .models import CertificateIssueBatch
    from apps.events.tasks_sweeps import batch as rows_for, take_ids
    ids = take_ids("certificate-batches", CertificateIssueBatch.objects.filter(state__in=("queued", "running")),
                   limit=rows_for(limit, heavy=True))
    rows = CertificateIssueBatch.objects.filter(pk__in=ids).order_by("pk")
    for batch in bounded.items(rows):
        # Inside a free tick the batch renders in this chunk; a broker hand-off would
        # run eagerly and unbounded.
        if bounded.active():
            process_batch(batch.pk)
        else:
            dispatch_batch(batch.pk)


@shared_task(bind=True, max_retries=3)
def render_one(self, certificate_id):
    from apps.events.models_certificates import EventAttendanceCertificate
    from .lifecycle import render_certificate
    row = EventAttendanceCertificate.objects.filter(pk=certificate_id).first()
    if not row or row.status in ("active", "revoked"):
        return
    try:
        render_certificate(row)
    except Exception as exc:
        # Retry metadata contains IDs only; do not place exception text or PII in broker payloads.
        raise self.retry(countdown=300) from None


def _render_in_chunk(row):
    """A free tick renders synchronously; a failure stays pending for the next tick."""
    from .lifecycle import render_certificate
    if row.status in ("active", "revoked"):
        return
    try:
        render_certificate(row)
    except Exception:
        logger.warning("event_certificate_render_deferred", extra={"certificate_id": row.pk})


@shared_task
def resume_certificates(limit=100):
    from datetime import timedelta
    from django.db.models import Q
    from django.utils import timezone
    from apps.events.models_certificates import EventAttendanceCertificate
    pending = Q(status__in=("pending", "failed")) | Q(status="rendering", render_started_at__lte=timezone.now()-timedelta(minutes=5)) | Q(status="rendering", render_started_at__isnull=True)
    from apps.events.tasks_sweeps import batch as rows_for, take_ids
    ids = take_ids("certificate-renders", EventAttendanceCertificate.objects.filter(pending),
                   limit=rows_for(limit, heavy=True))
    rows = EventAttendanceCertificate.objects.filter(pk__in=ids).order_by("pk")
    for row in bounded.items(rows):
        if bounded.active():
            _render_in_chunk(row)
            continue
        try:
            render_one.delay(row.pk)
        except Exception:
            logger.warning("event_certificate_resume_dispatch_failed", extra={"certificate_id": row.pk})
