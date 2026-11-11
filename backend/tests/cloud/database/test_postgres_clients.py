from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.backup import postgres_client as client
from config.cloud_database import database_spec


def test_wrong_major_versioned_binary_is_not_trusted(monkeypatch, tmp_path):
    directory = tmp_path / "16"
    directory.mkdir()
    (directory / "pg_restore").write_text("not actually v16")
    monkeypatch.setattr(client, "_VERSIONED_CLIENT_DIRS", (str(tmp_path / "{major}"),))
    monkeypatch.setattr(client, "_binary_major", lambda path: 17)
    monkeypatch.setattr(client.shutil, "which", lambda name: None)
    with pytest.raises(client.PostgresClientUnavailable):
        client.client_binary("pg_restore", 16)


@pytest.mark.parametrize("major", [15, 18])
def test_unsupported_server_major_is_not_certified(major):
    with pytest.raises(client.PostgresClientUnavailable):
        client.client_binary("pg_dump", major)


def test_client_runner_passes_tls_without_password_and_cleans_passfile(monkeypatch):
    spec = database_spec("postgresql://app:unique-secret@db.example/db?sslmode=verify-full&sslrootcert=%2Fca.pem", mode="direct", managed=True, environ={})
    monkeypatch.setattr(client, "client_binary", lambda tool, major: "/client/" + tool)
    seen = []
    def run(argv, **kwargs):
        assert "unique-secret" not in repr(argv)
        assert "PGPASSWORD" not in kwargs["env"]
        assert kwargs["env"]["PGSSLMODE"] == "verify-full"
        passfile = Path(kwargs["env"]["PGPASSFILE"])
        assert "unique-secret" in passfile.read_text()
        seen.append(passfile)
        return SimpleNamespace(returncode=0, stdout=b"")
    monkeypatch.setattr(client.subprocess, "run", run)
    client.run_client("pg_dump", ["--format=custom"], spec=spec, major=16)
    assert not seen[0].exists()


def test_createdb_uses_maintenance_db_flag(monkeypatch):
    spec = database_spec("postgresql://app:secret@db.example/db?sslmode=require", mode="direct", managed=True, environ={})
    monkeypatch.setattr(client, "client_binary", lambda tool, major: "/client/" + tool)
    def run(argv, **kwargs):
        assert "--maintenance-db" in argv and "--dbname" not in argv
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(client.subprocess, "run", run)
    client.run_client("createdb", ["scratch"], spec=spec, major=17)


def _fake_client_dirs(monkeypatch, tmp_path, tool="pg_restore"):
    for major in (16, 17):
        directory = tmp_path / str(major)
        directory.mkdir()
        (directory / tool).write_text("fake client")
    monkeypatch.setattr(client, "_VERSIONED_CLIENT_DIRS", (str(tmp_path / "{major}"),))
    monkeypatch.setattr(client, "_binary_major", lambda path: int(Path(path).parent.name))
    monkeypatch.setattr(client.shutil, "which", lambda name: None)


@pytest.mark.parametrize("tool", ["pg_dump", "pg_restore", "psql"])
@pytest.mark.parametrize("major", [16, 17])
def test_client_binary_picks_the_client_that_matches_the_server_major(monkeypatch, tmp_path, tool, major):
    _fake_client_dirs(monkeypatch, tmp_path, tool)
    assert client.client_binary(tool, major) == str(tmp_path / str(major) / tool)


def test_a_seventeen_server_is_read_from_server_version_num_and_gets_the_seventeen_client(monkeypatch, tmp_path):
    _fake_client_dirs(monkeypatch, tmp_path)

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, sql):
            assert sql == "SHOW server_version_num"

        def fetchone(self):
            return ("170004",)

    monkeypatch.setattr(client, "connections", {"default": SimpleNamespace(cursor=lambda: Cursor())})
    assert client.server_major() == 17
    assert client.client_binary("pg_restore") == str(tmp_path / "17" / "pg_restore")


def test_a_seventeen_server_never_falls_back_to_the_sixteen_client(monkeypatch, tmp_path):
    directory = tmp_path / "16"
    directory.mkdir()
    (directory / "pg_restore").write_text("fake client")
    monkeypatch.setattr(client, "_VERSIONED_CLIENT_DIRS", (str(tmp_path / "{major}"),))
    monkeypatch.setattr(client, "_binary_major", lambda path: 16)
    monkeypatch.setattr(client.shutil, "which", lambda name: str(directory / name))
    with pytest.raises(client.PostgresClientUnavailable):
        client.client_binary("pg_restore", 17)
