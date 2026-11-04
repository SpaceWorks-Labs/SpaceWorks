"""Retention for IP-blocking telemetry (``login_security_contract.RETENTION``; #157).

- ``IPAutoBlock`` rows, raw network included, are deleted 7 days after the block ends.
- django-axes rows (attempts, failure and access logs: usernames and addresses) are deleted
  after 30 days; a lockout lasts an hour (``AXES_COOLOFF_TIME``), so nothing live goes.

Daily, platform-global, and bounded by the cloud-jobs chunk on the free profile.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.operations.cloud_jobs import bounded

logger = logging.getLogger(__name__)
AXES_RETENTION = timedelta(days=30)


def purge_login_security_telemetry():
    from axes.models import AccessAttempt, AccessFailureLog, AccessLog

    from apps.accounts.login_security_contract import RETENTION
    from apps.accounts.models import IPAutoBlock

    now = timezone.now()
    _field, after, _what = RETENTION["accounts.IPAutoBlock"]
    targets = (
        (IPAutoBlock, IPAutoBlock.objects.filter(blocked_until__lt=now - after)),
        (AccessAttempt, AccessAttempt.objects.filter(attempt_time__lt=now - AXES_RETENTION)),
        (AccessFailureLog, AccessFailureLog.objects.filter(attempt_time__lt=now - AXES_RETENTION)),
        (AccessLog, AccessLog.objects.filter(attempt_time__lt=now - AXES_RETENTION)),
    )
    deleted = {}
    for model, rows in targets:
        label = model._meta.label
        try:
            deleted[label], _ = bounded.delete(rows, label)
        except Exception:  # one table's failure never stops the others
            logger.exception("login_security_purge_failed", extra={"model": label})
            deleted[label] = 0
    return deleted


@shared_task(name="apps.accounts.tasks_login_security.purge_login_security_task")
def purge_login_security_task():
    return purge_login_security_telemetry()
