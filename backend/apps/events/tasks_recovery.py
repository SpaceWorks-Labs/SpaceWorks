"""Durable certificate and judging recovery, plus retained print byte cleanup."""
from celery import shared_task
from apps.separability.registry import runtime_active


@shared_task
def sweep_judging_notices_task():
    if not runtime_active("events"):
        return 0
    from .judging.lifecycle import sweep_notices
    return sweep_notices(limit=100)


@shared_task
def sweep_print_cleanup_task():
    from .certificates.print_cleanup import cleanup_expired
    return cleanup_expired(limit=100)
