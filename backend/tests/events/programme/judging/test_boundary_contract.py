"""Lock-order/receipt contract tests without pretending mocks prove PostgreSQL races."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from apps.events.judging import boundary
from apps.events.judging.errors import ProgrammeError


def test_same_command_replays_but_different_path_or_body_conflicts(monkeypatch):
    monkeypatch.setattr(boundary, "connection", SimpleNamespace(in_atomic_block=True))
    monkeypatch.setattr(boundary, "_locks", Mock(get=Mock(return_value=SimpleNamespace(event_id=42))))
    receipts = []
    model = Mock()
    model.objects.filter.return_value.first.side_effect = lambda: receipts[0] if receipts else None
    model.objects.create.side_effect = lambda **values: receipts.append(SimpleNamespace(**values))
    monkeypatch.setattr(boundary.apps, "get_model", lambda *args: model)
    event, actor = SimpleNamespace(pk=42), SimpleNamespace(pk=17)
    data = {"operation_id": str(uuid4()), "expected_version": 4}
    run = Mock(return_value={"id": 81, "version": 5})
    first = boundary.command(event, actor, data, path="rounds/1/open", run=run)
    assert boundary.command(event, actor, data, path="rounds/1/open", run=run) == first
    assert run.call_count == 1
    for path, values in (("rounds/2/open", data), ("rounds/1/open", {**data, "expected_version": 5})):
        with pytest.raises(ProgrammeError) as error:
            boundary.command(event, actor, values, path=path, run=run)
        assert error.value.detail["code"] == "idempotency_conflict"


def test_fences_are_acquired_before_the_event_and_authority_rows(monkeypatch):
    # The shared write boundary owns source gate, preparation, atomic and fences; the
    # judging boundary must enter it before locking the event and authority rows.
    observed = []
    actor = SimpleNamespace(pk=17)
    event = SimpleNamespace(pk=42, makerspace_id=9)
    ports = Mock()
    @contextmanager
    def write_boundary(target, *, actor, account_ids):
        assert (target, actor.pk, account_ids) == (event, 17, (5,))
        observed.append("boundary")
        yield
    ports.lock_authority.side_effect = lambda **kwargs: observed.append("authority") or actor
    model = Mock()
    model.objects.select_related.return_value.get.side_effect = lambda **kwargs: observed.append("event") or event
    monkeypatch.setattr(boundary, "Event", model)
    monkeypatch.setattr(boundary, "runtime", lambda: ports)
    monkeypatch.setattr("apps.events.services_write_boundary.write_boundary", write_boundary)
    monkeypatch.setattr("apps.events.programme_locks.current_locks", lambda event_id: object())
    monkeypatch.setattr(boundary.event_authority, "get_event", lambda *args: event)
    monkeypatch.setattr(boundary.event_authority, "require", lambda *args: None)
    with boundary.mutation(42, actor, account_ids=(5,)):
        observed.append("domain")
    assert observed == ["boundary", "event", "authority", "domain"]


def test_missing_runtime_adapter_fails_closed(monkeypatch):
    from apps.events.judging import ports
    monkeypatch.setattr(ports, "_installed", None)
    with pytest.raises(ProgrammeError) as error:
        ports.runtime()
    assert error.value.status_code == 503
