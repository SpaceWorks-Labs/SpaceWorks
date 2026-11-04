"""Attendance confirmation emails (lane L21a): one bounded, idempotent fan-out per staff send."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_attendance_round_task(self, round_id):
    from .attendance_confirmation import deliver_round
    try:
        return deliver_round(round_id)
    except Exception as exc:  # the dedup key makes a retry re-send nothing already queued
        logger.warning("attendance_round_failed", extra={"round_id": round_id})
        raise self.retry(exc=exc)
