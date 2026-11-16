"""#189 as revised by #191: who may reach /control/ at all (config.control_plane_access).

Proxy off (the default): the public origin gets a plain 404, the SSH tunnel and the server
itself reach the login page, and the superadmin-only checks behind it still refuse staff.
Proxy on: the website route behaves exactly as before.
"""

from pathlib import Path

import pytest
from django.conf import settings as django_settings
from django.test import Client

from apps.accounts.models import User
from tests.accounts.mfa_helpers import force_mfa_login
from tests.return_helpers import make_user

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parents[3]
PUBLIC_PEER = "203.0.113.9"
COMPOSE_PEER = "172.18.0.7"  # the Caddy container on the private Compose network
TUNNEL = {"HTTP_X_SPACEWORKS_CONTROL_TUNNEL": "1"}
CONTROL_PATHS = ("/control/", "/control/login/", "/control", "/mfa/control/", "/mfa/reauth/")


def superadmin(username="reach-root"):
    return make_user(username, role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE,
                     is_staff=True, is_superuser=True)


@pytest.fixture
def server_only(settings):
    settings.CONTROL_PLANE_PROXY = False
    settings.CONTROL_PLANE_TUNNEL = False
    return settings


@pytest.fixture
def tunnel(server_only):
    server_only.CONTROL_PLANE_TUNNEL = True
    return server_only


def test_the_default_is_server_only():
    """No environment means no website route: the shipped default is server-only."""
    from apps.backup.settings_policy import ENV_SURFACE

    assert {"CONTROL_PLANE_PROXY", "CONTROL_PLANE_TUNNEL"} <= ENV_SURFACE
    assert "config.control_plane_access.ControlPlaneReachMiddleware" in django_settings.MIDDLEWARE


@pytest.mark.parametrize("path", CONTROL_PATHS)
def test_public_origin_gets_404_not_a_login_page(server_only, path):
    response = Client(REMOTE_ADDR=PUBLIC_PEER).get(path)
    assert response.status_code == 404
    assert b"csrfmiddlewaretoken" not in response.content
    assert "sessionid" not in response.cookies


def test_a_superadmin_session_from_the_public_origin_is_still_404(server_only):
    client = Client(REMOTE_ADDR=PUBLIC_PEER)
    force_mfa_login(client, superadmin())
    assert client.get("/control/").status_code == 404


def test_a_loopback_hop_that_forwarded_someone_else_is_not_the_server(server_only):
    response = Client(REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR=PUBLIC_PEER).get("/control/login/")
    assert response.status_code == 404


def test_the_server_itself_reaches_the_login_page(server_only):
    response = Client(REMOTE_ADDR="127.0.0.1").get("/control/login/")
    assert response.status_code == 200 and b"csrfmiddlewaretoken" in response.content


def test_the_tunnel_stamp_is_ignored_without_the_tunnel_overlay(server_only):
    assert Client(REMOTE_ADDR=COMPOSE_PEER, **TUNNEL).get("/control/login/").status_code == 404


def test_the_tunnel_stamp_from_a_public_peer_is_ignored(tunnel):
    """An exposed backend cannot be talked into the tunnel by a client sending the header."""
    assert Client(REMOTE_ADDR=PUBLIC_PEER, **TUNNEL).get("/control/login/").status_code == 404


def test_a_private_peer_without_the_stamp_is_refused(tunnel):
    assert Client(REMOTE_ADDR=COMPOSE_PEER).get("/control/login/").status_code == 404


def test_the_tunnel_works_for_the_superadmin(tunnel):
    client = Client(REMOTE_ADDR=COMPOSE_PEER, **TUNNEL)
    assert client.get("/control/login/").status_code == 200
    force_mfa_login(client, superadmin())
    assert client.get("/control/").status_code == 200


def test_a_staff_account_through_the_tunnel_is_refused(tunnel):
    staff = make_user("reach-staff", is_staff=True)
    client = Client(REMOTE_ADDR=COMPOSE_PEER, **TUNNEL)
    client.force_login(staff)
    response = client.get("/control/")
    assert response.status_code == 403
    assert "_auth_user_id" not in client.session  # the stray admin session is flushed


def test_proxy_on_keeps_the_website_route_exactly_as_before(settings):
    settings.CONTROL_PLANE_PROXY = True
    client = Client(REMOTE_ADDR=PUBLIC_PEER)
    login = client.get("/control/login/")
    assert login.status_code == 200 and b"csrfmiddlewaretoken" in login.content
    force_mfa_login(client, superadmin("reach-proxy-root"))
    assert client.get("/control/").status_code == 200
    staff = Client(REMOTE_ADDR=PUBLIC_PEER)
    staff.force_login(make_user("reach-proxy-staff", is_staff=True))
    assert staff.get("/control/").status_code == 403


def test_other_routes_are_untouched(server_only):
    assert Client(REMOTE_ADDR=PUBLIC_PEER).get("/api/v1/health/").status_code != 404


def test_the_middleware_runs_before_sessions_and_logins():
    middleware = django_settings.MIDDLEWARE
    reach = middleware.index("config.control_plane_access.ControlPlaneReachMiddleware")
    assert middleware.index("config.request_id.RequestIdMiddleware") < reach
    assert reach < middleware.index("django.contrib.sessions.middleware.SessionMiddleware")
    assert reach < middleware.index("config.admin_access.AdminSuperuserOnlyMiddleware")


def test_the_edges_answer_404_and_only_the_tunnel_stamps():
    closed = (ROOT / "deploy/control-plane-false.caddy").read_text()
    assert "respond 404" in closed and "reverse_proxy" not in closed
    assert "header_up X-SpaceWorks-Control-Tunnel 1" in (ROOT / "deploy/control-tunnel-on.caddy").read_text()
    assert "header_up -X-SpaceWorks-Control-Tunnel" in (ROOT / "deploy/control-plane-true.caddy").read_text()
    nginx = (ROOT / "frontend/nginx.conf").read_text()
    include = nginx.index("include /etc/nginx/spaceworks.d/*.conf;")
    fallback = nginx.index("location ~ ^/(control(/|$)|mfa/(control|reauth)/) {")
    assert include < fallback and "return 404;" in nginx[fallback:fallback + 120]
    overlay = (ROOT / "docker/compose.control-tunnel.yml").read_text()
    assert overlay.count('CONTROL_PLANE_TUNNEL: "on"') == 2  # Caddy's listener and Django's trust


def test_the_settings_probe_accepts_the_website_404():
    script = (ROOT / "scripts/apply-settings.sh").read_text()
    assert "off:404) return 0 ;;" in script
