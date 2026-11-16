"""Host beat keeps its existing shelve schedule and supplies a real heartbeat."""
from celery.beat import PersistentScheduler

from .diagnostics import scheduler_heartbeat


class ObservedPersistentScheduler(PersistentScheduler):
    def tick(self, **kwargs):
        scheduler_heartbeat("beat")
        # Celery's default tick may sleep five minutes; bound heartbeat freshness
        # without changing any task's due calculation or persistent schedule.
        return min(60, super().tick(**kwargs))
