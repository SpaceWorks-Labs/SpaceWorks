"""Source boundary and PII fences precede every event row lock."""

from contextlib import ExitStack, contextmanager

from django.db import transaction

from apps.encryption.write_fence import assert_mapped_write_allowed
from apps.events import event_authority
from apps.events.models_event import Event
from apps.events.staff_grant_locks import lock_authority
from apps.makerspaces.guards import require_module_locked
from apps.tenant_migration.gate_runtime import boundary_tenant_write

from .errors import ProgrammeConflict


@contextmanager
def event_command(event_id, *, actor=None, permission=None, tenant_ids=()):
    host_id = Event.objects.values_list("makerspace_id", flat=True).get(pk=event_id)
    tenants = sorted({host_id, *tenant_ids})
    with ExitStack() as stack:
        for tenant_id in tenants:
            stack.enter_context(boundary_tenant_write(tenant_id))
        stack.enter_context(transaction.atomic())
        for tenant_id in tenants:
            assert_mapped_write_allowed(tenant_id)
        event = Event.objects.select_for_update().get(pk=event_id)
        event.makerspace = require_module_locked(event.makerspace_id, "events")
        if actor is not None:
            actor = lock_authority(actor, event)
            event_authority.require(actor, event, permission)
        yield event, actor


def require_version(event, expected_version):
    if event.version != expected_version:
        raise ProgrammeConflict()


def advance(event):
    event.version += 1
    event.save(update_fields=("version", "updated_at"))
    return event.version
