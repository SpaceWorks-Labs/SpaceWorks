import uuid

import pytest

from apps.backup.host_marker import MarkerError
from scripts import spaceworks_entrypoint as entrypoint


def test_managed_path_never_reads_a_host_marker_or_socket(monkeypatch):
    monkeypatch.setenv("SPACEWORKS_DEPLOYMENT_MODE", "managed")
    monkeypatch.setenv("SPACEWORKS_DEPLOYMENT_PROFILE", "full")
    seen = []
    monkeypatch.setattr("apps.backup.managed.entrypoint.admit_managed_command", lambda role, argv: seen.append(role.value))
    monkeypatch.setattr(entrypoint, "read_marker", lambda *args: pytest.fail("host marker consulted"))
    monkeypatch.setattr(entrypoint.os, "execvp", lambda *args: seen.append(args))
    command = ["python", "-m", "scripts.run_cloud_role", "web"]
    assert entrypoint.main(["entrypoint", "--role", "backend", *command]) == 0
    assert seen == ["backend", ("python", command)]


def test_default_host_still_refuses_missing_marker(monkeypatch):
    monkeypatch.delenv("SPACEWORKS_DEPLOYMENT_MODE", raising=False)
    monkeypatch.delenv("SPACEWORKS_DEPLOYMENT_PROFILE", raising=False)
    monkeypatch.setattr(entrypoint, "read_marker", lambda *args: (_ for _ in ()).throw(MarkerError("missing marker")))
    monkeypatch.setattr(entrypoint.os, "execvp", lambda *args: pytest.fail("launched without marker"))
    assert entrypoint.main(["entrypoint", "--role", "backend", "gunicorn", "config.wsgi"]) == 78


def test_unknown_mode_fails_before_reading_marker(monkeypatch):
    monkeypatch.setenv("SPACEWORKS_DEPLOYMENT_MODE", "automatic")
    monkeypatch.setattr(entrypoint, "read_marker", lambda *args: pytest.fail("marker read"))
    assert entrypoint.main(["entrypoint", "--role", "backend", "python", "manage.py", "check"]) == 78


def test_database_failures_never_print_credentials(monkeypatch, capsys):
    monkeypatch.setenv("SPACEWORKS_DEPLOYMENT_MODE", "managed")
    monkeypatch.setenv("SPACEWORKS_DEPLOYMENT_PROFILE", "full")
    def failed(*args):
        raise RuntimeError("postgresql://owner:super-secret@example.invalid/db")
    monkeypatch.setattr("apps.backup.managed.entrypoint.admit_managed_command", failed)
    assert entrypoint.main(["entrypoint", "--role", "backend", "python", "-m", "scripts.run_cloud_role", "web"]) == 78
    assert "super-secret" not in capsys.readouterr().err


def _run_image_entrypoint(env):
    import os
    import subprocess
    import sys
    from pathlib import Path

    script = Path(entrypoint.__file__).resolve()
    clean = {k: v for k, v in os.environ.items() if not k.startswith("SPACEWORKS_DEPLOYMENT_")}
    return subprocess.run([sys.executable, str(script), "--role", "backend", "python", "-c", "pass"],
                          env={**clean, **env}, capture_output=True, text=True, timeout=60)


def test_one_image_hands_managed_mode_to_the_cloud_entrypoint_first():
    # #75a: the published image keeps the common ENTRYPOINT; managed mode must reach
    # cloud_entrypoint (secret materialization + admission) before anything else.
    result = _run_image_entrypoint({"SPACEWORKS_DEPLOYMENT_MODE": "managed", "SPACEWORKS_DEPLOYMENT_PROFILE": "bogus"})
    assert result.returncode == 78
    assert "SpaceWorks startup refused: deployment configuration" in result.stderr


def test_one_image_host_mode_never_enters_the_cloud_entrypoint():
    result = _run_image_entrypoint({"SPACEWORKS_HOST_MARKER_PATH": "/nonexistent/marker.json"})
    assert result.returncode == 78
    assert "SpaceWorks entrypoint refused startup" in result.stderr
    assert "startup refused: deployment configuration" not in result.stderr
