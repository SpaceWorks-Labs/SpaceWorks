"""Celery autodiscovery entry: the key-job task lives in ``rekey_tasks`` (lane L8)."""

from .rekey_tasks import advance_key_jobs_task  # noqa: F401
