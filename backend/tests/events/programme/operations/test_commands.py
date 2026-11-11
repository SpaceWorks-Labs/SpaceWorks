"""Replay/CAS/permission ordering without substituting a real database concurrency test."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.events.programme import commands


@pytest.fixture
def command_boundary(monkeypatch):
    actor = SimpleNamespace(pk=2)
    event = SimpleNamespace(pk=42, makerspace_id=9, series_id=None, makerspace=object(), version=4)
    boundary = Mock()
    monkeypatch.setattr(commands.event_authority, "require", boundary.require)
    # Source gate, preparation, atomic and fences now live in the shared write boundary.
    @contextmanager
    def write_boundary(target, **kwargs):
        boundary.source(target, **kwargs)
        yield
    monkeypatch.setattr("apps.events.services_write_boundary.write_boundary", write_boundary)
    monkeypatch.setattr(commands, "require_module_locked", lambda space, module: space)
    monkeypatch.setattr(commands, "lock_authority", lambda user, target: user)
    events = Mock()
    events.values_list.return_value.get.return_value = None
    events.select_for_update.return_value.get.return_value = event
    monkeypatch.setattr(commands.Event, "objects", events)
    receipts = Mock()
    receipts.filter.return_value.first.return_value = None
    monkeypatch.setattr(commands, "receipt_model", lambda: SimpleNamespace(objects=receipts))
    return actor, event, boundary, receipts


def test_duplicate_operation_replays_before_stale_version_without_mutating(command_boundary):
    actor, event, boundary, receipts = command_boundary
    data, operation = {"is_public": True}, uuid4()
    digest = commands.fingerprint({"command": "publishing", "payload": data})
    receipts.filter.return_value.first.return_value = SimpleNamespace(
        request_sha256=digest, response_reference={"event_id": 42, "version": 5})
    execute = Mock()
    result = commands.execute_command(event=event, actor=actor, command="publishing", payload=data,
        expected_version=1, operation_id=operation, execute=execute)
    assert result == {"event_id": 42, "version": 5}
    execute.assert_not_called()
    assert boundary.require.call_count == 2
    receipts.filter.assert_called_once_with(event=event, actor=actor, operation_uuid=operation)


def test_uuid_content_conflict_is_not_a_replay(command_boundary):
    actor, event, _, receipts = command_boundary
    receipts.filter.return_value.first.return_value = SimpleNamespace(request_sha256="different")
    execute = Mock()
    with pytest.raises(commands.ProgrammeConflict) as error:
        commands.execute_command(event=event, actor=actor, command="publishing", payload={},
            expected_version=4, operation_id=uuid4(), execute=execute)
    assert error.value.detail["code"] == "idempotency_conflict"
    execute.assert_not_called()


def test_stale_version_never_invokes_callback_or_inserts_receipt(command_boundary):
    actor, event, _, receipts = command_boundary
    execute = Mock()
    with pytest.raises(commands.ProgrammeConflict) as error:
        commands.execute_command(event=event, actor=actor, command="publishing", payload={},
            expected_version=3, operation_id=uuid4(), execute=execute)
    assert error.value.detail["code"] == "stale_version"
    execute.assert_not_called()
    receipts.create.assert_not_called()


def test_lost_authority_blocks_even_previously_successful_operation(command_boundary):
    actor, event, boundary, receipts = command_boundary
    boundary.require.side_effect = PermissionDenied()
    with pytest.raises(PermissionDenied):
        commands.execute_command(event=event, actor=actor, command="publishing", payload={},
            expected_version=4, operation_id=uuid4(), execute=Mock())
    receipts.filter.assert_not_called()


def test_digest_separates_commands_and_ignores_object_key_order():
    assert commands.fingerprint({"x": 1, "y": 2}) == commands.fingerprint({"y": 2, "x": 1})
    assert commands.fingerprint({"command": "a", "payload": {}}) != commands.fingerprint({"command": "b", "payload": {}})
