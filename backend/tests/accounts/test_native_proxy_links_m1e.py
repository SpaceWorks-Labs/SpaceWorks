"""Independent destination fixtures and exact public application proxy routing."""

from pathlib import Path
import re

import pytest

from apps.integrations.mobile_link_contract import is_supported_link
from apps.notifications.inbox import InboxDelivery, safe_link

ROOT = Path(__file__).resolve().parents[3]
ROUTES = ("/.well-known/assetlinks.json", "/.well-known/apple-app-site-association")
# Keep examples independent of DESTINATIONS, so dropping a contract entry fails.
DESTINATION_FIXTURES = (
    "/member", "/member/loans", "/member/account", "/member/events/42/ticket",
    "/events/161cd831-baaa-49e6-a911-733dce0addda",
    "/bookings/d0165a92-b753-4351-ab0a-b4a5a5ca81e1", "/items/17",
)


@pytest.mark.parametrize("local_path", DESTINATION_FIXTURES)
@pytest.mark.parametrize("prefix", ["", "/m/workshop"])
@pytest.mark.parametrize("suffix", ["", "/"])
def test_link_contract_accepts_every_documented_destination(local_path, prefix, suffix):
    assert is_supported_link(prefix + local_path + suffix)


@pytest.fixture
def member_push_links():
    # The inbox supplies phase-1b push link values. Include the generated event-ticket
    # shape and both shared-host and custom-domain forms, not only member home.
    return [InboxDelivery(user_id=1, title="Member update", summary="Update", link=prefix + path)
            for prefix in ("", "/m/workshop") for path in DESTINATION_FIXTURES]


def test_member_push_link_fixtures_remain_inside_the_app_contract(member_push_links):
    for delivery in member_push_links:
        link = safe_link(delivery.link)
        assert link == delivery.link
        assert is_supported_link(link)


@pytest.mark.parametrize("path", [
    "/m/workshop/admin", "/m/workshop/admin/", "/m/workshop/admin/inventory",
    "/m/workshop/admin/notifications", "/control", "/control/", "/control/accounts/user/",
    "/admin/inventory", "/api/v1/config", "/docs/", "/redoc/", "/schema/",
    "/", "/m/workshop", "/m/workshop/public", "/member/events/42",
    "//evil.example/member", "https://evil.example/member", "/member?tab=loans",
    "/member#account", "/member\\account", "/member/loans\n", None,
])
def test_staff_control_and_unlisted_links_are_outside_the_app_contract(path):
    assert not is_supported_link(path)


def test_safe_browser_staff_link_still_requires_native_inbox_fallback():
    link = safe_link("/m/workshop/admin/notifications")
    assert link  # Browser-safe does not imply the native app claims this destination.
    assert not is_supported_link(link)


def block(config, header):
    """Extract one braced block; placeholders contain balanced braces too."""
    start = config.index(header + " {") + len(header) + 1
    depth = 0
    for position in range(start, len(config)):
        if config[position] == "{":
            depth += 1
        elif config[position] == "}":
            depth -= 1
            if depth == 0:
                return config[start + 1:position]
    raise AssertionError(f"Unclosed block: {header}")


@pytest.mark.parametrize("relative", ["frontend/nginx.conf", "deploy/nginx.api-only.conf"])
def test_nginx_association_routes_are_exact_backend_locations_inside_application_server(relative):
    config = (ROOT / relative).read_text(encoding="utf-8")
    application = block(config, "server")
    for path in ROUTES:
        assert config.count(f"location = {path} {{") == 1
        location = block(application, f"location = {path}")
        assert "proxy_pass http://backend:8000;" in location
        assert "proxy_set_header Host $host;" in location
    assert not re.search(r"location\s+(?:\^~\s+)?/\.well-known/", config)


def publishing_lines(config):
    """Caddy text minus `not path` exclusion lists.

    Matchers such as the profile-card crawler reserve `/.well-known/*` so it is
    never rewritten; an exclusion cannot publish anything, every other mention can.
    """
    return "\n".join(line for line in config.splitlines() if not line.strip().startswith("not path "))


@pytest.mark.parametrize("relative,header,public_sites", [
    ("deploy/Caddyfile", "{$PUBLIC_DOMAIN}", ()),
    ("deploy/Caddyfile.saas", "(backend_paths)",
     ("*.space-works.tech, space-works.tech", "https://")),
    ("deploy/Caddyfile.saas-install", "(application)",
     ("{$PLATFORM_DOMAIN}, {$PLATFORM_FIRST_HOST}, {$PLATFORM_ORIGIN_HOST}", "https://")),
])
def test_caddy_exact_routes_are_in_the_public_application_block(relative, header, public_sites):
    config = (ROOT / relative).read_text(encoding="utf-8")
    application = block(config, header)
    for path in ROUTES:
        assert config.count(f"handle {path} {{") == 1
        assert "reverse_proxy backend:8000" in block(application, f"handle {path}")
    assert "/.well-known/*" not in publishing_lines(config)
    for site in public_sites:
        assert f"import {header.strip('()')}" in block(config, site)


def test_control_plane_and_tunnel_snippets_never_publish_association_routes():
    snippets = [*(ROOT / "deploy").glob("control-plane-*.caddy"),
                *(ROOT / "deploy").glob("control-tunnel-*.caddy")]
    assert len(snippets) >= 4  # A moved/deleted snippet must not turn this into an empty pass.
    for path in snippets:
        assert "/.well-known/" not in path.read_text(encoding="utf-8"), path
