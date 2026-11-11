"""Durable certificate and judging recovery, plus retained print byte cleanup."""
import logging

from celery import shared_task
from apps.separability.registry import runtime_active

from apps.events.tasks_sweeps import batch


def _retry_venue_fees():
    """Payments audit 0.12.0 B-9: ride the per-minute events pass to re-raise a failed venue fee."""
    try:
        from .venue_fee_retry import retry_unraised_venue_fees
        retry_unraised_venue_fees(limit=batch(50))
    except Exception:
        logging.getLogger(__name__).exception("event_venue_fee_retry_pass_failed")


@shared_task
def sweep_judging_notices_task():
    if not runtime_active("events"):
        return 0
    from .judging.lifecycle import sweep_notices
    _retry_venue_fees()
    return sweep_notices(limit=batch(100))


@shared_task
def sweep_print_cleanup_task():
    from .certificates.print_cleanup import cleanup_expired
    from .certificates.print_custody import sweep
    return {"retained_jobs": cleanup_expired(limit=batch(100, heavy=True)),
            "purged_jobs": sweep(limit=batch(100, heavy=True))}
