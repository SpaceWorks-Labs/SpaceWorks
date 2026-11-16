"""Control-plane HTTPS/CSRF contract and deployment configuration drift guards."""
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
APPLICATION_SERVICES = {
    "orchestration-init", "migrate", "orchestration-ready", "backend", "live", "worker",
    "beat", "frontend", "api-edge", "candidate-backend", "cron",
}  # The single-box "app" service was removed with its all-in-one image.
INFRASTRUCTURE_SERVICES = {"db", "redis", "minio", "createbuckets", "caddy"}


def compose(relative):
    import yaml

    class ComposeLoader(yaml.SafeLoader):
        pass

    for tag in ("!reset", "!override"):
        ComposeLoader.add_constructor(tag, lambda loader, node: loader.construct_sequence(node)
                                     if isinstance(node, yaml.SequenceNode)
                                     else loader.construct_mapping(node) if isinstance(node, yaml.MappingNode)
                                     else None)  # `!reset null` (compose.no-redis.yml) is a scalar
    return yaml.load((ROOT / relative).read_text(encoding="utf-8"), Loader=ComposeLoader)


@pytest.fixture
def secure_proxy_settings():
    from django.test import override_settings

    with override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
        SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True,
        ALLOWED_HOSTS=["localhost", "testserver"], CSRF_TRUSTED_ORIGINS=[],
        PLATFORM_ADMIN_SSO=False,
    ):
        yield


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/control/login/", "/mfa/control/"])
def test_plain_http_control_paths_redirect_to_https(secure_proxy_settings, path):
    from django.test import Client

    response = Client().get(path, HTTP_HOST="localhost:8443")
    assert response.status_code == 301
    assert response.url == f"https://localhost:8443{path}"


@pytest.mark.django_db
def test_forwarded_https_login_preserves_host_port_for_csrf(secure_proxy_settings):
    from django.conf import settings
    from django.test import Client

    client = Client(enforce_csrf_checks=True)
    headers = {"HTTP_HOST": "localhost:8443", "HTTP_X_FORWARDED_PROTO": "https"}
    login = client.get("/control/login/", **headers)
    assert login.status_code == 200
    assert b"csrfmiddlewaretoken" in login.content
    assert client.cookies[settings.CSRF_COOKIE_NAME]["secure"]
    token = client.cookies[settings.CSRF_COOKIE_NAME].value
    # Empty credentials exercise form validation without creating an authenticated session.
    data = {"username": "", "password": "", "csrfmiddlewaretoken": token}
    same_origin = client.post("/control/login/", data, HTTP_ORIGIN="https://localhost:8443", **headers)
    assert same_origin.status_code == 200
    wrong_port = client.post("/control/login/", data, HTTP_ORIGIN="https://localhost:9443", **headers)
    assert wrong_port.status_code == 403
    missing_token = client.post("/control/login/", {"username": "", "password": ""},
                                HTTP_ORIGIN="https://localhost:8443", **headers)
    assert missing_token.status_code == 403


def caddy_code(name):
    return "\n".join(line.split("#", 1)[0].strip()
                     for line in (ROOT / "deploy" / name).read_text().splitlines()).strip()


def test_caddy_opt_in_wiring_and_socket_peer_allowlist():
    main = caddy_code("Caddyfile")
    public_import = "import /etc/caddy/control-plane-{$CONTROL_PLANE_PROXY:false}.caddy"
    tunnel_import = "import /etc/caddy/control-tunnel-{$CONTROL_PLANE_TUNNEL:off}.caddy"
    assert "skip_install_trust" in main
    assert main.index("import {$STORAGE_CADDY_CONFIG:") < main.index(tunnel_import) < main.index("{$PUBLIC_DOMAIN} {")
    assert main.index("handle /api/v1/live/*") < main.index(public_import) < main.index("@backend path")
    # #189/#191: with the route off the website answers 404 itself, never the SPA.
    closed = caddy_code("control-plane-false.caddy")
    assert "@control_plane path /control /control/* /mfa/control/* /mfa/reauth /mfa/reauth/*" in closed
    assert "respond 404" in closed and "reverse_proxy" not in closed
    assert caddy_code("control-tunnel-off.caddy") == ""
    public = caddy_code("control-plane-true.caddy")
    assert "@control_plane path /control /control/* /mfa/control/* /mfa/reauth /mfa/reauth/*" in public
    assert "header_up -X-SpaceWorks-Control-Tunnel" in public
    assert "@control_plane_denied not remote_ip {$CONTROL_PLANE_ALLOW_CIDRS}" in public
    assert public.index("respond @control_plane_denied 403") < public.index("reverse_proxy backend:8000")
    tunnel = caddy_code("control-tunnel-on.caddy")
    assert "https://localhost:9443 {" in tunnel and "tls internal" in tunnel
    assert "@control_plane path /control /control/* /mfa/control/* /mfa/reauth /mfa/reauth/* /static/*" in tunnel
    assert "header_up X-SpaceWorks-Control-Tunnel 1" in tunnel
    assert "respond 404" in tunnel
    assert "header_down -Strict-Transport-Security" in tunnel
    for route in (public, tunnel):
        assert "header_up X-Forwarded-Proto https" in route
        assert not re.search(r"header_up\s+(?:Host|X-Forwarded-Host)\b", route, re.I)
        assert "trusted_proxies" not in route and "X-Forwarded-For" not in route
    assert "trusted_proxies" not in main


def test_compose_tls_defaults_readonly_mounts_and_loopback_tunnel():
    caddy = compose("docker/compose.tls.yml")["services"]["caddy"]
    assert caddy["environment"]["CONTROL_PLANE_PROXY"] == "${CONTROL_PLANE_PROXY:-false}"
    assert caddy["environment"]["CONTROL_PLANE_ALLOW_CIDRS"] == "${CONTROL_PLANE_ALLOW_CIDRS:-0.0.0.0/0 ::/0}"
    assert "CONTROL_PLANE_TUNNEL" not in caddy["environment"]
    for name in ("control-plane-false", "control-plane-true", "control-tunnel-off", "control-tunnel-on"):
        assert f"./deploy/{name}.caddy:/etc/caddy/{name}.caddy:ro" in caddy["volumes"]
    tunnel = compose("docker/compose.control-tunnel.yml")["services"]
    # #189/#191: the overlay also tells Django to believe the tunnel listener's stamp.
    assert set(tunnel) == {"caddy", "backend"}
    assert tunnel["caddy"]["environment"] == {"CONTROL_PLANE_TUNNEL": "on"}
    assert tunnel["backend"] == {"environment": {"CONTROL_PLANE_TUNNEL": "on"}}
    assert tunnel["caddy"]["ports"] == ["127.0.0.1:${CONTROL_PLANE_TUNNEL_PORT:?set CONTROL_PLANE_TUNNEL_PORT}:9443"]
    services = compose("docker-compose.prod.yml")["services"]
    for service in ("frontend",):
        assert services[service]["environment"]["CONTROL_PLANE_PROXY"] == "${CONTROL_PLANE_PROXY:-false}"
        assert services[service]["environment"]["CONTROL_PLANE_ALLOW_CIDRS"] == "${CONTROL_PLANE_ALLOW_CIDRS:-}"
    # #189/#191: Django's reach check reads the proxy switch (and only that one).
    for service in ("backend", "worker", "beat", "live", "migrate"):
        keys = {key for key in services[service]["environment"] if key.startswith("CONTROL_PLANE_")}
        assert keys == {"CONTROL_PLANE_PROXY"}
        assert services[service]["environment"]["CONTROL_PLANE_PROXY"] == "${CONTROL_PLANE_PROXY:-false}"


def test_application_image_construction_covers_all_release_services():
    assert APPLICATION_SERVICES.isdisjoint(INFRASTRUCTURE_SERVICES)
    files = [ROOT / "docker-compose.prod.yml", ROOT / "docker-compose.cloud.yml"]
    files += sorted(path for path in (ROOT / "docker").glob("compose.*.yml") if path.name != "compose.build.yml")
    seen = set()
    pattern = re.compile(
        r"\$\{MAKERSPACE_(?:BACKEND|FRONTEND)_IMAGE(?::-[^${}]+)?\}"
        r":\$\{MAKERSPACE_IMAGE_TAG(?::-[^${}]+)?\}"
    )
    for path in files:
        for service, config in compose(path.relative_to(ROOT))["services"].items():
            assert service in APPLICATION_SERVICES | INFRASTRUCTURE_SERVICES, (path, service)
            seen.add(service)
            if service in APPLICATION_SERVICES and "image" in config:
                image = config["image"]
                assert pattern.fullmatch(image) or ("$" not in image and bool(image.strip())), (path, service, image)
    assert seen == APPLICATION_SERVICES | INFRASTRUCTURE_SERVICES


@pytest.mark.skipif(not BASH, reason="requires bash")
def test_host_bundle_installs_every_selected_overlay_and_bind_mount(tmp_path):
    # Exercise the bundle installer, rather than matching its private files array.
    script = tmp_path / "install-host-bundle.sh"
    script.write_text((ROOT / "scripts/install-host-bundle.sh").read_text(), newline="\n")
    # install_staged_host_bundle sources installer/bundle-transaction.sh beside itself (5f5b3a93).
    (tmp_path / "installer").mkdir()
    (tmp_path / "installer" / "bundle-transaction.sh").write_text(
        (ROOT / "scripts/installer/bundle-transaction.sh").read_text(), newline="\n")
    target = tmp_path / "installed"
    result = subprocess.run(
        [BASH, "-c", 'set -euo pipefail; ROOT="$1"; say() { :; }; die() { echo "$*" >&2; exit 1; }; '
         'source ./install-host-bundle.sh; install_staged_host_bundle "$2"', "bundle", target.as_posix(), ROOT.as_posix()],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    required = {"docker-compose.prod.yml", "docker-compose.cloud.yml", "deploy/Caddyfile.saas",
                "deploy/Caddyfile.saas-install", "scripts/apply-settings.sh",
                "frontend/docker/control-plane-allowlist.sh", "frontend/docker-entrypoint.d/40-control-plane.sh"}
    for path in (ROOT / "docker").glob("compose.*.yml"):
        required.add(path.relative_to(ROOT).as_posix())
        for config in compose(path.relative_to(ROOT))["services"].values():
            for volume in config.get("volumes", []):
                # ./storage-config is written per install by the setup questions, not shipped in the bundle.
                if isinstance(volume, str) and volume.startswith("./") and not volume.startswith("./storage-config"):
                    required.add(volume.split(":", 1)[0][2:])
    for relative in required:
        assert (target / relative).read_bytes() == (ROOT / relative).read_bytes(), relative
