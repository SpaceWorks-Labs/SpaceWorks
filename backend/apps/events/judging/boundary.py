"""Common source/fence/event/authority boundary and canonical command replay."""

from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
import json
import logging
from uuid import UUID

from django.apps import apps
from django.db import connection, transaction
from django.http import Http404

from apps.audit.services import record
from apps.events import event_authority
from apps.events.contracts.providers import LockedContext
from apps.events.models import Event
from apps.makerspaces.guards import require_module_locked
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from .errors import ProgrammeError, require_version
from .ports import runtime

logger = logging.getLogger(__name__)
_locks = ContextVar("events_judging_locks", default=None)


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                             allow_nan=False, default=str).encode()).hexdigest()


@contextmanager
def mutation(event_id, actor, *, permission="manage_hackathon", account_ids=(), gallery=False, owner=False):
    # Visibility precedes a maintenance refusal so foreign event IDs disclose nothing.
    if owner:
        active_member(actor)
        event = Event.objects.filter(pk=event_id).first()
        if event is None:
            raise Http404
    else:
        event = event_authority.get_event(actor, event_id, permission)
    runtime().require_programme(event, gallery=gallery)
    host = event.makerspace_id
    account_ids = tuple(sorted({actor.pk, *account_ids}))
    with boundary_tenant_write(host):
        with transaction.atomic():
            # G provides global→tenant→account fences BEFORE the event row lock.
            with runtime().fences(tenant_ids=(host,), account_ids=tuple(sorted(set(account_ids)))):
                event = Event.objects.select_for_update().get(pk=event_id)
                if event.makerspace_id != host:
                    raise ProgrammeError("scope_changed", "Retry this action.")
                event.makerspace = require_module_locked(host, "events")
                fresh_actor = runtime().lock_authority(actor_id=actor.pk, event=event)
                if fresh_actor is None or fresh_actor.pk != actor.pk:
                    raise Http404
                if owner:
                    active_member(fresh_actor)
                else:
                    event_authority.require(fresh_actor, event, permission)
                runtime().require_programme(event, gallery=gallery)
                locks = LockedContext(event_id=event.pk, tenant_ids=(host,), account_ids=tuple(sorted(set(account_ids))))
                token = _locks.set(locks)
                try:
                    yield event, locks
                finally:
                    _locks.reset(token)


def assert_locked(locks):
    if not isinstance(locks, LockedContext) or not connection.in_atomic_block:
        raise RuntimeError("An event transaction and asserted lock context are required.")
    if _locks.get() is not locks:
        runtime().assert_lock_context(locks)


def active_member(actor):
    from apps.accounts.account_kind_guards import require_member_account
    require_member_account(actor)
    if not event_authority._active(actor):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied()


def command(event, actor, data, *, path, run):
    """Run inside mutation. Event lock serializes the shared receipt uniqueness key."""
    locks = _locks.get()
    if not connection.in_atomic_block or locks is None or locks.event_id != event.pk:
        raise RuntimeError("Command receipts require this workflow's locked event boundary.")
    operation = data.get("operation_id")
    try:
        operation = UUID(str(operation))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ProgrammeError("invalid_operation_id", "Use a command UUID.", status=400) from exc
    hashed = digest({"path": path, "body": data})
    model = apps.get_model("events", "EventCommandReceipt")
    prior = model.objects.filter(event_id=event.pk, actor_id=actor.pk, operation_uuid=operation).first()
    if prior:
        if prior.request_sha256 != hashed:
            raise ProgrammeError("idempotency_conflict", "This operation was used for different input.")
        return prior.response_reference
    response = run()
    model.objects.create(event_id=event.pk, actor_id=actor.pk, operation_uuid=operation,
                         request_sha256=hashed, response_reference=response)
    return response


def audit(event, actor, action, target, **safe):
    record(actor, f"event.programme.{action}", makerspace=event.makerspace, target=target, meta=safe)


def changed(event, actor, action, row, **safe):
    row.version += 1
    row.save()
    audit(event, actor, action, row, version=row.version, **safe)
    return envelope(row)


def envelope(row, **values):
    return {"id": row.pk, "event_id": row.event_id, "version": row.version,
            "allowed_actions": [], **({"state": row.state} if hasattr(row, "state") else {}), **values}


def owned(model, event_id, pk, *, expected=None):
    row = model.objects.select_for_update().filter(event_id=event_id, pk=pk).first()
    if row is None:
        raise Http404
    if expected is not None:
        require_version(row, expected)
    return row


def notice(event, kind, source_id, revision):
    from .models_results import JudgingNotice
    row, _ = JudgingNotice.objects.get_or_create(event=event, kind=kind, source_id=source_id, revision=revision)

    def enqueue():
        try:
            runtime().notify_intent(row.pk)
        except Exception:
            logger.warning("event_judging_notice_enqueue_failed", extra={"notice_id": row.pk})
    transaction.on_commit(enqueue)
