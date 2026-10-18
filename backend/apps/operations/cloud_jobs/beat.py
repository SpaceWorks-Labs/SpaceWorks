"""Managed full beat adapter using the DB journal for restart due timestamps.

I selects this scheduler only for the managed full profile. Host beat keeps its
persistent --schedule file and existing clock-slot semantics.
"""
import time

from celery.beat import Scheduler
from celery.schedules import maybe_schedule
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from .catalog import periodic_catalog
from .full_scheduler import leader


class DatabaseScheduler(Scheduler):
    max_interval = 60

    def setup_schedule(self):
        if (getattr(settings, "SPACEWORKS_DEPLOYMENT_MODE", "host") != "managed"
                or getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free"):
            raise ImproperlyConfigured("DatabaseScheduler requires the managed full profile")
        self.max_interval = 60
        # The journal, not a shelve file, is the managed schedule authority.
        self._leader_context = None
        self._leader = None

    def tick(self, **kwargs):
        from apps.operations.models_scheduling import PeriodicTaskRun
        from .diagnostics import scheduler_heartbeat
        if self._leader_context is None:
            context = leader()
            lock = context.__enter__()
            self._leader_context, self._leader = context, lock
        self._leader.check()
        scheduler_heartbeat("beat")
        now = timezone.now()
        for task in periodic_catalog():
            self._leader.check()
            with transaction.atomic():
                row, _ = PeriodicTaskRun.objects.select_for_update().get_or_create(
                    name=task.key, defaults={"last_run_at": now})
                declaration = settings.CELERY_BEAT_SCHEDULE.get(task.key, {})
                schedule = maybe_schedule(declaration.get("schedule", task.minutes * 60), app=self.app)
                if not schedule.is_due(row.last_run_at or now).is_due:
                    continue
                row.last_run_at, row.last_error = now, ""
                row.save(update_fields=["last_run_at", "last_error"])
            try:
                self._leader.check()
                task.resolve().apply_async()
            except Exception:
                PeriodicTaskRun.objects.filter(name=task.key).update(last_error="DispatchFailure")
                raise
        return self.max_interval

    def sync(self):
        pass  # Each due claim is already committed in PostgreSQL.

    def close(self):
        if self._leader_context is not None:
            self._leader_context.__exit__(None, None, None)
            self._leader_context, self._leader = None, None


def run_loop(command, *, lane, interval=60, stop=None):
    """No swallowed failures or threads. Entrypoint/host writer admission is M/I's."""
    if lane not in {"scheduler", "worker"} or not 1 <= interval <= 60:
        raise ValueError("A separate scheduler/worker lane and interval 1..60 are required")
    with leader(lane) as lock:
        while stop is None or not stop():
            if lock is not None:
                lock.check()
            command(lock)
            time.sleep(interval)
