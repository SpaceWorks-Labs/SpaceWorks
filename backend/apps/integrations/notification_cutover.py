"""Lock order: cutover -> tenant boundary -> sender -> configuration/User -> rows.

The dedicated lock transaction spans network I/O without transacting application work.
An exclusive checkpoint waits for every participating handler/worker to finish.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

from django.db import connections, transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import APIException

from .models_cutover import NotificationCutover, NotificationIngress

LOCK_KEY = 62839674110218
_held = ContextVar("notification_cutover_lock", default=False)


class CutoverClosed(APIException):
    status_code = 503
    default_code = "notification_cutover_closed"
    default_detail = "Notification reconciliation is in progress. Try again later."


@contextmanager
def boundary(*, using="default", exclusive=False):
    if _held.get():
        if exclusive:
            raise RuntimeError("Cannot upgrade a notification cutover lock")
        yield
        return
    import psycopg2
    connection = psycopg2.connect(**connections[using].get_connection_params())
    token = None
    try:
        lock = "pg_advisory_xact_lock" if exclusive else "pg_advisory_xact_lock_shared"
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT {lock}(%s)", [LOCK_KEY])
        token = _held.set(True)
        yield
    finally:
        if token is not None:
            _held.reset(token)
        # Closing also releases the lock after a broken application transaction.
        connection.close()


def state(using="default"):
    return NotificationCutover.objects.using(using).get_or_create(pk=1)[0]


def sending_allowed():
    current = state()
    return current.route == "canonical" and current.sending_enabled and current.activated_at is not None


def guarded(*, mutation=False, sending=False):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with boundary():
                if sending and not sending_allowed():
                    return None
                if mutation and state().route != "canonical":
                    raise CutoverClosed()
                return function(*args, **kwargs)
        return wrapped
    return decorate


def establish_barrier(*, drained=False, using="default"):
    """Operator checkpoint after old application instances and handlers are drained."""
    if not drained:
        raise ValueError("Confirm old instances and provider calls have been drained")
    with boundary(using=using, exclusive=True), transaction.atomic(using=using):
        current = state(using)
        if current.copied_at or current.snapshot.get("_copy_started"):
            raise ValueError("Conversion already started; use canonical replay recovery")
        from .notification_conversion_snapshot import snapshot
        current.route, current.sending_enabled = "receipt_only", False
        current.barrier_at = timezone.now()
        current.receipt_watermark = NotificationIngress.objects.using(using).aggregate(n=Max("pk"))["n"] or 0
        current.snapshot = snapshot(using)
        current.save(using=using)
        return current


def switch_to_canonical(*, using="default"):
    with boundary(using=using, exclusive=True), transaction.atomic(using=using):
        current = state(using)
        if not current.barrier_at or not current.copied_at:
            raise ValueError("Barrier and conversion checkpoints are required")
        current.route, current.sending_enabled = "canonical", False
        current.replay_watermark = NotificationIngress.objects.using(using).aggregate(n=Max("pk"))["n"] or 0
        current.save(using=using)
        return current


def activate(*, using="default"):
    with boundary(using=using, exclusive=True), transaction.atomic(using=using):
        current = state(using)
        if current.sending_enabled and current.activated_at:
            return current
        from .notification_conversion_snapshot import verify_reconciliation
        verify_reconciliation(using)
        current = state(using)
        if current.route != "canonical" or not current.reconciled_at:
            raise ValueError("Canonical replay and retirement verification are required")
        current.sending_enabled, current.activated_at = True, timezone.now()
        current.save(using=using)
