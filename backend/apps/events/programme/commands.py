"""CAS and replay boundary shared by programme commands and communications."""

import hashlib
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.apps import apps
from django.db import transaction
from rest_framework.exceptions import APIException

from apps.events import event_authority
from apps.events.models import Event, EventSeries
from apps.events.programme_locks import fences, lock_authority
from apps.makerspaces.guards import require_module_locked
from apps.tenant_migration.gate_runtime import boundary_tenant_write

class ProgrammeConflict(APIException):
    status_code = 409
    default_code = "stale_version"

    def __init__(self, code="stale_version", detail="This item changed. Reload before saving.", *, current_version=None):
        body = {"code": code, "detail": detail, "fields": {}}
        if current_version is not None:
            body["current_version"] = current_version
        super().__init__(body)
        if current_version is not None:
            self.detail["current_version"] = current_version


class ProgrammeUnavailable(APIException):
    status_code = 503

    def __init__(self, code="programme_unavailable", detail="This event operation is unavailable."):
        super().__init__({"code": code, "detail": detail})


def fingerprint(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         cls=DjangoJSONEncoder, allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def event_version(event):
    value = getattr(event, "version", None)
    if value is None:
        raise ProgrammeUnavailable("event_version_unavailable", "Event version integration is required.")
    return value


def receipt_model():
    try:
        return apps.get_model("events", "EventCommandReceipt")
    except LookupError as exc:
        raise ProgrammeUnavailable("command_receipt_unavailable", "Event command receipt integration is required.") from exc


def execute_command(*, event, actor, command, payload, expected_version, operation_id,
                    execute, permission=None, version_getter=None, authorize=None,
                    account_ids=(), tenant_ids=()):
    """Callback performs domain mutation/audit and returns a non-PII receipt.

    Receipt lookup precedes CAS but follows fresh authority checks. A retry cannot
    replay after the sender loses access, or reuse a UUID for different content.
    Domain callbacks must not perform storage/provider/network I/O under locks.
    """
    event_authority.require(actor, event, permission)
    from apps.events.services_write_boundary import write_boundary
    with write_boundary(event, actor=actor, account_ids=account_ids, tenant_ids=tenant_ids):
        return _execute_fenced(event=event, actor=actor, command=command, payload=payload,
            expected_version=expected_version, operation_id=operation_id, execute=execute,
            permission=permission, version_getter=version_getter, authorize=authorize)


def _execute_fenced(*, event, actor, command, payload, expected_version, operation_id,
                    execute, permission, version_getter, authorize):
    series_id = Event.objects.values_list("series_id", flat=True).get(pk=event.pk)
    if series_id:
        EventSeries.objects.select_for_update().get(pk=series_id)
    locked = Event.objects.select_for_update().get(pk=event.pk)
    if locked.makerspace_id != event.makerspace_id or locked.series_id != series_id:
        raise ProgrammeConflict("scope_changed", "Event ownership changed. Retry the command.")
    locked.makerspace = require_module_locked(locked.makerspace, "events")
    locked_actor = lock_authority(actor, locked)
    event_authority.require(locked_actor, locked, permission)
    if authorize is not None:
        authorize(locked, locked_actor)
    digest = fingerprint({"command": command, "payload": payload})
    receipts = receipt_model().objects
    receipt = receipts.filter(event=locked, actor=locked_actor, operation_uuid=operation_id).first()
    if receipt is not None:
        if receipt.request_sha256 != digest:
            raise ProgrammeConflict("idempotency_conflict", "This operation ID was already used.")
        return dict(receipt.response_reference)
    version = version_getter(locked) if version_getter else event_version(locked)
    if expected_version != version:
        raise ProgrammeConflict(current_version=version)
    response = execute(locked, locked_actor)
    receipts.create(
        event=locked, operation_uuid=operation_id, actor=locked_actor,
        request_sha256=digest, response_reference=response,
    )
    return response
