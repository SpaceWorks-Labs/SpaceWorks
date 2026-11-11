"""Installer frontend mode: Full (web app + API) or API-only. Real bash, no Docker."""
import os
import subprocess

import pytest

from tests.test_host_setup_questions_behavior import BASH, ROOT, defaults, question_tail, questionnaire

pytestmark = pytest.mark.skipif(not BASH, reason="requires bash")

# model, frontend, website (blank), HTTPS (own proxy), domain, storage, outside-services gate, org, space, MFA, providers.
API_ONLY_NO_SITE = ["", "2", "", "3", "api.example.org", "", "", "Test Organization", "My Lab", "", ""]


def env_of(tmp_path):
    return (tmp_path / ".env").read_text(encoding="utf-8")


def test_question_offers_full_and_api_only(tmp_path):
    result = questionnaire(tmp_path, defaults(), write=True)
    assert result.returncode == 0, result.stderr
    assert "1) Full - the web app and the API." in result.stdout
    assert "2) API-only - the backend for mobile apps and integrations" in result.stdout
    assert "install: Full (web app + API)" in result.stdout
    assert "SPACEWORKS_RUN_FRONTEND='yes'" in env_of(tmp_path)


def test_api_only_without_a_website_keeps_links_on_this_server(tmp_path):
    result = questionnaire(tmp_path, API_ONLY_NO_SITE + question_tail(), write=True)
    assert result.returncode == 0, result.stderr
    env = env_of(tmp_path)
    assert "SPACEWORKS_RUN_FRONTEND='no'" in env
    assert "SPACEWORKS_WEB_UPSTREAM='api-edge:80'" in env
    assert "PUBLIC_APP_BASE_URL='https://api.example.org'" in env
    assert "CORS_ALLOWED_ORIGINS='https://api.example.org'" in env
    assert "install: API-only (no web app on this server), no website" in result.stdout
    assert "set PUBLIC_APP_BASE_URL in .env" in result.stdout
    assert "API edge" in result.stdout.split("Will run:")[1]
    assert ", website" not in result.stdout.split("Will run:")[1]


def test_api_only_with_a_website_elsewhere_uses_its_origin(tmp_path):
    answers = ["", "2", "https://tools.example.org"] + API_ONLY_NO_SITE[3:] + question_tail()
    result = questionnaire(tmp_path, answers, write=True)
    assert result.returncode == 0, result.stderr
    assert "PUBLIC_APP_BASE_URL='https://tools.example.org'" in env_of(tmp_path)
    assert "website elsewhere" in result.stdout
    assert "set PUBLIC_APP_BASE_URL" not in result.stdout


@pytest.mark.parametrize("preset,stored", [("api-only", "no"), ("full", "yes")])
def test_frontend_preset_answers_the_question(tmp_path, monkeypatch, preset, stored):
    monkeypatch.setenv("SPACEWORKS_FRONTEND", preset)
    # The same answers as without a preset, minus the frontend answer itself.
    full = defaults()
    answers = API_ONLY_NO_SITE[:1] + API_ONLY_NO_SITE[2:] + question_tail() if preset == "api-only" else full[:1] + full[2:]
    result = questionnaire(tmp_path, answers, write=True)
    assert result.returncode == 0, result.stderr
    assert "(preset by --frontend)" in result.stdout
    assert "Frontend [" not in result.stdout
    assert f"SPACEWORKS_RUN_FRONTEND='{stored}'" in env_of(tmp_path)


def test_unknown_frontend_preset_is_refused_before_any_answer(tmp_path, monkeypatch):
    monkeypatch.setenv("SPACEWORKS_FRONTEND", "website")
    result = questionnaire(tmp_path, defaults(), write=True)
    assert "Use --frontend full or --frontend api-only" in result.stderr
    assert not (tmp_path / ".spaceworks-answers").exists()
    assert not (tmp_path / ".env").exists()


def run_preset(tmp_path, preset, answers):
    helper = (ROOT / "scripts/installer/frontend-choice.sh").as_posix()
    script = '''set -euo pipefail
source "$HELPER"
SETUP_NON_INTERACTIVE=1
declare -gA INPUT_ANSWERS=() INPUT_USED=()
for pair in $ANSWERS; do INPUT_ANSWERS["${pair%%=*}"]="${pair#*=}"; done
frontend_preset
printf 'RUN_FRONTEND=%s used=%s\\n' "$RUN_FRONTEND" "${INPUT_USED[RUN_FRONTEND]:-}"
'''
    return subprocess.run([BASH, "-c", script], cwd=tmp_path, text=True, capture_output=True, timeout=10,
                          env={**os.environ, "HELPER": helper, "SPACEWORKS_FRONTEND": preset, "ANSWERS": answers})


def test_noninteractive_answer_must_agree_with_the_preset(tmp_path):
    agreed = run_preset(tmp_path, "api-only", "RUN_FRONTEND=2")
    assert agreed.returncode == 0, agreed.stderr
    assert "RUN_FRONTEND=2 used=1" in agreed.stdout
    clash = run_preset(tmp_path, "api-only", "RUN_FRONTEND=1")
    assert clash.returncode != 0
    assert "disagrees with --frontend" in clash.stderr


@pytest.mark.parametrize("model,frontend,origins,called", [
    ("1", "2", "", False),          # API-only, no website: nothing to record, no subdomain
    ("1", "2", "https://tools.example.org", True),
    ("1", "1", "", False),
    ("3", "1", "", True),           # hosted platforms provision a subdomain
])
def test_setup_domain_runs_only_with_a_website_or_platform(tmp_path, model, frontend, origins, called):
    helper = (ROOT / "scripts/setup-host-orchestration.sh").as_posix()
    script = '''set -euo pipefail
source "$HELPER"
fake_compose() { echo called > compose-called; }
COMPOSE=(fake_compose)
HOSTING_MODEL="$MODEL"; RUN_FRONTEND="$FRONTEND"; SITE_ORIGINS="$ORIGINS"; MSNAME=Lab; MS_SUBDOMAIN=lab
configure_setup_domain
'''
    result = subprocess.run([BASH, "-c", script], cwd=tmp_path, text=True, capture_output=True, timeout=10,
                            env={**os.environ, "HELPER": helper, "MODEL": model, "FRONTEND": frontend, "ORIGINS": origins})
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "compose-called").exists() == called


def test_setup_refuses_a_frontend_flag_that_contradicts_the_install(tmp_path):
    (tmp_path / ".env").write_text("SPACEWORKS_RUN_FRONTEND='yes'\n")
    script = (ROOT / "setup.sh").read_text(encoding="utf-8").split("case \"${SPACEWORKS_DEPLOYMENT_PROFILE:-full}\" in\n  full) ;;")[0]
    script = script.replace('cd "$(dirname "$0")"', ":").replace('require_install_owner "$ROOT/setup.sh" "$@"', ":")
    script = script.replace('source "$ROOT/scripts/install-owner.sh"', ":")
    script = script.replace('source "$ROOT/scripts/compose-deployment.sh"', f'source "{(ROOT / "scripts/compose-deployment.sh").as_posix()}"')
    (tmp_path / "head.sh").write_text(script, encoding="utf-8", newline="\n")
    refused = subprocess.run([BASH, "head.sh", "--frontend", "api-only"], cwd=tmp_path, text=True, capture_output=True, timeout=10)
    assert refused.returncode == 64
    assert "already runs Full" in refused.stderr
    kept = subprocess.run([BASH, "head.sh", "--frontend", "full"], cwd=tmp_path, text=True, capture_output=True, timeout=10)
    assert kept.returncode == 0, kept.stderr
    bad = subprocess.run([BASH, "head.sh", "--frontend=web"], cwd=tmp_path, text=True, capture_output=True, timeout=10)
    assert bad.returncode == 64 and "Use --frontend full" in bad.stderr
