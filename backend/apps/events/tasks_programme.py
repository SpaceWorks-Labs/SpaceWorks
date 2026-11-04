"""Bounded, recoverable admission maintenance; domain services own transitions."""

import logging

from celery import shared_task

from apps.makerspaces.platform import feature_enabled
from apps.makerspaces.servability import servable_queryset
from apps.separability.registry import runtime_active
from apps.operations.cloud_jobs import bounded

logger = logging.getLogger(__name__)


@shared_task
def sweep_admission_deadlines_task():
    """Retries are safe: each service rechecks state/deadline under the event lock."""
    if not runtime_active("events"):
        return 0
    from .hackathons.admission_models import HackathonConfig
    from .hackathons.admission_maintenance import (
        expire_due, freeze_closed_applications, resume_waitlist,
    )

    configs = servable_queryset(HackathonConfig.objects.filter(
        enabled=True, event__makerspace__enabled_modules__contains=["events"],
    ), relation="event__makerspace").select_related("event__makerspace").order_by("event_id")
    processed = 0
    for config in bounded.page(configs, "event-admission-configs"):
        if not feature_enabled(config.event.makerspace, "events.hackathons"):
            continue
        try:
            # Each call establishes its own source/fence/domain boundary. No broker
            # or provider I/O runs while the domain transaction holds row locks.
            freeze_closed_applications(event_id=config.event_id, limit=100)
            expire_due(event_id=config.event_id, limit=100)
            resume_waitlist(event_id=config.event_id)
            processed += 1
        except Exception:  # One frozen/unavailable tenant must not stop the sweep.
            logger.exception("programme admission sweep failed", extra={"event_id": config.event_id})
    return processed
