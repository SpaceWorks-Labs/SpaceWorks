"""Privileged restore may read the install owner's env without weakening host trust."""

import json
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

from apps.backup import host_topology_record as topology


@pytest.mark.parametrize("env_owner,allowed", [(1000, True), (1001, False)])
def test_root_restore_admits_only_root_or_the_declared_install_owner(tmp_path, monkeypatch, env_owner, allowed):
    env, record = tmp_path / ".env", tmp_path / "topology.json"
    env.write_text("SPACEWORKS_SCHEDULER_MODE=image\n")
    record.write_text(json.dumps({"topology": "bundled"}))
    original_stat = Path.stat

    def ownership(path, **kwargs):
        if path == env:
            return SimpleNamespace(st_uid=env_owner, st_mode=stat.S_IFREG | 0o600)
        if path == record:
            return SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o640)
        return original_stat(path, **kwargs)

    monkeypatch.setattr(Path, "stat", ownership)
    monkeypatch.setattr(topology.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(topology, "read_pointer", lambda *args, **kwargs: None)
    monkeypatch.setattr(topology, "configuration_facts", lambda **kwargs: {"topology": "bundled"})
    arguments = dict(
        topology="bundled", static_env=env, pointer_file=tmp_path / "pointer.env",
        topology_record=record, compose_files=[], static_owner_uid=1000,
    )
    if allowed:
        assert topology.validate_compose_wrapper(**arguments) == {"topology": "bundled"}
        # Without the explicit install-owner context, the original caller rule applies.
        del arguments["static_owner_uid"]
    with pytest.raises(topology.TopologyRecordError, match="misowned"):
        topology.validate_compose_wrapper(**arguments)
