"""Installer Redis choice 3, "None (cron mode)": questionnaire, overlay, selector, probes, switch script.

Real bash and static Compose YAML; no Docker daemon, no network. The decision-43 rule under test: the HTTP
tick endpoint stays free-profile only, so cron mode runs `run_scheduled_tasks` from a scheduler loop and never
sets that profile.
"""
import importlib.util
import os
import subprocess
import sys
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest
import yaml

from tests.cloud.installer.test_runtime_completion import COMMON, SERVICES
from tests.test_host_setup_outside_services import BASH, ROOT, bash, layers, services_depending_on
from tests.test_host_setup_questions_behavior import question_tail, questionnaire

pytestmark = pytest.mark.skipif(not BASH, reason="requires bash")

OVERLAY = ROOT / "docker" / "compose.no-redis.yml"


def overlay():
    return yaml.safe_load(OVERLAY.read_text(encoding="utf-8").replace("!reset null", "null"))["services"]


def base():
    return yaml.safe_load((ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"))["services"]


def test_overlay_parks_redis_and_the_worker_and_frees_every_dependent():
    services = overlay()
    assert services["redis"]["profiles"] == ["redis-disabled"]
    assert services["worker"]["profiles"] == ["redis-disabled"]
    text = OVERLAY.read_text(encoding="utf-8")
    assert "depends_on: !override" not in text  # removed key by key so overlays stack in any order
    for service in services_depending_on("redis") - {"worker"}:
        assert "redis" in services[service]["depends_on"], service
    assert "redis" in services["worker"]["depends_on"]


def test_every_backend_process_gets_the_same_brokerless_settings_as_literal_empty_strings():
    services = overlay()
    backend_env = [name for name, row in base().items()
                   if isinstance(row.get("environment"), dict) and "CELERY_BROKER_URL" in row["environment"]]
    for name in backend_env:
        if name == "worker":
            continue  # parked
        env = services[name]["environment"]
        assert env["CELERY_BROKER_URL"] == "" and env["CACHE_URL"] == "" and env["LIVE_REDIS_URL"] == "", name
        assert env["CELERY_TASK_ALWAYS_EAGER"] == "True", name
        assert (env["CLOUD_TASK_PROFILE"], env["CLOUD_SCHEDULER"]) == ("brokerless", "external"), name


def test_beat_slot_runs_scheduled_tasks_from_a_loop_and_never_enables_the_free_profile_tick():
    command = overlay()["beat"]["command"]
    assert command[:2] == ["--role", "beat"] and command[2:4] == ["sh", "-c"]
    loop = command[4]
    assert "run_scheduled_tasks --due-only --lane scheduler" in loop and "--lane worker" in loop and "sleep 60" in loop
    text = OVERLAY.read_text(encoding="utf-8")
    for forbidden in ("SPACEWORKS_DEPLOYMENT_PROFILE", "FREE_TICK", "SPACEWORKS_DEPLOYMENT_MODE", "CLOUD_SCHEDULER: tick"):
        assert forbidden not in text.replace("(decision 43)", ""), forbidden


def test_selector_adds_the_overlay_for_none_and_names_the_valid_values(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "compose-deployment.sh").write_text(
        (ROOT / "scripts/compose-deployment.sh").read_text(encoding="utf-8"), newline="\n")
    result = layers(tmp_path, "SPACEWORKS_REDIS='none'\n")
    suffix, *files = result.stdout.splitlines()
    assert result.returncode == 0 and suffix == "-no-redis"
    assert [f.rsplit("/", 1)[1] for f in files] == ["compose.no-redis.yml"]
    bad = layers(tmp_path, "SPACEWORKS_REDIS='valkey'\n")
    assert bad.returncode == 64 and "bundled, external or none" in bad.stderr


def test_service_sets_for_updates_and_recovery_leave_the_parked_worker_out(tmp_path):
    (tmp_path / ".env").write_text("SPACEWORKS_REDIS='none'\n", newline="\n")
    script = 'ROOT="$PWD"; source scripts/compose-deployment.sh; deployment_services; ' \
             'echo "${WORKER_SERVICES[*]}|${ROLLBACK_SERVICES[*]}|${IMAGE_SERVICES[*]}"'
    out = subprocess.run([BASH, "-c", script], cwd=ROOT, text=True, capture_output=True, timeout=30,
                         env={**os.environ, "SPACEWORKS_STATIC_ENV_FILE": str(tmp_path / ".env"),
                              "SPACEWORKS_COMPOSE_LAYER": "none"})
    assert out.returncode == 0, out.stderr
    workers, rollback, images = out.stdout.strip().split("|")
    assert "worker" not in workers.split() + rollback.split() + images.split()
    assert "beat" in workers.split() and "beat" in rollback.split()


def test_redis_answer_numbers_map_to_the_setting_words():
    for number, word in (("1", "bundled"), ("2", "external"), ("3", "none")):
        assert bash(f'redis_choice_word {number}').stdout.strip() == word


def none_answers(*redis):
    # model, website, HTTPS (own proxy), domain | storage local | gate=yes | database local | Redis | email later
    return (["", "", "3", "api.example.org", "", "y", "1", *(redis or ("3",)), "1",
             "", "Test Organization", "My Lab", "", ""] + question_tail())


def test_the_questionnaire_offers_none_and_writes_no_broker_settings(tmp_path):
    result = questionnaire(tmp_path, none_answers(), write=True)
    assert result.returncode == 0, result.stderr
    assert "3) None (cron mode)" in result.stdout
    assert "Redis none (cron mode)" in result.stdout
    assert "scheduler loop (no worker or Redis)" in result.stdout
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "SPACEWORKS_REDIS='none'" in env
    assert "CELERY_BROKER_URL" not in env  # the overlay sets it; an empty .env value would fall back to Redis


def test_other_answers_still_write_bundled_and_an_out_of_range_one_is_asked_again(tmp_path):
    first, second = tmp_path / "bundled", tmp_path / "asked-again"
    first.mkdir()
    second.mkdir()
    assert questionnaire(first, none_answers("1"), write=True).returncode == 0
    assert "SPACEWORKS_REDIS='bundled'" in (first / ".env").read_text(encoding="utf-8")
    refused = questionnaire(second, none_answers("4", "3"), write=True)
    assert refused.returncode == 0, refused.stderr
    assert "SPACEWORKS_REDIS='none'" in (second / ".env").read_text(encoding="utf-8")


def test_outside_connection_checks_skip_redis_in_cron_mode():
    script = ('deployment_value() { printenv "$1" || true; }\n'
              'source scripts/installer/outside-checks.sh\n'
              'SPACEWORKS_REDIS=none outside_check_components; echo "|"; SPACEWORKS_REDIS=external outside_check_components')
    out = subprocess.run([BASH, "-c", script], cwd=ROOT, text=True, capture_output=True, timeout=30)
    none, external = out.stdout.split("|")
    assert "redis" not in none and "redis" in external


def test_the_completion_check_expects_no_worker_in_cron_mode():
    text = (ROOT / "scripts/installer/completion.sh").read_text(encoding="utf-8")
    assert 'services=(backend live beat)' in text and 'SPACEWORKS_REDIS)" != none' in text


def worker_modules(broker):
    return {
        "config.celery": NS(app=NS(conf=NS(task_always_eager=True), send_task=lambda *a, **k: None)),
        "django.core.cache": NS(cache=NS(get=lambda key: None, delete=lambda key: None)),
        "django.conf": NS(settings=NS(CELERY_BROKER_URL=broker,
                                      CACHES={"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache"}})),
    }


def test_the_worker_probe_accepts_inline_tasks_only_when_there_is_no_broker():
    with patch.dict(sys.modules, worker_modules("")):
        assert SERVICES.worker() == "inline_tasks_no_worker"
    with patch.dict(sys.modules, worker_modules("redis://redis:6379/0")), pytest.raises(COMMON.ProbeError):
        SERVICES.worker()
    spec = importlib.util.spec_from_file_location("runtime_probes", ROOT / "scripts/installer/runtime-probes.py")
    probes = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probes)
    assert "inline_tasks_no_worker" in probes.ALLOWED["worker"]


def test_switch_services_knows_the_none_choice():
    text = (ROOT / "scripts/switch-services.sh").read_text(encoding="utf-8")
    assert 'redis_choice_word "$REDIS_CHOICE"' in text and "none (cron mode" in text
    out = bash('redis_choice_word 3')
    assert out.stdout.strip() == "none"
    assert "docker/compose.no-redis.yml" in (ROOT / "scripts/install-host-bundle.sh").read_text(encoding="utf-8")
