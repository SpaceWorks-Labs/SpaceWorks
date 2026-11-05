"""Cache and background computation for the platform overview (#183A).

A read returns the cached overview when there is one. Otherwise it queues ONE Celery
computation per (period, toggle) -- an atomic `cache.add` lock stops a burst of reads
queueing the same heavy job -- and answers "computing" so the page polls. With no broker
(CELERY_TASK_ALWAYS_EAGER) the task runs inline and the first read is already ready.
A cache or broker outage degrades to computing inline; it never fails the page.
"""

import logging
from datetime import datetime

from django.core.cache import cache

from apps.operations.platform_overview_window import OverviewWindow

logger = logging.getLogger(__name__)

READY_TTL_SECONDS = 600
LOCK_TTL_SECONDS = 300
FAILED_TTL_SECONDS = 60
COMPUTING = {"status": "computing"}
FAILED = {"status": "failed"}


def cache_key(window, include_excluded):
    return f"platform-overview:v1:{window.cache_part()}:{int(bool(include_excluded))}"


def window_args(window):
    return [window.preset, window.start.isoformat() if window.start else None, window.end.isoformat()]


def window_from_args(preset, start, end):
    return OverviewWindow(preset, datetime.fromisoformat(start) if start else None, datetime.fromisoformat(end))


def compute_and_store(window, include_excluded):
    from apps.operations.platform_overview import build_platform_overview

    key = cache_key(window, include_excluded)
    try:
        data = build_platform_overview(window, include_excluded=include_excluded)
    except Exception:
        logger.exception("platform_overview.compute_failed")
        _safe(cache.set, key, FAILED, FAILED_TTL_SECONDS)
        raise
    finally:
        _safe(cache.delete, f"{key}:lock")
    _safe(cache.set, key, data, READY_TTL_SECONDS)
    return data


def read_or_schedule(window, include_excluded, *, refresh=False):
    """The cached overview, or COMPUTING after queueing one background computation."""
    key = cache_key(window, include_excluded)
    try:
        if refresh:
            cache.delete(key)
        hit = cache.get(key)
        if hit is not None:
            return hit
        if not cache.add(f"{key}:lock", 1, LOCK_TTL_SECONDS):
            return COMPUTING
    except Exception:  # noqa: BLE001 - no cache: compute for this read only
        logger.warning("platform_overview.cache_unavailable", exc_info=True)
        return _inline(window, include_excluded)
    from apps.operations.tasks_platform_overview import compute_platform_overview_task

    try:
        compute_platform_overview_task.delay(*window_args(window), include_excluded)
    except Exception:  # noqa: BLE001 - broker down: compute inline rather than strand the lock
        logger.warning("platform_overview.enqueue_failed", exc_info=True)
        return _inline(window, include_excluded)
    try:
        return cache.get(key) or COMPUTING
    except Exception:  # noqa: BLE001
        return COMPUTING


def _inline(window, include_excluded):
    try:
        return compute_and_store(window, include_excluded)
    except Exception:  # noqa: BLE001 - logged in compute_and_store
        return FAILED


def _safe(operation, *args):
    try:
        operation(*args)
    except Exception:  # noqa: BLE001
        logger.warning("platform_overview.cache_unavailable", exc_info=True)
