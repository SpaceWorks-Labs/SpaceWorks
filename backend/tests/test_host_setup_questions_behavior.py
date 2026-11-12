"""Exercise the real questionnaire and dotenv writer without Docker or host effects."""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH, reason="requires bash")


def defaults():
    # model, website, HTTPS, storage, outside-services gate, control plane, loopback, organization,
    # space name, MFA, providers; product page at /; 31 area answers; admin/email/password; repo/runner/proceed.
    return ["", "", "", "", "", "", "", "Test Organization", "", ""] + [""] * 32 + ["", "owner@example.org", "", "", "", ""]


def question_tail():
    return [""] * 32 + ["", "owner@example.org", "private-password", "", "", ""]


# The first prompt is "Use quick setup?"; "n" takes the full questionnaire these tests pin.
FULL = "n"


def questionnaire(tmp_path, answers, write=False, runner_supported=True, quick=False):
    scripts = tmp_path / "scripts"
    scripts.mkdir(exist_ok=True)
    shutil.copytree(ROOT / "scripts/installer", scripts / "installer", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("setup-questions.sh", "setup-question-input.sh", "setup-area-questions.sh", "setup-areas-json.sh", "setup-write-environment.sh", "spaceworks-repository.sh"):
        source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        source = source.replace("exec 3</dev/tty", "exec 3<&0")
        source = source.replace('[[ "$(uname -s)" == Linux ]] && command -v systemctl >/dev/null 2>&1', "true")
        source = source.replace("[[ -d /run/systemd/system ]]", "true" if runner_supported else "false")
        (scripts / name).write_text(source, encoding="utf-8", newline="\n")
    library = tmp_path / "frontend/docker"
    library.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "frontend/docker/control-plane-allowlist.sh", library)
    script = '''set -euo pipefail
ROOT="$PWD"
source scripts/spaceworks-repository.sh
source scripts/setup-questions.sh
ask_setup_questions || exit 0
save_setup_answers "$PWD/.spaceworks-answers"
'''
    if write:
        script += "source scripts/setup-write-environment.sh\nwrite_setup_environment\n"
    return subprocess.run(
        [BASH, "-c", script], cwd=tmp_path, input="\n".join(([] if quick else [FULL]) + answers) + "\n",
        env=os.environ.copy(), text=True, capture_output=True, timeout=30,
    )


def test_defaults_keep_standard_bundled_http_topology(tmp_path):
    result = questionnaire(tmp_path, defaults(), write=True)
    assert result.returncode == 0, result.stderr
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "SPACEWORKS_RUN_FRONTEND='yes'" in env
    assert "SPACEWORKS_STORAGE='bundled'" in env
    assert "ENABLE_HTTPS='false'" in env
    assert "AUTH_COOKIE_SECURE='false'" in env
    assert "AUTH_COOKIE_SAMESITE='Lax'" in env
    assert "AWS_S3_PUBLIC_ENDPOINT_URL='http://localhost:9000'" in env
    assert (tmp_path / ".spaceworks-layer").read_text(encoding="utf-8") == "none\n"
    assert "website" in result.stdout and "Silo storage" in result.stdout
    assert "Proceed? [Y/n]" in result.stdout
    assert (tmp_path / ".spaceworks-answers").stat().st_mode & 0o777 == 0o600
    # Pointer configuration reads generated DB passwords literally, without quote marks.
    assert "POSTGRES_APP_PASSWORD='" not in env


def test_summary_refusal_writes_no_answers_or_environment(tmp_path):
    answers = defaults()
    answers[-1] = "n"
    result = questionnaire(tmp_path, answers, write=True)
    assert result.returncode == 0, result.stderr
    assert "Cancelled" in result.stdout
    assert not (tmp_path / ".env").exists()
    assert not (tmp_path / ".spaceworks-answers").exists()
    assert not (tmp_path / ".spaceworks-layer").exists()


def test_api_only_requires_https_and_uses_standard_containers(tmp_path):
    answers = ["", "2", "https://tools.example.org", "1", "3", "api.example.org",
               "", "", "Test Organization", "My Lab", "", ""] + question_tail()
    result = questionnaire(tmp_path, answers, write=True)
    assert result.returncode == 0, result.stderr
    assert "Choose one of the listed options" in result.stdout
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "SPACEWORKS_RUN_FRONTEND='no'" in env
    assert "CORS_ALLOWED_ORIGINS='https://tools.example.org'" in env
    assert "CSRF_TRUSTED_ORIGINS='https://tools.example.org'" in env
    assert "API_BIND='127.0.0.1'" in env
    assert "API_PORT='8080'" in env
    assert "AUTH_COOKIE_SECURE='true'" in env
    assert "AUTH_COOKIE_SAMESITE='None'" in env
    assert "private-password" not in result.stdout
    assert "files.api.example.org" in result.stdout


def test_external_storage_answers_and_secrets_are_private(tmp_path):
    # endpoint, browser endpoint, region, private bucket, (clashing) public bucket, a distinct one,
    # keys, public image URL, storage profile (limited uploads with put), outside-services gate (no).
    answers = ["", "", "", "2", "https://objects.example.org", "", "", "",
               "evidence", "images", "access-key", "secret-$key", "https://cdn.example.org/images",
               "", "", "", "", "Test Organization", "My Lab", "", ""] + question_tail()
    result = questionnaire(tmp_path, answers, write=True)
    assert result.returncode == 0, result.stderr
    assert "must use different buckets" in result.stdout
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "SPACEWORKS_STORAGE='external'" in env
    assert "AWS_SECRET_ACCESS_KEY='secret-$key'" in env
    assert "STORAGE_PRESIGN_METHOD='put'" in env
    assert "PUBLIC_IMAGE_BUCKET='images'" in env
    assert "secret-$key" not in result.stdout and "access-key" not in result.stdout
    assert "Silo storage" not in result.stdout.split("Will run:")[1]


def test_platform_uses_saas_edge_and_operator_subdomain(tmp_path):
    answers = ["3", "community.example.org", "", "owner@example.org", "", "",
               "Test Organization", "My Lab", "lab", "", ""] + question_tail()
    result = questionnaire(tmp_path, answers, write=True)
    assert result.returncode == 0, result.stderr
    assert "Hosting other makerspaces on subdomains requires automatic HTTPS" in result.stdout
    assert "HTTPS [" not in result.stdout  # HTTPS mode is forced, not silently guessed.
    assert (tmp_path / ".spaceworks-layer").read_text(encoding="utf-8") == "saas\n"
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "PLATFORM_DOMAIN_SUFFIX='.community.example.org'" in env
    assert "PLATFORM_FIRST_HOST='lab.community.example.org'" in env
    assert "CADDY_SAAS_CONFIG='./deploy/Caddyfile.saas-install'" in env


@pytest.mark.parametrize("layer", ["none", "tls", "saas", "build-tls"])
def test_deployment_layers_preserve_frontend_storage_choices(tmp_path, layer):
    (tmp_path / ".env").write_text("SPACEWORKS_RUN_FRONTEND='no'\nSPACEWORKS_STORAGE='external'\n")
    result = subprocess.run(
        [BASH, "-c", '''set -euo pipefail
ROOT="$PWD"
source "$TEST_DEPLOYMENT_HELPER"
COMPOSE_FILES=()
append_deployment_layers "$TEST_LAYER" "$ROOT"
printf '%s\n' "$DEPLOYMENT_SUFFIX" "${COMPOSE_FILES[@]}"
'''], cwd=tmp_path,
        env={**os.environ, "TEST_DEPLOYMENT_HELPER": (ROOT / "scripts/compose-deployment.sh").as_posix(),
             "TEST_LAYER": layer}, text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "-api-only-external-storage" in result.stdout
    assert "compose.api-only.yml" in result.stdout
    assert "compose.external-storage.yml" in result.stdout
    assert ("compose.api-only-edge.yml" in result.stdout) == (layer.endswith(("tls", "saas")))


def test_private_answers_roundtrip_and_reject_public_mode(tmp_path):
    result = questionnaire(tmp_path, defaults())
    assert result.returncode == 0, result.stderr
    command = 'source scripts/setup-question-input.sh; load_setup_answers .spaceworks-answers; test "$ADMINEMAIL" = owner@example.org'
    result = subprocess.run([BASH, "-c", command], cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    (tmp_path / ".spaceworks-answers").chmod(0o644)
    result = subprocess.run([BASH, "-c", command.replace('; test ', ' || exit 1; test ')], cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode != 0 and "mode 600" in result.stderr


def test_direct_setup_cancellation_precedes_docker_and_writes(tmp_path):
    scripts = tmp_path / "scripts"
    shutil.copytree(ROOT / "scripts", scripts)
    questions = scripts / "setup-questions.sh"
    questions.write_text(questions.read_text(encoding="utf-8").replace("exec 3</dev/tty", "exec 3<&0").replace('[[ "$(uname -s)" == Linux ]] && command -v systemctl >/dev/null 2>&1', "true").replace("[[ -d /run/systemd/system ]]", "true"), newline="\n")
    setup = (ROOT / "setup.sh").read_text(encoding="utf-8").replace('require_install_owner "$ROOT/setup.sh" "$@"', ":")
    (tmp_path / "setup.sh").write_text(setup, newline="\n")
    answers = defaults()
    answers[-1] = "n"
    result = subprocess.run([BASH, "setup.sh"], cwd=tmp_path, input="\n".join([FULL] + answers) + "\n",
                            text=True, capture_output=True, timeout=30)
    # Cancelling is distinct from success (130), so a caller never records an install.
    assert result.returncode == 130, result.stderr
    assert "Cancelled" in result.stdout and "Docker is missing" not in result.stderr
    assert not (tmp_path / ".env").exists()


def test_external_storage_overlay_removes_all_storage_dependencies():
    overlay = (ROOT / "docker/compose.external-storage.yml").read_text(encoding="utf-8")
    assert "profiles: [storage-disabled]" in overlay
    for name in ("backend", "candidate-backend"):
        block = re.split(r"\n  [a-z-]+:\n", overlay.split(f"  {name}:\n")[1], maxsplit=1)[0]
        # Removed key by key so the overlay stacks with compose.external-db/redis.yml.
        assert "createbuckets: !reset null" in block
        assert "depends_on: !override" not in block
    assert "profiles: [website-disabled]" in (ROOT / "docker/compose.api-only.yml").read_text(encoding="utf-8")


@pytest.mark.parametrize('answers,warning', [
    (["9", "1"], 'Choose one of the listed options'),
    (["3", "bad-.example.org", "community.example.org"], 'Enter a DNS domain'),
])
def test_invalid_choices_reask_before_any_effect(tmp_path, answers, warning):
    result = questionnaire(tmp_path, answers)
    assert warning in result.stdout
    assert not (tmp_path / '.env').exists() and not (tmp_path / '.spaceworks-answers').exists()


def test_confirmed_resume_file_keeps_first_instance_setup_pending(tmp_path):
    helper = (ROOT / 'scripts/setup-first-run.sh').as_posix()
    (tmp_path / '.env').write_text('SECRET_KEY=existing\n')
    result = subprocess.run([BASH, '-c', 'ROOT="$PWD"; say() { :; }; ANSWERS_CONFIRMED=yes; source "$TEST_HELPER"; test "$FIRST_RUN" = 1'],
                            cwd=tmp_path, env={**os.environ, 'TEST_HELPER': helper}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / '.env').read_text(encoding="utf-8") == 'SECRET_KEY=existing\n'



def test_native_windows_secures_the_answers_file_before_any_secret_is_written(tmp_path):
    # Native Windows has no POSIX 600: the helper applies the owner-only ACL through
    # private_files.py to the still-empty file, then writes the confirmed answers.
    helper = (ROOT / 'scripts/setup-question-input.sh').as_posix()
    script = r'''set -euo pipefail
source "$TEST_HELPER"
uname() { echo MINGW64_NT; }
python3() { printf '%s size=%s\n' "$2" "$(stat -c %s "$3")" > secured; }
ADMINPASS='private-password'
ANSWERS_CONFIRMED=yes
persist_setup_answers "$PWD/answers"
'''
    result = subprocess.run([BASH, '-c', script], cwd=tmp_path,
                            env={**os.environ, 'TEST_HELPER': helper}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / 'secured').read_text() == "secure size=0\n"
    assert (tmp_path / 'answers').stat().st_mode & 0o777 == 0o600
    assert "ADMINPASS=private-password" in (tmp_path / 'answers').read_text()


def test_origin_hosts_are_canonicalized_before_persistence(tmp_path):
    answers = ["", "2", "https://TOOLS.EXAMPLE.ORG", "3", "api.example.org", "", "",
               "Test Organization", "My Lab", "", ""] + question_tail()
    result = questionnaire(tmp_path, answers, write=True)
    assert result.returncode == 0, result.stderr
    assert "CORS_ALLOWED_ORIGINS='https://tools.example.org'" in (tmp_path / '.env').read_text(encoding="utf-8")


def test_runner_question_defaults_no_and_keeps_fork_images(tmp_path):
    answers = defaults()
    answers[-3] = "Example-Owner/MyFork"
    result = questionnaire(tmp_path, answers, write=True)
    assert result.returncode == 0, result.stderr
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "SPACEWORKS_REPOSITORY='Example-Owner/MyFork'" in env
    assert "MAKERSPACE_BACKEND_IMAGE='ghcr.io/example-owner/spaceworks-backend'" in env
    assert "MAKERSPACE_FRONTEND_IMAGE='ghcr.io/example-owner/spaceworks-frontend'" in env
    assert "ALLINONE" not in env
    assert "Install a GitHub Actions runner on this server for automatic deploys? [y/N]" in result.stdout
    assert "install GitHub Actions runner: N" in result.stdout
    assert "migrate builds the database tables. It runs once and stops. It's required." in result.stdout
    assert "orchestration is a start-up safety check. It runs once and stops. It's required." in result.stdout
    saved = (tmp_path / ".spaceworks-answers").read_text(encoding="utf-8")
    assert "SPACEWORKS_REPOSITORY=Example-Owner/MyFork" in saved and "INSTALL_RUNNER=N" in saved


def test_runner_yes_is_recorded_and_shown_in_summary(tmp_path):
    answers = defaults()
    answers[-2] = "y"
    result = questionnaire(tmp_path, answers, write=True)
    assert result.returncode == 0, result.stderr
    assert "install GitHub Actions runner: y" in result.stdout
    assert "INSTALL_RUNNER=y" in (tmp_path / ".spaceworks-answers").read_text(encoding="utf-8")
    # No runner registration token is persisted. PUSH_TOKEN_HMAC_KEY is the generated
    # push-fingerprint key (installer continuity keys), not a runner credential.
    lines = (tmp_path / ".env").read_text(encoding="utf-8").splitlines()
    assert not any("token" in line.lower() for line in lines if not line.startswith("PUSH_TOKEN_HMAC_KEY="))


def test_rejected_summary_never_generates_configuration(tmp_path):
    answers = defaults()
    answers[-1] = "n"
    result = questionnaire(tmp_path, answers, write=True)
    assert "Cancelled" in result.stdout
    assert not list(tmp_path.glob(".spaceworks*"))
    assert not (tmp_path / ".env").exists()


def test_unsupported_runner_host_skips_question_and_records_no(tmp_path):
    answers = defaults()
    answers.pop(-2)
    result = questionnaire(tmp_path, answers, runner_supported=False)
    assert result.returncode == 0, result.stderr
    assert "only Linux with running systemd; skipping" in result.stdout
    assert "Install a GitHub Actions runner on this server for automatic deploys?" not in result.stdout
    assert "INSTALL_RUNNER=N" in (tmp_path / ".spaceworks-answers").read_text(encoding="utf-8")


@pytest.mark.parametrize("host", ["192.168.1.50", "makerspace.local", "0.0.0.0"])
def test_plain_http_rejects_lan_and_reasks_for_loopback(tmp_path, host):
    answers = defaults()
    answers[6:7] = [host, "127.0.0.1"]  # index 6 is the web address (5 is the control-panel gate)
    result = questionnaire(tmp_path, answers, write=True)
    assert result.returncode == 0, result.stderr
    assert "LAN access requires HTTPS" in result.stdout
    env = (tmp_path / ".env").read_text()
    assert "PUBLIC_APP_BASE_URL='http://127.0.0.1'" in env
    for key in ("HTTP_PORT_BIND", "API_BIND", "MINIO_API_BIND", "MINIO_CONSOLE_BIND"):
        assert f"{key}='127.0.0.1'" in env


def test_writer_refuses_resumed_plain_http_lan_answers_before_creating_env(tmp_path):
    result = subprocess.run([BASH, "-c", 'die() { echo "$*" >&2; exit 1; }; source "$WRITER"; ANSWERS_CONFIRMED=yes; HTTPS_MODE=1; WEBHOST=192.168.1.50; write_setup_environment'],
                            cwd=tmp_path, env={**os.environ, "WRITER": (ROOT / "scripts/setup-write-environment.sh").as_posix()},
                            text=True, capture_output=True, timeout=10)
    assert result.returncode != 0 and "LAN addresses require HTTPS" in result.stderr
    assert not (tmp_path / ".env").exists()


# Quick setup (decision 235): gate, frontend, web address, name, every-area shortcut,
# eight area switches, timezone, email, proceed.
def quick_answers(address="", email="owner@example.org"):
    return ["", "", address, ""] + [""] * 9 + ["", email, ""]


def test_quick_setup_defaults_to_local_http_and_asks_the_minimum(tmp_path):
    result = questionnaire(tmp_path, quick_answers(), write=True, quick=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("]: ") == 16
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "SPACEWORKS_RUN_FRONTEND='yes'" in env and "SPACEWORKS_STORAGE='bundled'" in env
    assert "ENABLE_HTTPS='false'" in env
    # "Hosting model" is not a prompt here, but the deployment summary line starts with it
    # (the summary also prints "Maximum active loans per borrower: 0", so only the prompt form is a marker).
    for skipped in ("Hosting model:\n", "Organization name", "Admin login username", "Admin password",
                    "Maximum active loans per borrower [", "Install a GitHub Actions runner", "Reach the control panel"):
        assert skipped not in result.stdout
    saved = (tmp_path / ".spaceworks-answers").read_text(encoding="utf-8")
    assert r"ORG_NAME=My\ Makerspace" in saved and "ADMINUSER=admin" in saved and "GEN_PASS=1" in saved
    assert "ANSWERS_CONFIRMED=yes" in saved


def test_quick_setup_domain_turns_on_automatic_https_with_the_admin_email(tmp_path):
    # A bad address is asked again, then the domain is accepted (and lower-cased).
    answers = ["", "", "http://bad", "Tools.Example.org"] + quick_answers()[3:]
    result = questionnaire(tmp_path, answers, write=True, quick=True)
    assert result.returncode == 0, result.stderr
    assert "Enter a domain name such as tools.example.org" in result.stdout
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "ENABLE_HTTPS='true'" in env
    assert "TLS_EMAIL='owner@example.org'" in env
    assert "tools.example.org" in env and "Tools.Example.org" not in env


def test_quick_setup_cancel_writes_nothing(tmp_path):
    answers = quick_answers()
    answers[-1] = "n"
    result = questionnaire(tmp_path, answers, write=True, quick=True)
    assert result.returncode == 0 and "Cancelled" in result.stdout
    assert not (tmp_path / ".env").exists() and not (tmp_path / ".spaceworks-answers").exists()


def test_landing_question_defaults_to_yes_and_writes_true(tmp_path):
    result = questionnaire(tmp_path, defaults(), write=True)
    assert result.returncode == 0, result.stderr
    assert "Show the SpaceWorks product page at your site's front page? [Y/n]" in result.stdout
    assert "product page at /: shown" in result.stdout
    assert "HUB_LANDING_ENABLED='true'" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_landing_answer_no_writes_false_and_roundtrips(tmp_path):
    answers = defaults()
    answers[11] = "n"  # the first answer after the sign-in providers
    result = questionnaire(tmp_path, answers, write=True)
    assert result.returncode == 0, result.stderr
    assert "product page at /: hidden" in result.stdout
    assert "HUB_LANDING_ENABLED='false'" in (tmp_path / ".env").read_text(encoding="utf-8")
    assert "SETUP_HUB_LANDING=n" in (tmp_path / ".spaceworks-answers").read_text(encoding="utf-8")


def test_quick_setup_keeps_the_landing_page_on_without_asking(tmp_path):
    result = questionnaire(tmp_path, quick_answers(), write=True, quick=True)
    assert result.returncode == 0, result.stderr
    assert "product page at your site" not in result.stdout
    assert "HUB_LANDING_ENABLED='true'" in (tmp_path / ".env").read_text(encoding="utf-8")
