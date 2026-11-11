"""Run the image's real POSIX validators and snippet generator without nginx."""
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
SH = shutil.which("sh")
pytestmark = pytest.mark.skipif(not SH, reason="requires sh")

VALID_CIDRS = [
    "10.0.0.0/8", "192.168.1.5", "0.0.0.0/0", "::/0", "::1",
    "2001:db8::/32", "fe80::1", "1:2:3:4:5:6:7:8", "1::8", "::ffff",
    "::", "255.255.255.255/32", "2001:DB8::1/128",
]
INVALID_CIDRS = [
    "256.1.1.1", "01.2.3.4", "10.0.0.0/33", "10.0.0.0/08", "1:2:3",
    "12345::", "1:2:3:4:5:6:7:8:9", "1::2::3", ":::",
    "1:2:3:4:5:6:7::8:9", "::ffff:1.2.3.4",
    "fe80::1%eth0", "2001:db8::/129", "a,b", "", ":1", "1:", "1.2.3",
    "1.2.3.4/", "::1/01", "10.0.0.0/8/9", "10.0.0.1;deny all;",
]


@pytest.fixture
def nginx_scripts(tmp_path):
    for relative in ("frontend/docker/control-plane-allowlist.sh",
                     "frontend/docker-entrypoint.d/40-control-plane.sh"):
        target = tmp_path / Path(relative).name
        target.write_text((ROOT / relative).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    return tmp_path


def validate(directory, function, value):
    return subprocess.run(
        [SH, "-c", '. ./control-plane-allowlist.sh; "$1" "$2"', "validate", function, value],
        cwd=directory, capture_output=True, text=True, timeout=10,
    )


def test_sourcing_library_has_no_side_effects(nginx_scripts):
    before = set(nginx_scripts.iterdir())
    result = subprocess.run(
        [SH, "-c", 'set -eu; flags="$-"; . ./control-plane-allowlist.sh; '
         '[ "$flags" = "$-" ]; printf sourced'], cwd=nginx_scripts,
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "sourced" and result.stderr == ""
    assert set(nginx_scripts.iterdir()) == before


@pytest.mark.parametrize("value", VALID_CIDRS)
def test_accepts_addresses_and_cidrs(nginx_scripts, value):
    result = validate(nginx_scripts, "cp_valid_cidr", value)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("value", INVALID_CIDRS)
def test_rejects_invalid_addresses_and_cidrs(nginx_scripts, value):
    assert validate(nginx_scripts, "cp_valid_cidr", value).returncode != 0


@pytest.mark.parametrize("value,valid", [
    ("1", True), ("8080", True), ("65535", True), ("0", False), ("08080", False),
    ("65536", False), ("123456", False), ("", False), ("-1", False), ("8;exit 0", False),
])
def test_port_boundaries(nginx_scripts, value, valid):
    assert (validate(nginx_scripts, "cp_valid_port", value).returncode == 0) == valid


@pytest.mark.parametrize("value,valid", [
    ("10.0.0.0/8 ::1", True), (" ".join(["::1"] * 32), True),
    (" ".join(["::1"] * 33), False), ("", False), (" ::1", False), ("::1 ", False),
    ("::1  ::2", False), ("::1\t::2", False), ("::1\n::2", False),
    ("::1 256.0.0.1", False),
    # 25 valid long IPv6 entries fit the count limit but exceed 1024 characters.
    (" ".join(["ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff/128"] * 25), False),
])
def test_list_format_and_limits(nginx_scripts, value, valid):
    assert (validate(nginx_scripts, "cp_valid_cidr_list", value).returncode == 0) == valid


def generate(directory, **settings):
    environment = {key: value for key, value in os.environ.items() if not key.startswith("CONTROL_PLANE_")}
    return subprocess.run(
        [SH, "40-control-plane.sh"], cwd=directory,
        env={**environment, "CONTROL_PLANE_LIB": (directory / "control-plane-allowlist.sh").as_posix(),
             "CONTROL_PLANE_SNIPPET": (directory / "snippets/control-plane.conf").as_posix(), **settings},
        capture_output=True, text=True, timeout=10,
    )


@pytest.mark.parametrize("env_settings", [{}, {"CONTROL_PLANE_PROXY": "false"}])
def test_off_removes_stale_snippet_without_loading_library(nginx_scripts, env_settings):
    snippet = nginx_scripts / "snippets/control-plane.conf"
    snippet.parent.mkdir()
    snippet.write_text("stale route", newline="\n")
    result = generate(nginx_scripts, CONTROL_PLANE_LIB="/missing-library", **env_settings)
    assert result.returncode == 0, result.stderr
    assert not snippet.exists()
    assert generate(nginx_scripts, **env_settings).returncode == 0


@pytest.mark.parametrize("env_settings,upstream,proto", [
    ({}, "http://backend:8000", "$external_scheme"),
    ({"CONTROL_PLANE_UPSTREAM": "http://127.0.0.1:8000", "CONTROL_PLANE_PROTO": "$scheme"},
     "http://127.0.0.1:8000", "$scheme"),
])
def test_on_preserves_request_host_port_and_path(nginx_scripts, env_settings, upstream, proto):
    result = generate(nginx_scripts, CONTROL_PLANE_PROXY="true", **env_settings)
    assert result.returncode == 0, result.stderr
    snippet = (nginx_scripts / "snippets/control-plane.conf").read_text()
    assert f"proxy_pass {upstream};" in snippet  # No URI part: keep the incoming path.
    assert "proxy_set_header Host $http_host;" in snippet
    assert "proxy_set_header X-Real-IP $remote_addr;" in snippet
    assert "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;" in snippet
    assert f"proxy_set_header X-Forwarded-Proto {proto};" in snippet
    assert not re.search(r"\b(allow|deny|real_ip_header|set_real_ip_from)\b", snippet)
    pattern = re.search(r"location ~ (\S+) \{", snippet)[1]
    for path in ("/control", "/control/", "/control/login/", "/mfa/control/", "/mfa/control/verify", "/mfa/reauth/"):
        assert re.search(pattern, path), path
    for path in ("/controller", "/control-other/", "/mfa/control", "/mfa/reauthx/", "/api/", "/"):
        assert not re.search(pattern, path), path
    assert list((nginx_scripts / "snippets").iterdir()) == [nginx_scripts / "snippets/control-plane.conf"]


def test_cidrs_generate_ordered_socket_peer_rules_and_replace_stale_file(nginx_scripts):
    assert generate(nginx_scripts, CONTROL_PLANE_PROXY="true").returncode == 0
    result = generate(nginx_scripts, CONTROL_PLANE_PROXY="true", CONTROL_PLANE_ALLOW_CIDRS="10.0.0.0/8 ::1")
    assert result.returncode == 0, result.stderr
    snippet = (nginx_scripts / "snippets/control-plane.conf").read_text()
    rules = [line.strip() for line in snippet.splitlines() if line.strip().startswith(("allow ", "deny "))]
    assert rules == ["allow 10.0.0.0/8;", "allow ::1;", "deny all;"]
    assert "real_ip_header" not in snippet and "set_real_ip_from" not in snippet
    assert generate(nginx_scripts, CONTROL_PLANE_PROXY="true").returncode == 0
    assert "deny all;" not in (nginx_scripts / "snippets/control-plane.conf").read_text()


@pytest.mark.parametrize("env_settings", [
    {"CONTROL_PLANE_PROXY": value} for value in ("", "TRUE", "yes", "1")
] + [
    {"CONTROL_PLANE_ALLOW_CIDRS": value} for value in ("01.2.3.4", "::1  ::2", "::1; deny all;")
] + [
    {"CONTROL_PLANE_UPSTREAM": value} for value in
    ("https://backend:8000", "http://backend", "http://backend:8000/", "http://user@backend:8000", "http://backend:8000;}")
] + [
    {"CONTROL_PLANE_PROTO": value} for value in ("https", "", "$http_x_forwarded_proto", "$scheme;}")
])
def test_invalid_configuration_fails_without_replacing_snippet(nginx_scripts, env_settings):
    snippet = nginx_scripts / "snippets/control-plane.conf"
    snippet.parent.mkdir()
    snippet.write_text("existing config\n", newline="\n")
    result = generate(nginx_scripts, **{"CONTROL_PLANE_PROXY": "true", **env_settings})
    assert result.returncode == 1
    assert "Invalid control-plane config" in result.stderr
    assert snippet.read_text() == "existing config\n"
    assert list(snippet.parent.iterdir()) == [snippet]
