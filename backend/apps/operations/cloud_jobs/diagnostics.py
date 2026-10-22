"""Real scheduler/worker evidence consumed by the installer diagnostics capsule."""
import re

from celery import shared_task
from celery.signals import task_failure, task_success
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

KEY = "spaceworks:scheduler:diagnostics:v1"


def scheduler_heartbeat(mode):
    if mode not in {"beat", "loop", "external"}:
        raise ValueError("Unknown scheduler mode")
    cache.set(KEY + ":heartbeat", {"mode": mode, "at": timezone.now().isoformat()}, timeout=600)


def scheduler_completed(*, failed=False, task_key=None):
    cache.set(KEY + ":failed", bool(failed), timeout=600)
    if not failed:
        cache.set(KEY + ":success", timezone.now().isoformat(), timeout=600)
    if task_key is not None:
        from apps.operations.models_scheduling import PeriodicTaskRun
        values = {"last_error": "TaskFailure" if failed else ""}
        PeriodicTaskRun.objects.update_or_create(name=task_key, defaults=values,
            create_defaults={**values, "last_run_at": timezone.now()})


def scheduler_snapshot():
    from .catalog import periodic_catalog
    from apps.operations.models_scheduling import PeriodicTaskRun
    heartbeat = cache.get(KEY + ":heartbeat") or {}
    failed = PeriodicTaskRun.objects.filter(name__in=[task.key for task in periodic_catalog()]).exclude(last_error="").exists()
    return {"schema_version": 1, "mode": heartbeat.get("mode", "external"),
            "heartbeat_at": heartbeat.get("at"), "last_success_at": cache.get(KEY + ":success"),
            "failed": failed or cache.get(KEY + ":failed", False)}


@shared_task(name="apps.operations.cloud_jobs.diagnostics.installer_roundtrip", ignore_result=True)
def installer_roundtrip(nonce):
    if not isinstance(nonce, str) or re.fullmatch("[0-9a-f]{32}", nonce) is None:
        raise ValueError("Invalid diagnostic nonce")
    cache.set("spaceworks:installer:roundtrip:" + nonce, nonce, timeout=60)


def _periodic(sender):
    from .catalog import periodic_catalog
    return next((task for task in periodic_catalog() if task.path == getattr(sender, "name", "")), None)


@task_success.connect(weak=False)
def periodic_success(sender=None, result=None, **kwargs):
    task = _periodic(sender)
    if task:
        # A failed count returned by a domain sweep is a failed sweep too.
        failed = isinstance(result, dict) and bool(result.get("failed"))
        scheduler_completed(failed=failed, task_key=task.key)


@task_failure.connect(weak=False)
def periodic_failure(sender=None, **kwargs):
    task = _periodic(sender)
    if task:
        scheduler_completed(failed=True, task_key=task.key)
