"""Durable deferred notification fan-out: a request enqueues ONE job carrying ids, a Celery worker does the rest.

Recipient resolution, per-recipient rendering, preference/quiet-hour/limit checks, row creation and delivery all
live inside the decorated notification entry point. ``@deferred_fanout`` turns a call made from a web request, an
admin action or a management command into (1) one lightweight ``legacy.lifecycle`` NotificationEnvelope shell
written in the caller's transaction (ids only) and (2) an after-commit ``deliver_envelope`` task. The existing
outbox sweeper recovers a shell whose enqueue was lost to a broker outage, so the intent is as durable as the
domain write itself.

Rules the wrapper keeps:
* Eager Celery (tests, brokerless installs), the free profile (no worker) and code already running inside a Celery
  task run the function inline, so return values and test determinism are unchanged.
* Idempotency: a retried job re-runs the same function with the same ids; inner ``emit()`` calls dedupe on their
  own ``dedup_key``. A caller-supplied ``dedupe`` makes a double call create one shell.
* Ordering: shells for the same subject run in pk order (an "issued" shell blocks the "returned" shell of the
  same request), for at most ``ORDER_WAIT`` after which the later job proceeds.
* Failure is recorded on the shell (attempts, error class), retried with exponential backoff, then marked dead
  with an error log. It is never raised into the request.
"""
import importlib
import logging
from contextvars import ContextVar
from datetime import datetime, timedelta
from functools import wraps
from uuid import uuid4

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

LEGACY_KIND = "legacy.lifecycle"
MAX_ATTEMPTS = 6
STALE_START = timedelta(minutes=15)
ORDER_WAIT = timedelta(minutes=30)
REGISTRY = {}
_in_job = ContextVar("fanout_in_job", default=False)
_job_id = ContextVar("fanout_job_id", default=None)
_calls = ContextVar("fanout_job_calls", default=0)


from .fanout_codec import SubjectGone, Unserializable, _decode, _encode  # noqa: E402


def _in_worker():
    from celery import current_task
    return bool(current_task and getattr(current_task.request, "id", None))


def defer_enabled():
    """False wherever no separate worker will pick the job up (eager, free profile) or inside a worker."""
    from .mail_providers.budget_config import free_profile
    return not (_in_job.get() or _in_worker() or free_profile()
                or getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)
                or not getattr(settings, "NOTIFICATION_FANOUT_VIA_CELERY", True))


_HOPS = ("event", "order", "request", "registration", "team", "project", "assignment", "obligation", "programme",
         "series", "booking", "membership", "invitation", "campaign", "payout", "claim", "award")


def _space_of(value, depth=2):
    from apps.makerspaces.models import Makerspace
    if isinstance(value, Makerspace):
        return value
    if not isinstance(value, models.Model):
        return None
    space = getattr(value, "makerspace", None)
    if isinstance(space, Makerspace):
        return space
    space_id = getattr(value, "makerspace_id", None)
    if isinstance(space_id, int):
        return Makerspace.objects.filter(pk=space_id).first()
    if depth:
        for hop in _HOPS:
            related = getattr(value, hop, None)
            found = _space_of(related, depth - 1) if isinstance(related, models.Model) else None
            if found is not None:
                return found
    return None


def _makerspace_of(args, kwargs):
    for value in (*args, *kwargs.values()):
        found = _space_of(value)
        if found is not None:
            return found
    return None


def register(function):
    """Make ``function`` runnable by a worker (done at import time, so the worker's import registers it)."""
    REGISTRY[f"{function.__module__}.{function.__qualname__}"] = function


def maybe_defer(function, args, kwargs, *, feature="", event="", dedupe=None, subject_index=0, space=None) -> bool:
    """Queue ``function(*args, **kwargs)`` as a durable job; False means the caller runs it inline (as before).

    Inline wherever no worker will pick it up (see ``defer_enabled``) or the arguments are not plain ids/models.
    """
    if not defer_enabled() or "<locals>" in function.__qualname__:
        return False
    name = f"{function.__module__}.{function.__qualname__}"
    try:
        owner_space = (space(*args, **kwargs) if space else None) or _makerspace_of(args, kwargs)
        if owner_space is None:
            raise Unserializable("no makerspace")
        key = dedupe(*args, **kwargs) if dedupe else uuid4().hex
        enqueue_job(owner_space, name, args, kwargs, feature=feature or function.__module__.split(".")[1],
                    event=event or function.__name__[:64], key=key, subject_index=subject_index)
        return True
    except Exception:
        # Never lose the notification: an unserialisable call keeps the previous inline behaviour.
        logger.warning("fanout_inline_fallback", extra={"fn": name}, exc_info=True)
        return False


def deferred_fanout(*, feature="", event="", dedupe=None, subject_index=0, space=None):
    """Decorate a notification entry point whose return value request-path callers ignore.

    ``dedupe(*args, **kwargs)`` optionally returns a stable string (event/recipient/revision); ``subject_index``
    names the positional argument whose model row orders this job against others for the same subject; ``space``
    optionally maps the call's arguments to the owning makerspace when they carry only ids.
    """
    def decorate(function):
        register(function)

        @wraps(function)
        def wrapper(*args, **kwargs):
            if maybe_defer(function, args, kwargs, feature=feature, event=event,
                           dedupe=dedupe, subject_index=subject_index, space=space):
                return None
            return function(*args, **kwargs)
        return wrapper
    return decorate


def enqueue_job(space, name, args, kwargs, *, feature, event, key, subject_index=0):
    from django.contrib.contenttypes.models import ContentType
    from .models_contract import NotificationEnvelope
    subject = args[subject_index] if len(args) > subject_index else None
    subject = subject if isinstance(subject, models.Model) else None
    job = {"fn": name, "args": [_encode(item) for item in args],
           "kwargs": {k: _encode(v) for k, v in kwargs.items()},
           "state": "queued", "attempts": 0}
    with transaction.atomic():
        envelope, created = NotificationEnvelope.objects.get_or_create(
            dedup_key=f"fanout:{name}:{key}"[:200],
            defaults=dict(
                makerspace=space, feature=feature, stream=feature, event=event or name.rsplit(".", 1)[-1][:64],
                audience="staff", source_kind=LEGACY_KIND, context={"fanout": job},
                subject_type=ContentType.objects.get_for_model(subject) if subject is not None else None,
                subject_id=str(subject.pk) if subject is not None else "", revision="1"))
        if created:
            from .notification_outbox import enqueue
            transaction.on_commit(lambda: enqueue(envelope.pk), robust=True)
    return envelope


def _blocked_by_earlier(envelope):
    if not envelope.subject_type_id or not envelope.subject_id:
        return False
    if timezone.now() - envelope.created_at > ORDER_WAIT:
        return False
    from .models_contract import NotificationEnvelope
    return NotificationEnvelope.objects.filter(
        source_kind=LEGACY_KIND, processed_at=None, pk__lt=envelope.pk,
        subject_type_id=envelope.subject_type_id, subject_id=envelope.subject_id,
        context__has_key="fanout").exists()


def _save(envelope, **changes):
    envelope.context = {**envelope.context, "fanout": {**envelope.context["fanout"], **changes}}
    update = {"context": envelope.context}
    if changes.get("state") in {"done", "dead", "subject_gone"}:
        envelope.processed_at = timezone.now()
        update["processed_at"] = envelope.processed_at
    envelope.save(update_fields=list(update))


def run(envelope):
    """Execute one stored job. Called by the notification outbox worker/sweeper (recover)."""
    from .models_contract import NotificationEnvelope
    with transaction.atomic():
        locked = NotificationEnvelope.objects.select_for_update().get(pk=envelope.pk)
        job = locked.context.get("fanout") or {}
        if locked.processed_at is not None or not job:
            return False
        started = job.get("started_at")
        if job.get("state") == "started" and started and \
                timezone.now() - datetime.fromisoformat(started) < STALE_START:
            return False
        if _blocked_by_earlier(locked):
            return False
        _save(locked, state="started", attempts=job.get("attempts", 0) + 1,
              started_at=timezone.now().isoformat())
    job = locked.context["fanout"]
    module = job["fn"].rsplit(".", 1)[0]
    importlib.import_module(module)
    function = REGISTRY.get(job["fn"])
    if function is None:
        _save(locked, state="dead", error="unknown_job")
        logger.error("fanout_job_unknown", extra={"fn": job["fn"], "envelope_id": locked.pk})
        return False
    token, id_token, calls_token = _in_job.set(True), _job_id.set(locked.pk), _calls.set(0)
    try:
        args = [_decode(item) for item in job["args"]]
        kwargs = {key: _decode(item) for key, item in job["kwargs"].items()}
        with transaction.atomic():  # a failed attempt leaves no half-written rows to duplicate on retry
            function(*args, **kwargs)
    except SubjectGone:
        _save(locked, state="subject_gone")
        return False
    except Exception as exc:
        attempts = job["attempts"]
        if attempts >= MAX_ATTEMPTS:
            _save(locked, state="dead", error=type(exc).__name__)
            logger.error("fanout_job_dead", extra={"fn": job["fn"], "envelope_id": locked.pk,
                                                    "error_class": type(exc).__name__})
        else:
            wait = timedelta(seconds=min(30 * 2 ** (attempts - 1), 1800))
            NotificationEnvelope.objects.filter(pk=locked.pk).update(available_at=timezone.now() + wait)
            _save(locked, state="failed", error=type(exc).__name__)
            logger.warning("fanout_job_failed", extra={"fn": job["fn"], "envelope_id": locked.pk,
                                                       "attempts": attempts, "error_class": type(exc).__name__})
        return False
    finally:
        _in_job.reset(token)
        _job_id.reset(id_token)
        _calls.reset(calls_token)
    _save(locked, state="done")
    return True


def stable_event_key():
    """A uuid for the n-th legacy fan-out inside this job, identical on every re-run of the job.

    Outside a job (inline/eager) it is a fresh uuid4, exactly as before. Inside one, a retried job reaches the same
    legacy envelope and the same per-leg markers, so a leg that already went out is never sent twice.
    """
    job = _job_id.get()
    if job is None:
        return uuid4()
    from uuid import NAMESPACE_URL, uuid5
    _calls.set(_calls.get() + 1)
    return uuid5(NAMESPACE_URL, f"spaceworks:fanout:{job}:{_calls.get()}")
