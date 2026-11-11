"""The additional free profile cannot change host/full topology."""

import pytest

from apps.backup.managed.profile import (
    DeploymentConfigurationError, deployment_profile, effective_environment, validate_process,
)
from apps.backup.process_roles import ProcessRole
from scripts.run_cloud_role import role_argv


@pytest.mark.parametrize("values", [{}, {"SPACEWORKS_DEPLOYMENT_PROFILE": "full"}])
def test_missing_selectors_preserve_host_full(values):
    values = {**values, "FREE_TICK_SECRET": "ignored", "FREE_EMAIL_DAILY_CAP": "1"}
    assert deployment_profile(values).mode == "host"
    assert deployment_profile(values).profile == "full"
    assert effective_environment(values) == values
    validate_process(deployment_profile(values), ProcessRole.WORKER, ["celery", "worker"])


@pytest.mark.parametrize("overrides", [
    {"SPACEWORKS_DEPLOYMENT_MODE": ""}, {"SPACEWORKS_DEPLOYMENT_MODE": "automatic"},
    {"SPACEWORKS_DEPLOYMENT_PROFILE": "cheap"}, {"SPACEWORKS_DEPLOYMENT_PROFILE": "free"},
])
def test_selectors_fail_closed(overrides):
    with pytest.raises(DeploymentConfigurationError):
        deployment_profile(overrides)


@pytest.mark.parametrize("overrides", [
    {"CELERY_BROKER_URL": "redis://redis"}, {"CACHE_URL": "redis://cache"},
    {"LIVE_REDIS_URL": "redis://live"}, {"CLOUD_SCHEDULER": "loop"},
    {"CLOUD_TASK_PROFILE": "redis"}, {"GUNICORN_WORKERS": "2"},
    {"GUNICORN_THREADS": "2"}, {"CELERY_TASK_ALWAYS_EAGER": "false"},
    {"GUNICORN_CMD_ARGS": "--preload"}, {"UPLOAD_SCAN_POLICY": "clamav"},
])
def test_free_rejects_contradictory_options(overrides):
    source = {"SPACEWORKS_DEPLOYMENT_MODE": "managed", "SPACEWORKS_DEPLOYMENT_PROFILE": "free", **overrides}
    with pytest.raises(DeploymentConfigurationError):
        deployment_profile(source)


def test_free_uses_single_sync_web_and_bounded_recycling():
    source = {"SPACEWORKS_DEPLOYMENT_MODE": "managed", "SPACEWORKS_DEPLOYMENT_PROFILE": "free", "PORT": "8123"}
    result = effective_environment(source)
    assert result["CLOUD_SCHEDULER"] == "tick"
    assert result["CELERY_BROKER_URL"] == ""
    command = role_argv("web", result)
    assert command[command.index("--workers") + 1] == "1"
    assert command[command.index("--worker-class") + 1] == "sync"
    assert "0.0.0.0:8123" in command
    assert "--preload" not in command
    assert "--max-requests" in command


@pytest.mark.parametrize("role", ["worker", "beat", "scheduler", "live"])
def test_free_refuses_resident_other_roles(role):
    with pytest.raises(DeploymentConfigurationError):
        role_argv(role, {"SPACEWORKS_DEPLOYMENT_MODE": "managed", "SPACEWORKS_DEPLOYMENT_PROFILE": "free"})


def test_reduced_image_cannot_be_accidentally_run_as_full(monkeypatch):
    monkeypatch.setattr("apps.backup.managed.image.image_profile", lambda: "free")
    with pytest.raises(DeploymentConfigurationError):
        deployment_profile({"SPACEWORKS_DEPLOYMENT_MODE": "managed"})


@pytest.mark.parametrize("port", ["0", "65536", "hello", "8000;echo secret"])
def test_port_is_validated_without_a_shell(port):
    with pytest.raises(DeploymentConfigurationError):
        role_argv("web", {"SPACEWORKS_DEPLOYMENT_MODE": "managed", "SPACEWORKS_DEPLOYMENT_PROFILE": "free", "PORT": port})


def test_full_brokerless_selectors_remain_a_resident_worker_and_loop():
    source = {"SPACEWORKS_DEPLOYMENT_MODE": "managed", "CLOUD_TASK_PROFILE": "brokerless", "CLOUD_SCHEDULER": "loop", "FREE_TICK_SECRET": "inert", "FREE_EMAIL_DAILY_CAP": "1"}
    assert role_argv("worker", source)[-1] == "worker"
    assert role_argv("scheduler", source)[-1] == "scheduler"
    with pytest.raises(DeploymentConfigurationError):
        role_argv("beat", source)


def test_full_management_cannot_run_arbitrary_shell_or_candidate_commands():
    profile = deployment_profile({"SPACEWORKS_DEPLOYMENT_MODE": "managed"})
    for command in (["sh", "-c", "anything"], ["python", "manage.py", "shell"], ["python", "manage.py", "import_backup_archive"]):
        with pytest.raises(DeploymentConfigurationError):
            validate_process(profile, ProcessRole.MANAGEMENT, command)
