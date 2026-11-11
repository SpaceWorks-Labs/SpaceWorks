from unittest.mock import Mock

import pytest

from apps.backup.managed.audit_guard import guarded_anchor_sink


def test_lost_session_prevents_remote_anchor_effect(monkeypatch):
    guard = Mock(unsafe=True)  # the guard API is assert_valid()
    guard.assert_valid.side_effect = RuntimeError("session lost")
    monkeypatch.setattr("apps.backup.managed.audit_guard.current_session", lambda: guard)
    sink = Mock()
    with pytest.raises(RuntimeError):
        guarded_anchor_sink(sink).publish({"opaque": "envelope"})
    sink.publish.assert_not_called()


def test_session_lost_during_anchor_call_refuses_its_result(monkeypatch):
    guard = Mock(unsafe=True)  # the guard API is assert_valid()
    guard.assert_valid.side_effect = [None, RuntimeError("session lost during I/O")]
    monkeypatch.setattr("apps.backup.managed.audit_guard.current_session", lambda: guard)
    sink = Mock()
    with pytest.raises(RuntimeError):
        guarded_anchor_sink(sink).fetch(("deployment", "scope", "fingerprint", 1))
    sink.fetch.assert_called_once()
