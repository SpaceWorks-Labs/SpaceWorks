"""Celery autodiscovery entry for the machines app."""

from .tasks_jobs import sweep_job_flow_task  # noqa: F401
