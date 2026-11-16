"""One short event command transaction, stable receipts, and ordered fences."""
from django.utils.translation import gettext
import hashlib
import json
from dataclasses import dataclass

from django.apps import apps
from django.db import transaction
from django.shortcuts import get_object_or_404
from apps.accounts.staff_identity import is_person
from apps.audit.services import record
from apps.accounts.models import User
from apps.events import event_authority
from apps.events.contracts.providers import LockedContext
from apps.events.models import Event
from apps.makerspaces.guards import require_feature, require_module_locked
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from .errors import ProgrammeError
from .ports import ports


@dataclass(frozen=True)
class CommandResult:
    row: object
    status: int
    replayed: bool


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        default=str, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def active_member(actor):
    if not event_authority._active(actor) or not is_person(actor):
        raise ProgrammeError("member_required", gettext("An active member account is required."), status=403)


def run(*, actor, event_id, operation_id, payload, action, feature, permission,
        mutate, authorize=None, account_ids=(), authority_ids=(), status=200):
    """authorize runs again on replay; mutate must contain no external I/O.

    G owns EventCommandReceipt and the combined fence adapter. This package never
    creates a competing receipt table or acquires account-key rows under event locks.
    """
    adapter = ports()
    event = get_object_or_404(Event.objects.select_related("makerspace"), pk=event_id)
    if not event_authority._active(actor):
        raise ProgrammeError("account_inactive", gettext("An active account is required."), status=403)
    # Avoid exposing gate/key readiness to a caller without local authority.
    if permission is not False:
        event_authority.require(actor, event, permission)
    if authorize:
        authorize(event)
    if feature:
        require_feature(event.makerspace, feature)
        adapter.require_event_feature(event_id=event.pk, feature=feature)
    adapter.prepare_private_write(makerspace_id=event.makerspace_id)
    request_hash = digest({"action": action, "payload": payload})
    accounts = tuple(sorted({actor.pk, *account_ids, *authority_ids}))
    from apps.events.services_write_boundary import write_boundary
    from apps.events.programme_locks import current_locks
    with write_boundary(event, actor=actor, account_ids=accounts):
        with transaction.atomic():
            event = Event.objects.get(pk=event_id)
            event.makerspace = require_module_locked(event.makerspace_id, "events")
            locks = current_locks(event.pk)
            accounts = locks.account_ids
            # The shipped grant helper locks User under the event, which conflicts
            # with the programme/account-key lock order. G supplies the opt-in
            # membership/grant-only authority lock under the declared fences.
            # All declared subjects may become a live issuer during scope
            # discovery. Lock every account's authority before domain rows so
            # membership in account_ids is also proof of this authority fence.
            for authority_id in accounts:
                adapter.lock_authority_locked(actor_id=authority_id, event_id=event.pk, locks=locks)
            actor = User.objects.filter(pk=actor.pk).first()
            if not event_authority._active(actor):
                raise ProgrammeError("account_inactive", gettext("An active account is required."), status=403)
            if permission is not False:
                event_authority.require(actor, event, permission)
            if authorize:
                authorize(event)
            if feature:
                require_feature(event.makerspace, feature)
                adapter.require_event_feature(event_id=event.pk, feature=feature)
            receipt_model = apps.get_model("events", "EventCommandReceipt")
            receipt = receipt_model.objects.filter(event=event, actor=actor,
                operation_uuid=operation_id).first()
            if receipt:
                if receipt.request_sha256 != request_hash:
                    raise ProgrammeError("idempotency_conflict", gettext("This operation has different content."))
                ref = receipt.response_reference
                if not ref["model"].startswith("events."):
                    raise ProgrammeError("invalid_receipt", gettext("This operation cannot be replayed."), status=503)
                row = get_object_or_404(apps.get_model(ref["model"]), pk=ref["id"], event=event)
                return CommandResult(row=row, status=ref["status"], replayed=True)
            row = mutate(event, locks)
            from .models_roles import EventRoleAssignment
            if isinstance(row, EventRoleAssignment):
                from .role_notices import emit_role_locked
                emit_role_locked(row=row, action=action)
            receipt_model.objects.create(event=event, actor=actor, operation_uuid=operation_id,
                request_sha256=request_hash, response_reference={"model": row._meta.label_lower,
                    "id": row.pk, "status": status})
            record(actor, f"event.programme.{action}", makerspace=event.makerspace, target=row,
                   meta={"event_id": event.pk, "version": row.version})
            return CommandResult(row=row, status=status, replayed=False)


def owned(row_model, *, event_id, pk, actor):
    active_member(actor)
    return get_object_or_404(row_model.objects.filter(event_id=event_id, member=actor), pk=pk)


def new_row(model, event, **fields):
    return model.objects.create(event=event, makerspace_id=event.makerspace_id, **fields)


def changed(row, **fields):
    for key, value in fields.items():
        setattr(row, key, value)
    row.version += 1
    row.save(update_fields=[*fields, "version"])
    return row
