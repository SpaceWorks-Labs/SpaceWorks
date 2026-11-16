"""S-C: automatic IP blocking against credential stuffing (#62, Q12, #157)."""

from datetime import timedelta

import pytest
from django.core import signing
from django.test import RequestFactory, override_settings
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework.test import APIClient

from apps.accounts import ip_guard
from apps.accounts.models import IPAccessRule, IPAutoBlock, KnownDevice, User
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db
ORIGIN = "http://localhost:5000"
ATTACKER = "203.0.113.5"


@pytest.fixture(autouse=True)
def small_threshold(settings, monkeypatch):
    from rest_framework.throttling import ScopedRateThrottle

    settings.LOGIN_IP_BLOCK_DISTINCT_ACCOUNTS = 3
    settings.LOGIN_IP_BLOCK_ENABLED = True
    monkeypatch.setattr(ScopedRateThrottle, "allow_request", lambda *args: True)


def fail(username, address=ATTACKER, client=None, **extra):
    return (client or APIClient()).post("/api/v1/auth/login", {"username": username, "password": "wrong-pass-1"},
                                        format="json", HTTP_ORIGIN=ORIGIN, REMOTE_ADDR=address, **extra)


def superadmin():
    return User.objects.create_user(username="platform-root", password="Root password 77!", account_kind="platform",
                                    role=User.Role.SUPERADMIN, is_superuser=True, is_staff=True)


def test_distinct_accounts_from_one_address_block_it_for_a_fixed_hour():
    for name in ("alice", "bob", "carol"):
        assert fail(name).status_code == 401
    block = IPAutoBlock.objects.get()
    assert block.network == "203.0.113.5/32" and len(block.ip_key) == 64
    assert abs((block.blocked_until - timezone.now()) - timedelta(seconds=3600)) < timedelta(seconds=30)
    refused = fail("dave")
    assert refused.status_code == 429 and refused.json()["code"] == "ip_blocked"
    assert 3500 < int(refused["Retry-After"]) <= 3600
    audit = AuditLog.objects.get(action="auth.ip_auto_blocked")
    assert ATTACKER not in str(audit.meta) and audit.meta["ip_key"] == block.ip_key


def test_one_person_mistyping_never_blocks_a_shared_address():
    for _ in range(12):
        fail("alice")
    assert not IPAutoBlock.objects.exists()
    assert fail("alice").status_code == 401


def test_an_active_block_is_not_extended_by_more_failures(settings):
    for name in ("a1", "a2", "a3"):
        fail(name)
    until = IPAutoBlock.objects.get().blocked_until
    source = ip_guard.client_source(RequestFactory().post("/", REMOTE_ADDR=ATTACKER))
    ip_guard.block(source)
    assert IPAutoBlock.objects.get().blocked_until == until


def test_ipv6_counts_per_64():
    for index, name in enumerate(("v1", "v2", "v3")):
        fail(name, address=f"2001:db8:1:2::{index + 10}")
    assert IPAutoBlock.objects.get().network == "2001:db8:1:2::/64"
    assert fail("v4", address="2001:db8:1:2:ffff::1").status_code == 429
    assert fail("v4", address="2001:db8:1:3::1").status_code == 401


@pytest.mark.parametrize("address", ["10.1.2.3", "172.20.0.1", "192.168.0.9", "100.64.1.1", "127.0.0.1", "169.254.1.1",
                                     "fe80::1", "fd00::1", "::1", "not-an-ip"])
def test_private_loopback_link_local_and_unparsable_are_never_blocked(address):
    for name in ("p1", "p2", "p3", "p4"):
        fail(name, address=address)
    assert not IPAutoBlock.objects.exists()


def test_a_short_forwarded_chain_is_skipped_and_logged_once(caplog):
    ip_guard._proxy_warning_logged = False
    with override_settings(REST_FRAMEWORK={"NUM_PROXIES": 2}, AXES_IPWARE_PROXY_COUNT=2):
        request = RequestFactory().post("/", REMOTE_ADDR="198.51.100.1", HTTP_X_FORWARDED_FOR="203.0.113.9")
        first = ip_guard.client_source(request)
        ip_guard.client_source(request)
        full = ip_guard.client_source(RequestFactory().post(
            "/", REMOTE_ADDR="198.51.100.1", HTTP_X_FORWARDED_FOR="203.0.113.9, 198.51.100.7"))
    assert not first.countable
    assert len([r for r in caplog.records if r.msg == "security.proxy_count_exceeds_hops"]) == 1
    assert full.countable and str(full.address) == "203.0.113.9"


def test_the_proxy_itself_is_never_counted():
    with override_settings(REST_FRAMEWORK={"NUM_PROXIES": 1}, AXES_IPWARE_PROXY_COUNT=1):
        request = RequestFactory().post("/", REMOTE_ADDR="198.51.100.1", HTTP_X_FORWARDED_FOR="198.51.100.1")
        assert not ip_guard.client_source(request).countable


def test_switch_off_counts_nothing(settings):
    settings.LOGIN_IP_BLOCK_ENABLED = False
    for name in ("o1", "o2", "o3", "o4"):
        fail(name)
    assert not IPAutoBlock.objects.exists()


def _remembered_device(user):
    device = "d" * 32
    digest = salted_hmac("spaceworks.accounts.device_memory.v1", device, algorithm="sha256").hexdigest()
    KnownDevice.objects.create(user=user, device_hmac=digest, last_verified_at=timezone.now())
    return signing.dumps({"d": device}, salt="accounts.device")


def _blocked():
    for name in ("b1", "b2", "b3"):
        fail(name)
    assert IPAutoBlock.objects.exists()


def test_a_remembered_device_bypasses_auto_blocks_until_it_fails_ten_times():
    person = User.objects.create_user(username="member-dev", password="Device password 91!")
    cookie = _remembered_device(person)
    _blocked()
    client = APIClient()
    client.cookies["sw_device"] = cookie
    ok = client.post("/api/v1/auth/login", {"username": "member-dev", "password": "Device password 91!"},
                     format="json", HTTP_ORIGIN=ORIGIN, REMOTE_ADDR=ATTACKER)
    assert ok.status_code == 200, ok.content
    for _ in range(10):
        fail("member-dev", client=client)
    assert fail("member-dev", client=client).status_code == 429


def test_a_revoked_or_unsigned_device_does_not_bypass():
    person = User.objects.create_user(username="member-rev", password="Device password 91!")
    cookie = _remembered_device(person)
    KnownDevice.objects.update(revoked_at=timezone.now())
    _blocked()
    client = APIClient()
    client.cookies["sw_device"] = cookie
    assert fail("member-rev", client=client).status_code == 429
    client.cookies["sw_device"] = "forged"
    assert fail("member-rev", client=client).status_code == 429


def test_deny_rules_always_apply_even_to_a_remembered_device():
    person = User.objects.create_user(username="member-deny", password="Device password 91!")
    cookie = _remembered_device(person)
    IPAccessRule.objects.create(cidr="203.0.113.0/24", action="deny", created_by=superadmin())
    client = APIClient()
    client.cookies["sw_device"] = cookie
    refused = fail("member-deny", client=client)
    assert refused.status_code == 429 and refused.json()["code"] == "ip_blocked" and "Retry-After" not in refused


def test_allow_beats_deny_and_auto_blocks():
    owner = superadmin()
    _blocked()
    IPAccessRule.objects.create(cidr="203.0.113.0/24", action="deny", created_by=owner)
    IPAccessRule.objects.create(cidr="203.0.113.5", action="allow", created_by=owner)
    assert fail("allowed").status_code == 401


def test_a_deny_rule_with_an_expiry_reports_retry_after():
    IPAccessRule.objects.create(cidr="203.0.113.0/24", action="deny", created_by=superadmin(),
                                expires_at=timezone.now() + timedelta(minutes=10))
    refused = fail("x")
    assert refused.status_code == 429 and 500 < int(refused["Retry-After"]) <= 600


def test_expired_blocks_and_unflagged_routes_are_never_refused():
    _blocked()
    assert APIClient().get("/api/v1/config", REMOTE_ADDR=ATTACKER).status_code == 200
    IPAutoBlock.objects.update(blocked_until=timezone.now() - timedelta(seconds=1))
    assert fail("later").status_code == 401


def test_the_control_login_page_is_guarded(settings):
    settings.CONTROL_PLANE_PROXY = True  # a non-loopback peer needs the website route (#191)
    _blocked()
    response = APIClient().post("/control/login/", {"username": "x", "password": "y"}, REMOTE_ADDR=ATTACKER)
    assert response.status_code == 429 and response["Content-Type"].startswith("text/plain")


def test_a_cache_outage_fails_open_but_deny_rules_still_load(monkeypatch):
    from apps.accounts import ip_guard_middleware, ip_rules

    IPAccessRule.objects.create(cidr="203.0.113.0/24", action="deny", created_by=superadmin())

    class Broken:
        def __getattr__(self, name):
            def fail(*args, **kwargs):
                raise ConnectionError("cache down")
            return fail

    for module in (ip_guard, ip_rules, ip_guard_middleware):
        monkeypatch.setattr(module, "cache", Broken())
    assert fail("nobody").status_code == 429
    assert fail("nobody", address="198.51.100.20").status_code == 401  # counting failed open
    assert not IPAutoBlock.objects.exists()
