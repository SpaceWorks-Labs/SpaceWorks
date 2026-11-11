"""Removed deployment layers fail before host effects; own-proxy output stays usable."""
import os
import shutil
import subprocess

import pytest

from tests.test_host_updater_behavior import BASH, ROOT, host, write_script  # noqa: F401
from tests.test_host_compose_wrapper_behavior import run_wrapper, wrapper  # noqa: F401

pytestmark = pytest.mark.skipif(not BASH, reason="requires bash")


def assert_switch_steps(result):
    assert result.returncode == 64, result.stderr
    assert "CURRENTLY INSTALLED scripts, then retry" in result.stderr
    for step in ("bundled stop app", "bundled rm -f app", "printf 'none\\n' > .spaceworks-layer", "bundled up -d"):
        assert step in result.stderr


@pytest.mark.parametrize("layer", ["single", "none"])
def test_compose_refuses_retired_layer_and_preserves_standard_layer(wrapper, layer):
    root, _ = wrapper
    (root / "installed/.spaceworks-layer").write_text(layer + "\n")
    result = run_wrapper(wrapper, SPACEWORKS_COMPOSE_LAYER="", TEST_PYTHON_AVAILABLE="0")
    if layer == "single":
        assert_switch_steps(result)
        assert not (root / "order").exists()  # Neither Docker validation nor compose ran.
        assert not (root / "compose-args").exists()
    else:
        assert result.returncode == 0, result.stderr
        assert (root / "order").read_text().splitlines() == ["run", "compose"]
        assert "compose.single.yml" not in (root / "compose-args").read_text()


def test_setup_refuses_persisted_single_layer_without_changing_environment(host):
    root, environment = host
    shutil.copy(ROOT / "setup.sh", root / "setup.sh")
    (root / ".spaceworks-layer").write_text("single\n")
    original = (root / ".env").read_bytes()
    result = subprocess.run([BASH, "setup.sh"], cwd=root, env=environment,
                            text=True, capture_output=True, timeout=30)
    assert_switch_steps(result)
    assert (root / ".env").read_bytes() == original
    assert not (root / "docker.log").exists()
    assert not (root / "compose.log").exists()


@pytest.mark.parametrize("storage", ["1", "2"], ids=["bundled", "external"])
def test_generated_proxy_routes_and_certificate_steps(tmp_path, storage):
    result = subprocess.run([BASH, "-c", '''set -euo pipefail
source "$PROXY_HELPER"
write_proxy_nginx_config
print_proxy_nginx_steps
'''], env={**os.environ, "ROOT": tmp_path.as_posix(), "WEBHOST": "api.example.org",
           "STORAGE": storage, "PROXY_HELPER": (ROOT / "scripts/setup-proxy-config.sh").as_posix()},
        text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    source = (tmp_path / "spaceworks-proxy.nginx.conf").read_text()
    assert "server_name api.example.org;" in source
    assert "proxy_pass http://127.0.0.1:8080;" in source
    live = source.split("location /api/v1/live/ {", 1)[1].split("}", 1)[0]
    assert "proxy_buffering off;" in live
    feed = source.split("location ~ ", 1)[1].split("}", 1)[0]
    assert "maintenance/feed" in feed and r"\.ics$" in feed
    assert "access_log off;" in feed and "error_log /dev/null;" in feed
    assert ("server_name files.api.example.org;" in source) == (storage == "1")
    assert ("proxy_pass http://127.0.0.1:9000;" in source) == (storage == "1")
    assert "@DOMAIN@" not in source and "@SERVER_NAMES@" not in source
    imports = source.split("location = /api/v1/admin/platform/tenant-migrations/imports {", 1)[1].split("}", 1)[0]
    assert "client_max_body_size 20g;" in imports and "proxy_request_buffering" not in imports  # Gunicorn sync workers time out on slow streams.
    assert "certbot certonly --nginx --cert-name api.example.org -d api.example.org" in result.stdout
    assert ("-d files.api.example.org" in result.stdout) == (storage == "1")


def test_release_image_verification_pulls_only_backend_and_frontend(host):
    root, environment = host
    # The shared host fixture's docker stub does not log; record pulls here.
    write_script(root / "bin/docker", 'printf "%s\\n" "$*" >> "$TEST_DOCKER_LOG"\nexit 0\n')
    result = subprocess.run([BASH, (ROOT / "scripts/verify-release-images.sh").as_posix(), "fixture-tag"],
                            cwd=root, env={**environment, "GHCR_OWNER": "spaceworks-labs",
                                           "TEST_DOCKER_LOG": (root / "docker.log").as_posix()},
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    # Each published image is verified for both release platforms.
    assert (root / "docker.log").read_text().splitlines() == [
        f"pull --platform {platform} ghcr.io/spaceworks-labs/spaceworks-{image}:fixture-tag"
        for image in ("backend", "frontend") for platform in ("linux/amd64", "linux/arm64")
    ]


@pytest.mark.parametrize("relative", ["frontend/nginx.conf", "deploy/nginx.api-only.conf"])
def test_bundled_edges_allow_bulk_import_and_tenant_archive_bodies(relative):
    source = (ROOT / relative).read_text()
    imports = source.split("location = /api/v1/admin/platform/tenant-migrations/imports {", 1)[1].split("}", 1)[0]
    assert "client_max_body_size 20g;" in imports and "proxy_request_buffering" not in imports  # Gunicorn sync workers time out on slow streams.
    api = source.split("location /api/ {" if "location /api/ {" in source else "location ~ ^/(api", 1)[1]
    assert "client_max_body_size 10m;" in api.split("}", 1)[0]
