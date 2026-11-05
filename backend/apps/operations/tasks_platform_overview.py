"""Background computation of the superadmin platform overview (#183A).

The result is counts and per-currency money only, keyed by period and toggle; no
person data enters the cache. Not retried: the next read after the short failure
marker expires queues a fresh run.
"""

from celery import shared_task


@shared_task(ignore_result=True)
def compute_platform_overview_task(preset, start, end, include_excluded):
    from apps.operations.platform_overview_cache import compute_and_store, window_from_args

    compute_and_store(window_from_args(preset, start, end), bool(include_excluded))
