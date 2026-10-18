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
    from apps.events.services_write_boundary import write_boundary
    target = Event.objects.get(pk=event_id)
    with write_boundary(target, actor=actor, account_ids=account_ids, tenant_ids=tenant_ids):
        event = Event.objects.get(pk=event_id)
        event.makerspace = require_module_locked(event.makerspace_id, "events")
        if revalidate is not None:
            revalidate(event)
        if actor is not None:
            from apps.accounts.models import User
            actor = User.objects.get(pk=actor.pk)
            event_authority.require(actor, event, permission)
        yield event, actor



def require_version(event, expected_version):
    if event.version != expected_version:
        raise ProgrammeConflict()


def advance(event):
    event.version += 1
    event.save(update_fields=("version", "updated_at"))
    return event.version
