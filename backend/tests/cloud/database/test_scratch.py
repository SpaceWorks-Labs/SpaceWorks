import json
import os
import uuid

import pytest

from config.cloud_database.scratch import ScratchUnavailable, qualify_scratch, scratch_specs


def write_file(path, databases):
    path.write_text(json.dumps({"version": 1, "databases": databases}))
    path.chmod(0o600)


def test_scratch_file_rejects_same_database_and_hides_secrets(tmp_path):
    file = tmp_path / "scratch.json"
    database = {"url": "postgresql://owner:scratch-secret@db.example/scratch?sslmode=require", "connection_mode": "direct"}
    write_file(file, [database, database])
    with pytest.raises(ScratchUnavailable) as error:
        scratch_specs(file, environ={})
    assert "scratch-secret" not in str(error.value)


def test_scratch_file_requires_exact_version_and_two_databases(tmp_path):
    file = tmp_path / "scratch.json"
    write_file(file, [])
    with pytest.raises(ScratchUnavailable):
        scratch_specs(file, environ={})


def test_scratch_requires_private_file_on_posix(tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX file-mode contract is verified in the Linux job image")
    file = tmp_path / "scratch.json"
    write_file(file, [])
    file.chmod(0o644)
    with pytest.raises(ScratchUnavailable):
        scratch_specs(file, environ={})


def test_scratch_requires_runtime_role_inventory_before_any_connection():
    with pytest.raises(ScratchUnavailable):
        qualify_scratch([], application_uuid=uuid.uuid4(), runtime_roles=[])
