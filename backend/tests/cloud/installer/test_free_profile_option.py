"""Opt-in free profile in the VPS installer, and continuity-key generation (local only).

Replaces the earlier `test_full_installer_has_no_free_profile_mode`: the owner asked the
installer to OFFER the free profile, with full staying the default and unchanged.
"""
import base64
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[4]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH or sys.platform == "win32", reason="requires Linux Bash")
FREE_OPTION = ("  4) Free profile (opt-in) - one web process, no worker or scheduler; "
               "external services and an HTTP tick.")
ANSWERS = {"Use quick setup": "n", "Admin email": "owner@example.org", "Organization name": "Example Org"}


def installer_copy(tmp_path):
    """A private copy of the shipped installer files (the tty is replaced by stdin)."""
    target = tmp_path / "install"
    shutil.copytree(ROOT / "scripts", target / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    for relative in ("setup.sh", "deploy/cloud/free.env.example", "frontend/docker/control-plane-allowlist.sh"):
        (target / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / relative, target / relative)
    questions = target / "scripts/setup-questions.sh"
    questions.write_text(questions.read_text().replace("exec 3</dev/tty", "exec 3<&0"), newline="\n")
    return target


def drive(root, env=None, answers=None):
    """Answer the real questionnaire prompt by prompt; Enter for anything not named."""
    answers = {**ANSWERS, **(answers or {})}
    process = subprocess.Popen(
        [BASH, "-c", 'set -euo pipefail; source scripts/setup-questions.sh; status=0; '
                     'ask_setup_questions || status=$?; '
                     'echo "PROFILE=${SPACEWORKS_DEPLOYMENT_PROFILE:-unset} STATUS=$status"'],
        cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**{k: v for k, v in os.environ.items() if k != "SPACEWORKS_DEPLOYMENT_PROFILE"},
             "SPACEWORKS_EDITION": "makerspace", **(env or {})}, bufsize=0)
    lines, buffer = [], b""
    while True:
        char = process.stdout.read(1)
        if not char:
            break
        buffer += char
        if buffer.endswith(b"]: "):
            line = buffer.decode()
            label = line.rsplit(" [", 1)[0]
            answer = next((value for key, value in answers.items() if label.startswith(key)), "")
            lines.append(line + answer)
            process.stdin.write((answer + "\n").encode())
            process.stdin.flush()
            buffer = b""
        elif char == b"\n":
            lines.append(buffer.decode().rstrip("\n"))
            buffer = b""
    process.wait(timeout=60)
    return lines


def test_interactive_default_is_full_and_only_adds_the_free_option_line(tmp_path):
    root = installer_copy(tmp_path)
    explicit_full = drive(root, {"SPACEWORKS_DEPLOYMENT_PROFILE": "full"})
    default = drive(root)
    assert explicit_full[-1] == "PROFILE=full STATUS=0"
    assert default[-1] == "PROFILE=unset STATUS=0"
    assert FREE_OPTION not in explicit_full
    # The explicit-full run takes exactly the pre-existing code path. The default run
    # asks the same questions with the same keystrokes; the only difference is the one
    # opt-in menu line and the widened choice list behind the same Hosting model prompt.
    index = default.index(FREE_OPTION)
    assert default[index - 1] == explicit_full[index - 1] and index == explicit_full.index(next(
        line for line in explicit_full if line.startswith("Hosting model [1]")))
    assert default[:index] + default[index + 1:-1] == explicit_full[:-1]


def test_noninteractive_default_never_selects_free(tmp_path):
    root = installer_copy(tmp_path)
    answers = root / "answers.json"
    answers.write_text(json.dumps({"schema_version": 1, "confirmed": True,
                                   "answers": {"ORG_NAME": "Example Org", "ADMINEMAIL": "owner@example.org"}}))
    answers.chmod(0o600)
    result = subprocess.run([BASH, "-c", '''set -euo pipefail
ROOT="$PWD"; source scripts/setup-questions.sh
load_noninteractive_answers answers.json
ask_setup_questions
echo "PROFILE=${SPACEWORKS_DEPLOYMENT_PROFILE:-unset}"'''], cwd=root, capture_output=True, text=True,
        env={k: v for k, v in os.environ.items() if k != "SPACEWORKS_DEPLOYMENT_PROFILE"}, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.rstrip().endswith("PROFILE=unset")
    assert "Deployment profile" not in result.stdout and "Free profile" not in result.stdout
    assert "FREE_TICK_SECRET" not in result.stdout


def test_interactive_opt_in_selects_free_and_skips_the_full_questionnaire(tmp_path):
    root = installer_copy(tmp_path)
    lines = drive(root, answers={"Hosting model": "4"})
    text = "\n".join(lines)
    assert lines[-1] == "PROFILE=free STATUS=0"
    assert "Website [" not in text and "Admin email" not in text and FREE_OPTION in text
    assert "Malware scanning is off" in text and "POST /api/v1/internal/free/tick" in text


def setup_free(root, *arguments, env=None):
    return subprocess.run([BASH, "setup.sh", *arguments], cwd=root, capture_output=True, text=True, timeout=60,
                          env={**{k: v for k, v in os.environ.items() if k != "SPACEWORKS_DEPLOYMENT_PROFILE"},
                               "PATH": os.environ["PATH"], **(env or {})})


def env_values(path):
    values = {}
    for line in path.read_text().splitlines():
        match = re.fullmatch(r"([A-Z][A-Z0-9_]*)='(.*)'", line)
        if match:
            values[match[1]] = match[2]
    return values


@pytest.mark.parametrize("selector", [("--profile", "free"), ("--profile=free",), ()])
def test_opt_in_free_generates_tick_secret_writes_env_and_notice(tmp_path, selector):
    root = installer_copy(tmp_path)
    env = {} if selector else {"SPACEWORKS_DEPLOYMENT_PROFILE": "free"}
    result = setup_free(root, *selector, "--non-interactive", env=env)
    assert result.returncode == 0, result.stderr
    values = env_values(root / ".env")
    assert (root / ".env").stat().st_mode & 0o777 == 0o600
    assert values["SPACEWORKS_DEPLOYMENT_PROFILE"] == "free" and values["SPACEWORKS_DEPLOYMENT_MODE"] == "managed"
    assert values["UPLOAD_SCAN_POLICY"] == "none" and values["CLOUD_SCHEDULER"] == "tick"
    assert re.fullmatch(r"[A-Za-z0-9]{48}", values["FREE_TICK_SECRET"])
    assert re.fullmatch(r"[A-Za-z0-9]{50}", values["SECRET_KEY"])
    for name in ("API_CLIENT_ENC_KEY", "AUDIT_MAC_MASTER_KEY", "PII_MASTER_KEY", "PII_SEARCH_HASH_KEY",
                 "ACCOUNT_PII_MASTER_KEY"):
        assert len(base64.urlsafe_b64decode(values[name])) == 32
    assert len({values[name] for name in ("API_CLIENT_ENC_KEY", "AUDIT_MAC_MASTER_KEY", "PII_MASTER_KEY",
                                          "PII_SEARCH_HASH_KEY", "ACCOUNT_PII_MASTER_KEY")}) == 5
    uuid.UUID(values["SPACEWORKS_DEPLOYMENT_ID"])
    output = result.stdout + result.stderr
    assert "Malware scanning is off" in output and "POST /api/v1/internal/free/tick" in output
    assert "X-Cron-Secret" in output and "Back up the private .env" in output
    assert values["FREE_TICK_SECRET"] not in output and values["SECRET_KEY"] not in output
    assert not (root / ".spaceworks-version").exists()
    # A rerun is an upgrade: every generated secret is kept byte for byte.
    before = (root / ".env").read_bytes()
    again = setup_free(root, "--profile", "free", "--non-interactive")
    assert again.returncode == 0, again.stderr
    assert "keeping your settings and secrets" in again.stdout
    assert (root / ".env").read_bytes() == before


def test_free_profile_never_overwrites_a_full_installation(tmp_path):
    root = installer_copy(tmp_path)
    (root / ".env").write_text("SECRET_KEY='existing-full-install'\n")
    result = setup_free(root, "--profile", "free", "--non-interactive")
    assert result.returncode != 0
    assert (root / ".env").read_text() == "SECRET_KEY='existing-full-install'\n"


@pytest.mark.parametrize("value", ["paid", "FREE", "managed"])
def test_unknown_profile_refuses_before_any_effect(tmp_path, value):
    root = installer_copy(tmp_path)
    result = setup_free(root, "--profile", value, "--non-interactive")
    assert result.returncode == 64 and not (root / ".env").exists()


def test_installer_entry_points_parse_the_opt_in_and_keep_full_default():
    install = (ROOT / "scripts/installer/install-entry.sh").read_text()
    assert "--profile) " in install and "--profile=*)" in install
    assert '"${SPACEWORKS_DEPLOYMENT_PROFILE:-full}"' in install
    for path in [ROOT / "install.sh", ROOT / "scripts/installer/standalone-install.sh", ROOT / "setup.sh", *(ROOT / "scripts/installer").glob("*.sh")]:
        # Nothing selects free implicitly or writes a tick secret outside the generator.
        assert "SPACEWORKS_DEPLOYMENT_PROFILE=free\n" not in path.read_text()
    generator = (ROOT / "scripts/setup-write-environment.sh").read_text()
    assert 'FREE_TICK_SECRET) value="$(rand_key 48)"' in generator


def continuity(root, function, env=None):
    return subprocess.run([BASH, "-c", f'''set -euo pipefail
ROOT="$PWD"; die() {{ echo "$*" >&2; exit 1; }}
source scripts/compose-deployment.sh
source scripts/setup-question-input.sh
source scripts/setup-write-environment.sh
{function}'''], cwd=root, capture_output=True, text=True, timeout=30,
        env={**os.environ, **(env or {})})


def test_fresh_install_generates_independent_continuity_keys_or_uses_supplied(tmp_path):
    root = installer_copy(tmp_path)
    (root / ".env").write_text("")
    result = continuity(root, "write_continuity_keys .env", {"ACCOUNT_PII_MASTER_KEY": base64.urlsafe_b64encode(b"r" * 32).decode()})
    assert result.returncode == 0, result.stderr
    values = env_values(root / ".env")
    assert values["ACCOUNT_PII_MASTER_KEY"] == base64.urlsafe_b64encode(b"r" * 32).decode()
    assert len(values["PUSH_TOKEN_HMAC_KEY"]) == 64
    assert len(base64.b64decode(values["EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY"], validate=True)) == 32
    keys = json.loads(values["EVENT_REGISTRATION_CREDENTIAL_KEYS"])
    assert list(keys) == ["1"] and len(base64.b64decode(keys["1"], validate=True)) == 32
    assert values["EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION"] == "1"


def test_upgrade_backfill_adds_only_undeclared_keys_once_and_never_replaces(tmp_path):
    root = installer_copy(tmp_path)
    original = "SECRET_KEY='kept'\nPUSH_TOKEN_HMAC_KEY='existing-push-key-material-000000000000'\nACCOUNT_PII_MASTER_KEY=\n"
    (root / ".env").write_text(original.rstrip("\n"))  # no trailing newline: appends must not merge
    result = continuity(root, "backfill_absent_continuity_keys")
    assert result.returncode == 0, result.stderr
    first = (root / ".env").read_text()
    values = env_values(root / ".env")
    assert first.startswith(original)
    assert values["PUSH_TOKEN_HMAC_KEY"] == "existing-push-key-material-000000000000"
    assert "ACCOUNT_PII_MASTER_KEY=\n" in first and first.count("ACCOUNT_PII_MASTER_KEY=") == 1
    assert "EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY" in values and "EVENT_REGISTRATION_CREDENTIAL_KEYS" in values
    again = continuity(root, "backfill_absent_continuity_keys")
    assert again.returncode == 0 and (root / ".env").read_text() == first


def test_upgrade_backfill_respects_external_account_key_broker(tmp_path):
    root = installer_copy(tmp_path)
    (root / ".env").write_text("ACCOUNT_PII_KEY_BROKER=aws_kms\n")
    assert continuity(root, "backfill_absent_continuity_keys").returncode == 0
    assert "ACCOUNT_PII_MASTER_KEY" not in (root / ".env").read_text()


@pytest.mark.skipif(not __import__("importlib").util.find_spec("cryptography"), reason="needs cryptography")
def test_cloud_wizard_generates_extra_keys_once_and_refuses_bad_recovery(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    from unittest.mock import patch
    from cloud_setup.errors import SetupError
    from cloud_setup.secrets import ensure_secrets, validate_secrets
    with patch("cloud_setup.secrets.age_identity"):
        first = ensure_secrets(tmp_path, {"version": 1, "values": {}}, free=True)
        second = ensure_secrets(tmp_path, {"version": 1, "values": {}}, free=True)
    assert first == second
    assert len(base64.urlsafe_b64decode(first["ACCOUNT_PII_MASTER_KEY"])) == 32
    assert len(base64.b64decode(first["EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY"], validate=True)) == 32
    assert first["EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION"] == "1" and len(first["PUSH_TOKEN_HMAC_KEY"]) >= 32
    with pytest.raises(SetupError):
        validate_secrets({"EVENT_REGISTRATION_CREDENTIAL_KEYS": '{"1":"not-a-key"}'})
    with pytest.raises(SetupError):
        validate_secrets({"ACCOUNT_PII_MASTER_KEY": "short"})
