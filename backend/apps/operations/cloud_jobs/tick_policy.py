"""Free-only bounds. Full deployments never consult these settings."""
from contextlib import contextmanager
from datetime import timedelta
import time

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection, transaction
from django.utils import timezone

from .contracts import BudgetExpired
from .journal import model


def free_profile():
    return getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free"


def integer_setting(name, default, low, high):
    value = getattr(settings, name, default)
    if type(value) is not int or not low <= value <= high:
        raise ImproperlyConfigured(f"{name} must be an integer in {low}..{high}")
    return value


def tick_budget():
    return integer_setting("FREE_TICK_BUDGET_SECONDS", 20, 3, 20)


class TickRateExceeded(Exception):
    def __init__(self, seconds):
        self.seconds = seconds


@transaction.atomic
def consume_rate(*, authenticated):
    """Fixed global buckets bound rejected-auth traffic without trusting IP headers."""
    limit = (integer_setting("FREE_TICK_RATE_LIMIT_PER_MINUTE", 6, 1, 60) if authenticated
             else integer_setting("FREE_TICK_INGRESS_LIMIT_PER_MINUTE", 120, 6, 600))
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL statement_timeout = '1000ms'")
        cursor.execute("SET LOCAL lock_timeout = '500ms'")
    now = timezone.now()
    window = now.replace(second=0, microsecond=0)
    row, _ = model("CloudTickRateWindow").objects.select_for_update().get_or_create(
        key="authenticated" if authenticated else "ingress", defaults={"window": window, "hits": 0},
    )
    if row.window != window:
        row.window, row.hits = window, 0
    if row.hits >= limit:
        raise TickRateExceeded(max(1, int((window + timedelta(minutes=1) - now).total_seconds()) + 1))
    row.hits += 1
    row.save(update_fields=["window", "hits"])


@contextmanager
def database_deadline(deadline):
    """Bound ORM statements and row contention too, with response headroom.

    Domain adapters must independently bound their auxiliary DB/storage/mail clients.
    Restore caller session timeouts even if a callback fails.
    """
    with connection.cursor() as cursor:
        cursor.execute("SHOW statement_timeout")
        statement_timeout = cursor.fetchone()[0]
        cursor.execute("SHOW lock_timeout")
        lock_timeout = cursor.fetchone()[0]

    def bounded(execute, sql, params, many, context):
        remaining = int((deadline - time.monotonic()) * 1000)
        if remaining <= 0:
            raise BudgetExpired()
        execute("SELECT set_config('statement_timeout', %s, false), set_config('lock_timeout', %s, false)",
                [str(remaining), str(min(500, remaining))], False, context)
        return execute(sql, params, many, context)

    try:
        with connection.execute_wrapper(bounded):
            yield
    finally:
        # A broken transaction is rolled back by its owner before exiting here.
        if not connection.needs_rollback:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('statement_timeout', %s, false), set_config('lock_timeout', %s, false)",
                               [statement_timeout, lock_timeout])
