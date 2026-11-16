"""Every programme permission recognizes managers and refuses ungranted actors."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from apps.events import event_authority
from apps.events.event_permissions import PROGRAMME_PERMISSIONS


@pytest.mark.parametrize("permission", PROGRAMME_PERMISSIONS)
def test_manager_and_ungranted_actor(permission, monkeypatch):
    actor = SimpleNamespace(is_authenticated=True, is_active=True, access_status="active")
    event = SimpleNamespace(makerspace_id=7, series_id=None)
    monkeypatch.setattr(event_authority, "can_manage_grants", lambda *_: True)
    assert event_authority.can(actor, event, permission)
    rows = Mock()
    rows.filter.return_value = rows
    rows.exists.return_value = False
    monkeypatch.setattr(event_authority, "can_manage_grants", lambda *_: False)
    monkeypatch.setattr(event_authority, "active_grants", lambda *a, **kw: rows)
    # Authority is entitlement-aware: an ungranted actor has no live entitlement either.
    monkeypatch.setattr("apps.events.contributions.authority.grant_ids", lambda **kw: [])
    assert not event_authority.can(actor, event, permission)


def test_unknown_permission_remains_denied(monkeypatch):
    monkeypatch.setattr(event_authority, "can_manage_grants", lambda *_: False)
    assert not event_authority.can(SimpleNamespace(), SimpleNamespace(), "unregistered_permission")


def test_programme_permission_callers_are_registered():
    import ast
    from pathlib import Path
    from apps.events.event_permissions import PERMISSIONS

    used = set()
    for path in Path(event_authority.__file__).parent.rglob("*.py"):
        if "migrations" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            if ast.unparse(node.func) in {"event_authority.can", "event_authority.require"} and len(node.args) >= 3:
                value = node.args[2]
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    used.add(value.value)
            for kw in node.keywords:
                if kw.arg == "permission" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    used.add(kw.value.value)
    assert used <= set(PERMISSIONS) | {"view"}
