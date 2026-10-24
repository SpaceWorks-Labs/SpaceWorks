"""Narrow byte-retention boundary; never grants workflow or publication authority.

Only expiry/cleanup callers use this boundary. It deliberately doesn't install a
source-gate override: ordinary commands continue to refuse frozen sources. The
shared source lock still serializes migration state changes with cleanup, while
recovery quarantine and not-restored tenants always refuse retention mutations.
"""
from contextlib import contextmanager

from django.db import transaction

from apps.backup.models import DeploymentRecoveryState
from apps.backup.not_restored import assert_restored
from apps.events.models_event import Event
from apps.events.models_series import EventSeries
from apps.events.programme_locks import fences
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.gate_locks import shared_boundary


def require_retention_ready(makerspace_id):
    if not DeploymentRecoveryState.objects.filter(pk=1, mode=DeploymentRecoveryState.Mode.NORMAL).exists():
        raise RuntimeError("Retention is unavailable during deployment recovery.")
    assert_restored(makerspace_id)


@contextmanager
def _retention_event(event_id):
    """Internal cleanup primitive. No actor, permissions, callback or bypass token."""
    scope = Event.objects.values("makerspace_id", "series_id").get(pk=event_id)
    host_id = scope["makerspace_id"]
    with shared_boundary(host_id):
        require_retention_ready(host_id)
        with transaction.atomic(), fences(tenant_ids=(host_id,), account_ids=()):
            if scope["series_id"]:
                EventSeries.objects.select_for_update().get(pk=scope["series_id"])
            event = Event.objects.select_for_update().get(pk=event_id)
            if (event.makerspace_id, event.series_id) != (host_id, scope["series_id"]):
                raise RuntimeError("Retention scope changed; retry.")
            event.makerspace = Makerspace.objects.select_for_update().get(pk=host_id)
            require_retention_ready(host_id)
            yield event
