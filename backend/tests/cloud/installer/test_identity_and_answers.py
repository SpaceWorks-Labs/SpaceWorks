"""Driver-free boundary tests; runtime Docker/Postgres evidence is a separate gate."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[4]


def load_script(name):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location("installer_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("rows", [[("makerspace", 42, "a" * 36)], [], [("a", 1, "b"), ("c", 2, "d")]])
def test_identity_closes_cursor_and_connection_even_on_missing_singleton(monkeypatch, capsys, rows):
    events = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            events.append("cursor_closed")

        def execute(self, statement):
            assert "current_database()" in statement

        def fetchall(self):
            return rows

    class Connection:
        def cursor(self):
            return Cursor()

        def close(self):
            events.append("connection_closed")

    def connect(url, *, connect_timeout):
        assert connect_timeout == 10
        events.append("connect")
        return Connection()

    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=connect))
    monkeypatch.setenv("DATABASE_URL", "postgres://operator:secret@db:5432/makerspace")
    monkeypatch.setattr(sys, "argv", ["restore-database-identity.py"])
    module = load_script("restore-database-identity.py")
    assert not events  # module import must never touch the DB
    if len(rows) == 1:
        module.main()
        assert capsys.readouterr().out == "makerspace|42|" + "a" * 36 + "\n"
    else:
        with pytest.raises(ValueError):
            module.main()
    assert events == ["connect", "cursor_closed", "connection_closed"]


def test_identity_external_endpoint_refuses_without_connecting(monkeypatch):
    def fail(*_, **__):
        pytest.fail("must refuse before connection")
    monkeypatch.setitem(sys.modules, "psycopg2", SimpleNamespace(connect=fail))
    monkeypatch.setenv("DATABASE_URL", "postgres://user:private@outside.example/db")
    with pytest.raises(ValueError):
        load_script("restore-database-identity.py").main()


def test_connection_error_is_sanitized_when_executed(tmp_path):
    (tmp_path / "psycopg2.py").write_text('def connect(*a, **k): raise RuntimeError("DO-NOT-PRINT-PASSWORD")\n')
    result = subprocess.run([sys.executable, str(ROOT / "scripts/restore-database-identity.py")],
                            env={**os.environ, "PYTHONPATH": str(tmp_path), "DATABASE_URL": "postgres://db:5432/demo"},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert "Cannot prove" in result.stderr
    assert "DO-NOT-PRINT" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def answers(tmp_path, document):
    path = tmp_path / "answers.json"
    path.write_text(document)
    path.chmod(0o600)
    return subprocess.run([sys.executable, str(ROOT / "scripts/installer/answers.py"), str(path)],
                          capture_output=True, timeout=10)


def test_answers_are_nul_framed_data_not_shell_code(tmp_path):
    raw = {"schema_version": 1, "confirmed": True,
           "answers": {"ORG_NAME": "Maker $(touch should-not-exist)", "ADMINEMAIL": "owner@example.org"}}
    result = answers(tmp_path, json.dumps(raw))
    assert result.returncode == 0
    assert result.stdout.split(b"\0")[:2] == [b"ORG_NAME", b"Maker $(touch should-not-exist)"]
    assert not (tmp_path / "should-not-exist").exists()


@pytest.mark.parametrize("document", [
    '{}', '{"schema_version":1,"schema_version":1,"confirmed":true,"answers":{}}',
    '{"schema_version":true,"confirmed":true,"answers":{}}',
    '{"schema_version":1,"confirmed":false,"answers":{"ORG_NAME":"a","ADMINEMAIL":"b"}}',
    '{"schema_version":1,"confirmed":true,"answers":{"ORG_NAME":"a","ADMINEMAIL":"b","BAD":"a\\nb"}}',
    '{"schema_version":1,"confirmed":true,"answers":{"ORG_NAME":"a"}}',
])
def test_invalid_answers_emit_no_partial_input_or_values(tmp_path, document):
    result = answers(tmp_path, document)
    assert result.returncode != 0 and not result.stdout
    assert b"Invalid private answers" in result.stderr


def test_generated_credential_never_replaces_an_existing_one_or_prints_secret(tmp_path):
    target = tmp_path / "bootstrap.json"
    command = [sys.executable, str(ROOT / "scripts/installer/credential.py"), str(target)]
    env = {**os.environ, "SETUP_BOOTSTRAP_PASSWORD": "private-test-credential", "SETUP_BOOTSTRAP_USER": "owner"}
    first = subprocess.run(command, env=env, capture_output=True, timeout=10)
    assert first.returncode == 0 and not first.stdout and not first.stderr
    original = target.read_bytes()
    second = subprocess.run(command, env={**env, "SETUP_BOOTSTRAP_PASSWORD": "different"}, capture_output=True, timeout=10)
    assert second.returncode == 1 and target.read_bytes() == original
    assert b"private-test-credential" not in second.stdout + second.stderr
