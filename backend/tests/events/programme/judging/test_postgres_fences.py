"""Real blocking regression: D must wait at the PII fence BEFORE locking Event.

Run with G's isolated PostgreSQL runner after programme migrations/registries.
Each worker has its own connection; this is one pytest process/database.
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event as Signal
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection, transaction

from apps.encryption.models import PiiMakerspaceWriteFence
from apps.encryption.write_fence import (
    GLOBAL_LOCK_NAMESPACE, TENANT_LOCK_NAMESPACE, PiiWriteFenced, assert_mapped_write_allowed, close_makerspace,
)
from apps.events.judging import ports
from apps.events.judging.definitions_workflow import save_definition
from apps.events.judging.models_definitions import HackathonTrack
from apps.events.models import Event
from tests.events.programme.judging.test_definition_workflow import DefinitionsPorts
from tests.events.staff_grant_helpers import grant_fixture


@pytest.mark.django_db(transaction=True)
def test_closed_tenant_fence_wins_before_event_row_is_acquired(monkeypatch):
    space, manager, _, event, _ = grant_fixture()
    entered = Signal()
    # The judging boundary now enters the shared write boundary, whose real fences
    # block on the tenant advisory lock held below before any Event row lock.
    from apps.events import services_write_boundary as boundary
    real_fences = boundary.fences
    @contextmanager
    def fences(**kwargs):
        entered.set()
        with real_fences(**kwargs):
            yield
    monkeypatch.setattr(boundary, "fences", fences)
    monkeypatch.setattr(ports, "_installed", DefinitionsPorts())
    data = {"operation_id": str(uuid4()), "expected_version": 0, "name": "Blocked track"}
    def worker():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '8s'")
            save_definition(event.pk, actor=manager, kind="tracks", data=data)
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=1) as executor:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock_shared(%s, 0)", [GLOBAL_LOCK_NAMESPACE])
            cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", [TENANT_LOCK_NAMESPACE, space.pk])
            future = executor.submit(worker)
            assert entered.wait(timeout=5), "Writer did not reach the declared fence."
            # A writer that took Event first makes this NOWAIT fail: the regression
            # is observable without timing sleeps or a second pytest process.
            Event.objects.select_for_update(nowait=True).get(pk=event.pk)
            close_makerspace(space.pk, PiiMakerspaceWriteFence.OperationKind.DECRYPT_ROLLBACK, manager.pk)
        with pytest.raises(PiiWriteFenced):
            future.result(timeout=10)
    assert not HackathonTrack.objects.filter(event=event).exists()
