"""S-C: optional Cloudflare Turnstile (after failures, per-space always, fail mode, native exempt, CSP)."""

import os
import subprocess
from pathlib import Path

import httpx
import pytest
from rest_framework.test import APIClient

from apps.accounts import turnstile
from apps.accounts.models import IPAutoBlock
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.makerspaces.models_security import MakerspaceSecurityPolicy

pytestmark = pytest.mark.django_db
ORIGIN = "http://localhost:5000"


@pytest.fixture
def verdicts(monkeypatch):
    """What siteverify answers; each call is recorded."""
    state = {"body": {"success": True, "action": "login", "hostname": "localhost"}, "calls": [], "status": 200}

    def handler(request):
        state["calls"].append(request)
        if state["status"] is None:
            raise httpx.ConnectTimeout("slow", request=request)
        return httpx.Response(state["status"], json=state["body"])

    monkeypatch.setattr(turnstile, "_transport", lambda: httpx.MockTransport(handler))
    return state


@pytest.fixture(autouse=True)
def configured(settings, monkeypatch):
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(ScopedRateThrottle, "allow_request", lambda *args: True)
    settings.TURNSTILE_SITE_KEY, settings.TURNSTILE_SECRET_KEY = "site-key", "secret-key"
    settings.TURNSTILE_HOSTNAMES, settings.TURNSTILE_AFTER_FAILURES, settings.TURNSTILE_FAIL_MODE = [], 3, "open"
    settings.LOGIN_IP_BLOCK_DISTINCT_ACCOUNTS = 10


def login(username="alice", address="203.0.113.5", token=None, origin=ORIGIN, path="/api/v1/auth/login"):
    headers = {"REMOTE_ADDR": address}
    if origin:
        headers["HTTP_ORIGIN"] = origin
    if token:
        headers["HTTP_X_TURNSTILE_TOKEN"] = token
    return APIClient().post(path, {"username": username, "password": "wrong-pass-1"}, format="json", **headers)


def fail_three(username="alice", address="203.0.113.5"):
    for _ in range(3):
        assert login(username, address).status_code == 401


def test_required_after_three_failures_and_a_valid_token_passes(verdicts):
    fail_three()
    refused = login()
    assert refused.status_code == 400
    assert refused.json() == {"detail": "Complete the CAPTCHA to continue.", "code": "captcha_required",
                              "turnstile_site_key": "site-key", "turnstile_action": "login"}
    assert login(token="tok").status_code == 401
    sent = dict(httpx.QueryParams(verdicts["calls"][0].content.decode()))
    assert sent == {"secret": "secret-key", "response": "tok", "remoteip": "203.0.113.5"}


def test_per_account_failures_count_from_any_address(verdicts):
    for index in range(3):
        login("bob", address=f"198.51.100.{index + 1}")
    assert login("bob", address="198.51.100.200").json()["code"] == "captcha_required"
    assert login("carol", address="198.51.100.201").status_code == 401


@pytest.mark.parametrize("body", [
    {"success": False}, {"success": True, "action": "signup", "hostname": "localhost"},
    {"success": True, "action": "login", "hostname": "evil.example"},
])
def test_a_bad_token_action_or_hostname_fails_and_is_audited_once(verdicts, body):
    fail_three()
    verdicts["body"] = body
    assert login(token="bad").json()["code"] == "captcha_failed"
    assert login(token="bad").json()["code"] == "captcha_failed"
    assert AuditLog.objects.filter(action="auth.captcha_failed").count() == 1


@pytest.mark.parametrize("status", [None, 500])
def test_cloudflare_outage_follows_the_fail_mode(settings, verdicts, status):
    fail_three()
    verdicts["status"] = status
    assert login(token="tok").status_code == 401  # open: let through
    settings.TURNSTILE_FAIL_MODE = "closed"
    assert login(token="tok").json()["code"] == "captcha_failed"


def test_inactive_without_keys_outside_the_hostname_list_or_without_a_trusted_origin(settings, verdicts):
    fail_three()
    assert login(origin=None).status_code == 401
    assert login(origin="https://unknown.example").status_code == 401
    settings.TURNSTILE_HOSTNAMES = ["app.example"]
    assert login().status_code == 401
    settings.TURNSTILE_HOSTNAMES = ["localhost"]
    assert login().status_code == 400
    settings.TURNSTILE_SITE_KEY = settings.TURNSTILE_SECRET_KEY = ""
    assert login().status_code == 401
    assert verdicts["calls"] == []


def test_an_auto_blocked_address_gets_a_captcha_instead_of_a_429_but_native_does_not(settings, verdicts):
    settings.LOGIN_IP_BLOCK_DISTINCT_ACCOUNTS, settings.TURNSTILE_AFTER_FAILURES = 3, 20
    for name in ("n1", "n2", "n3"):
        login(name, address="203.0.113.77")
    assert IPAutoBlock.objects.exists()
    assert login("n4", address="203.0.113.77").json()["code"] == "captcha_required"
    assert login("n4", address="203.0.113.77", token="tok").status_code == 401
    native = APIClient().post("/api/v1/auth/device/login", {"username": "n4", "password": "x"}, format="json",
                              REMOTE_ADDR="203.0.113.77", HTTP_ORIGIN=ORIGIN)
    assert native.status_code == 429 and native.json()["code"] == "ip_blocked"


def test_a_space_set_to_always_asks_on_its_verified_domain_only(settings, verdicts):
    space = Makerspace.objects.create(name="Always", slug="always", frontend_domain="always.example",
                                      frontend_domain_status=Makerspace.DomainStatus.VERIFIED)
    row, _ = MakerspaceSecurityPolicy.objects.get_or_create(makerspace=space)
    MakerspaceSecurityPolicy.objects.filter(pk=row.pk).update(values={"security.captcha_on_sign_in": "always"})
    first = login(origin="https://always.example")
    assert first.json()["code"] == "captcha_required"
    assert login(origin=ORIGIN).status_code == 401  # the platform origin keeps the platform rule
    Makerspace.objects.filter(pk=space.pk).update(frontend_domain_status=Makerspace.DomainStatus.PENDING)
    assert login(origin="https://always.example").status_code == 401


def test_sign_up_reset_and_code_routes_use_their_own_actions(verdicts):
    fail_three("dana@example.com")
    signup = APIClient().post("/api/v1/auth/member-sign-up", {"display_name": "D", "email": "dana@example.com",
                              "password": "Some password 1!"}, format="json", REMOTE_ADDR="203.0.113.5",
                              HTTP_ORIGIN=ORIGIN)
    assert signup.json()["turnstile_action"] == "signup"
    forgot = APIClient().post("/api/v1/auth/forgot-password", {"email": "dana@example.com"}, format="json",
                              REMOTE_ADDR="203.0.113.5", HTTP_ORIGIN=ORIGIN)
    assert forgot.json()["turnstile_action"] == "reset"


def test_config_exposes_the_site_key_only_when_configured(settings):
    assert APIClient().get("/api/v1/config").json()["turnstile_site_key"] == "site-key"
    settings.TURNSTILE_SITE_KEY = settings.TURNSTILE_SECRET_KEY = ""
    assert "turnstile_site_key" not in APIClient().get("/api/v1/config").json()


SCRIPT = Path(__file__).resolve().parents[3] / "frontend" / "docker-entrypoint.d" / "40-web-analytics.sh"


@pytest.mark.skipif(not SCRIPT.exists(), reason="frontend tree not mounted")
@pytest.mark.parametrize("site_key", ["", "0x4AAAAAAA"])
def test_csp_adds_cloudflare_only_when_configured(tmp_path, site_key):
    env = {**os.environ, "WEB_ANALYTICS_SCRIPT_URL": "https://plausible.example/js/script.manual.js",
           "WEB_ANALYTICS_COLLECT_URL": "https://plausible.example/api/event", "WEB_ANALYTICS_DOMAIN": "app.example",
           "WEB_ANALYTICS_HEADERS_PATH": str(tmp_path / "h.conf"), "TENANT_CONFIG_PATH": str(tmp_path / "c.js"),
           "TURNSTILE_SITE_KEY": site_key}
    subprocess.run(["sh", str(SCRIPT)], env=env, check=True)
    headers = (tmp_path / "h.conf").read_text()
    assert ("https://challenges.cloudflare.com" in headers) is bool(site_key)
