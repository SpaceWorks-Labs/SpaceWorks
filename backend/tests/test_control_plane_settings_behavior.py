"""Drive the installed control-plane questionnaire through its real input validator."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(not BASH, reason="requires bash")


def write_script(path, source):
    path.write_text("#!/bin/bash\n" + source, encoding="utf-8", newline="\n")
    path.chmod(0o755)


@pytest.fixture
def questionnaire_installation(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("control-plane-settings.sh", "install-owner.sh", "compose-deployment.sh",
                 "setup-question-input.sh"):
        source = (ROOT / "scripts" / name).read_text()
        (scripts / name).write_text(source.replace("exec 3</dev/tty", "exec 3<&0"), newline="\n")
    library = tmp_path / "frontend/docker/control-plane-allowlist.sh"
    library.parent.mkdir(parents=True)
    library.write_text((ROOT / "frontend/docker/control-plane-allowlist.sh").read_text(), newline="\n")
    write_script(scripts / "apply-settings.sh", '''
printf '%s\\0' "$@" > apply-argv
printf '%s\\n' "$SPACEWORKS_UPDATE_INSTALL_DIR" > apply-root
[[ "$SPACEWORKS_UPDATE_INSTALL_DIR" == "$(cd "$(dirname "$0")/.." && pwd)" ]] || exit 91
exit 0
''')
    bins = tmp_path / "bin"
    bins.mkdir()
    write_script(bins / "docker", '''
case "$1" in
  info) [[ "${TEST_DOCKER_INFO_FAIL:-0}" != 1 ]] ;;
  version) echo "${TEST_ENGINE:-28.1.0}" ;;
  *) exit 92 ;;
esac
''')
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("SPACEWORKS_", "MAKERSPACE_", "CONTROL_PLANE_", "COMPOSE_"))
           and key != "STATIC_ENV"}
    env["PATH"] = os.pathsep.join((str(bins), str(Path(BASH).parent), os.environ["PATH"]))
    return tmp_path, env


def questionnaire(installation, answers, settings="", layer="none", https=False, frontend="yes", **changes):
    root, env = installation
    (root / ".env").write_text(
        f"SPACEWORKS_RUN_FRONTEND={frontend}\nENABLE_HTTPS={str(https).lower()}\n"
        "PUBLIC_APP_BASE_URL=http://tools.example.org\n" + settings, newline="\n")
    (root / ".spaceworks-layer").write_text(layer + "\n", newline="\n")
    return subprocess.run([BASH, "scripts/control-plane-settings.sh"], cwd=root,
                          env={**env, **changes}, input="\n".join(answers) + "\n",
                          capture_output=True, text=True, timeout=15)


def assert_applied(installation, result, expected):
    assert result.returncode == 0, result.stdout + result.stderr
    root, _ = installation
    assert (root / "apply-argv").read_bytes().split(b"\0") == [
        *(arg.encode() for arg in expected), b"",
    ]
    assert (root / "apply-root").exists()


def test_http_enable_warns_and_has_no_tunnel_question(questionnaire_installation):
    result = questionnaire(questionnaire_installation, ["y", "10.0.0.0/8", "y"],
                           "CONTROL_PLANE_PROXY='false'\n")
    assert_applied(questionnaire_installation, result,
                   ["--control-plane", "on", "--allow-cidrs", "10.0.0.0/8"])
    assert "over plain HTTP" in result.stdout
    assert "Loopback port for an SSH-tunnel fallback" not in result.stdout


def test_blank_cidrs_clear_previous_allowlist(questionnaire_installation):
    result = questionnaire(questionnaire_installation, ["y", "", "y"],
                           "CONTROL_PLANE_PROXY=true\nCONTROL_PLANE_ALLOW_CIDRS='10.0.0.0/8'\n")
    assert_applied(questionnaire_installation, result,
                   ["--control-plane", "on", "--allow-cidrs", ""])


def test_disable_omits_allowlist_argument(questionnaire_installation):
    result = questionnaire(questionnaire_installation, ["n", "y"],
                           "CONTROL_PLANE_PROXY=true\nCONTROL_PLANE_ALLOW_CIDRS='10.0.0.0/8'\n")
    assert_applied(questionnaire_installation, result, ["--control-plane", "off"])


@pytest.mark.parametrize("env_settings,answers", [
    ("CONTROL_PLANE_PROXY=false\n", [""]),
    ("CONTROL_PLANE_PROXY=true\nCONTROL_PLANE_ALLOW_CIDRS=10.0.0.0/8\n", ["", "10.0.0.0/8"]),
])
def test_unchanged_answers_do_not_apply(questionnaire_installation, env_settings, answers):
    result = questionnaire(questionnaire_installation, answers, env_settings)
    assert result.returncode == 0, result.stderr
    assert "No change; nothing applied." in result.stdout
    assert not (questionnaire_installation[0] / "apply-argv").exists()


def test_declining_confirmation_does_not_apply(questionnaire_installation):
    result = questionnaire(questionnaire_installation, ["y", "10.0.0.0/8", "n"])
    assert result.returncode == 0, result.stderr
    assert "Nothing changed." in result.stdout
    assert not (questionnaire_installation[0] / "apply-argv").exists()


def test_tls_reasks_reserved_custom_and_default_ports(questionnaire_installation):
    result = questionnaire(questionnaire_installation, ["y", "", "8080", "443", "8443", "y"],
                           "TLS_HTTP_PORT=8080\n", layer="tls")
    assert_applied(questionnaire_installation, result,
                   ["--control-plane", "on", "--allow-cidrs", "", "--tunnel-port", "8443"])
    assert result.stdout.count("That port is already used") == 2
    assert result.stdout.count("Loopback port for an SSH-tunnel fallback") == 3


@pytest.mark.parametrize("engine,expected_status", [("27.1.0", 64), ("28.1.0", 0)])
def test_tunnel_requires_docker_engine_28(questionnaire_installation, engine, expected_status):
    result = questionnaire(questionnaire_installation, ["y", "", "8443", "y"],
                           layer="tls", TEST_ENGINE=engine)
    assert result.returncode == expected_status, result.stderr
    if expected_status:
        assert "Docker Engine 28 or newer" in result.stderr
        assert not (questionnaire_installation[0] / "apply-argv").exists()
    else:
        assert_applied(questionnaire_installation, result,
                       ["--control-plane", "on", "--allow-cidrs", "", "--tunnel-port", "8443"])


def test_own_https_proxy_skips_allowlist_question_and_clears_it(questionnaire_installation):
    result = questionnaire(questionnaire_installation, ["y", "y"],
                           "CONTROL_PLANE_PROXY=false\nCONTROL_PLANE_ALLOW_CIDRS=10.0.0.0/8\n", https=True)
    assert_applied(questionnaire_installation, result,
                   ["--control-plane", "on", "--allow-cidrs", ""])
    assert "Allowed client IPs/CIDRs" not in result.stdout
    assert "Restrict /control/ in your own proxy instead." in result.stdout


@pytest.mark.parametrize("layer,api_only,changes,message", [
    ("saas", False, {}, "single-server installs only"),
    ("none", True, {}, "API-only"),
    ("none", False, {"TEST_DOCKER_INFO_FAIL": "1"}, "docker group"),
])
def test_preflight_refusals_never_apply(questionnaire_installation, layer, api_only, changes, message):
    root, _ = questionnaire_installation
    result = questionnaire(questionnaire_installation, [], layer=layer,
                           frontend="no" if api_only else "yes", **changes)
    assert result.returncode == 64, result.stderr
    assert message in result.stderr
    assert not (root / "apply-argv").exists()


def test_inherited_overrides_cannot_select_another_installation(questionnaire_installation, tmp_path):
    other = tmp_path / "other-install"
    other.mkdir()
    (other / ".env").write_text("CONTROL_PLANE_PROXY='true'\nCONTROL_PLANE_ALLOW_CIDRS=192.0.2.1\n")
    result = questionnaire(questionnaire_installation, ["y", "10.0.0.0/8", "y"],
                           "CONTROL_PLANE_PROXY='false'\n",
                           SPACEWORKS_STATIC_ENV_FILE=(other / ".env").as_posix(),
                           SPACEWORKS_UPDATE_INSTALL_DIR=other.as_posix())
    assert "Current website access: off" in result.stdout
    assert "Allowed addresses: any" in result.stdout
    assert "192.0.2.1" not in result.stdout
    assert_applied(questionnaire_installation, result,
                   ["--control-plane", "on", "--allow-cidrs", "10.0.0.0/8"])


def test_exported_current_setting_is_read_so_disabling_applies(questionnaire_installation):
    result = questionnaire(questionnaire_installation, ["n", "y"],
                           "export CONTROL_PLANE_PROXY='true'\n  CONTROL_PLANE_ALLOW_CIDRS=\"10.0.0.0/8\"\n")
    assert "Current website access: on" in result.stdout
    assert "Allowed addresses: 10.0.0.0/8" in result.stdout
    assert_applied(questionnaire_installation, result, ["--control-plane", "off"])
