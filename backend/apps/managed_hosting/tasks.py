"""The managed-hosting beat sweep (#187A): trial reminders and expiry, then non-payment
enforcement (which itself does nothing unless the superadmin enabled it). With the
switch off the task returns at once."""

import logging

from celery import shared_task

from .availability import plans_enabled

logger = logging.getLogger(__name__)


def sweep():
    if not plans_enabled():
        return {"enabled": False}
    from .billing import enforce_overdue
    from .trials import sweep as sweep_trials

    result = {"enabled": True, **sweep_trials(), "read_only_for_payment": enforce_overdue()}
    logger.info("managed_hosting_swept", extra=result)
    return result


@shared_task(name="apps.managed_hosting.tasks.sweep_managed_hosting_task")
def sweep_managed_hosting_task():
    return sweep()



@shared_task(name="apps.managed_hosting.tasks.sweep_limit_thresholds_task")
def sweep_limit_thresholds_task():
    """Decision 328a: 80 / 100 percent limit warnings for every space; a no-op for a space with no limits."""
    from .limit_thresholds import sweep_all

    return sweep_all()
