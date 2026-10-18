"""Source boundary and PII fences precede every event row lock."""

from contextlib import ExitStack, contextmanager

from django.db import transaction

from apps.events import event_authority
from apps.events.models_event import Event
from apps.events.models_series import EventSeries
from apps.events.programme_locks import fences, lock_authority
from apps.makerspaces.guards import require_module_locked
from apps.tenant_migration.gate_runtime import boundary_tenant_write

from .errors import ProgrammeConflict


@contextmanager
def event_command(event_id, *, actor=None, permission=None, tenant_ids=(), account_ids=(), revalidate=None):
    original = Event.objects.values("makerspace_id", "series_id").get(pk=event_id)
    host_id = original["makerspace_id"]
    tenants = sorted({host_id, *tenant_ids})
    with ExitStack() as stack:
        for tenant_id in tenants:
            stack.enter_context(boundary_tenant_write(tenant_id))
        stack.enter_context(transaction.atomic())
        accounts = sorted({*account_ids, *((actor.pk,) if actor else ())})
        stack.enter_context(fences(tenant_ids=tenants, account_ids=accounts))
        if original["series_id"]:
            EventSeries.objects.select_for_update().get(pk=original["series_id"])
        event = Event.objects.select_for_update().get(pk=event_id)
        if event.makerspace_id != host_id or event.series_id != original["series_id"]:
            raise ProgrammeConflict("Event scope changed; retry the command.")
        event.makerspace = require_module_locked(event.makerspace_id, "events")
        if revalidate is not None:
            revalidate(event)
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
