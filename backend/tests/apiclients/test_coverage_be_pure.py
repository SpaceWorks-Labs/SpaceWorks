"""COVERAGE-BE: exact refusals of the small apiclients policy modules (origins, secrets, verdicts, throttles, scopes)."""
from types import SimpleNamespace

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory
from rest_framework.exceptions import PermissionDenied

from apps.apiclients import crypto, person_scopes, scope_registry
from apps.apiclients.origin_validation import validate_exact_origins
from apps.apiclients.scope_registry_routes import TARGET_GLOBAL
from apps.apiclients.scope_registry_verdicts import PEER_CLIENT_TYPE, peer_may_reach, target_allows
from apps.apiclients.throttling import ClientTierRateThrottle, MemberPrincipalRateThrottle


# ------------------------------------------------------------ origin_validation
@pytest.mark.parametrize("bad,message", [
    ("not a list", "At least one allowed origin is required."),
    ([], "At least one allowed origin is required."),
    ([5], "Origins must be exact http(s) URLs."),
    ([" https://a.test"], "Origins must be exact http(s) URLs."),
    (["https://a.test\t"], "Origins must be exact http(s) URLs."),
    (["https://a.te st"], "Origins must be exact http(s) URLs."),
    (["ftp://a.test"], "Origins must be bare scheme://host[:port] values without credentials or paths."),
    (["https://a.test:"], "Origins must be bare scheme://host[:port] values without credentials or paths."),
    (["https://u:p@a.test"], "Origins must be bare scheme://host[:port] values without credentials or paths."),
    (["https://a.test\\x"], "Origins must be bare scheme://host[:port] values without credentials or paths."),
    (["https://a.test:99999"], "Origin port is invalid."),
    (["https://*.a.test"], "Origin host must be exact and cannot contain a wildcard."),
])
def test_validate_exact_origins_refusals_have_exact_messages(bad, message):
    with pytest.raises(ValueError) as caught:
        validate_exact_origins(bad)
    assert str(caught.value) == message


def test_validate_exact_origins_canonicalises_case_default_ports_ipv6_and_duplicates():
    assert validate_exact_origins([
        "HTTPS://Example.TEST:443", "https://example.test", "http://example.test:80",
        "http://example.test:8080", "http://[::1]:3000", "https://[2001:db8::1]",
    ]) == ["https://example.test", "http://example.test", "http://example.test:8080",
           "http://[::1]:3000", "https://[2001:db8::1]"]
    assert validate_exact_origins(("https://a.test",)) == ["https://a.test"]


# ------------------------------------------------------------------- crypto
def test_secret_round_trip_and_missing_key_refused(settings):
    from cryptography.fernet import Fernet
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    token = crypto.encrypt_secret("s3cret")
    assert token != b"s3cret" and crypto.decrypt_secret(token) == "s3cret"
    assert crypto.decrypt_secret(memoryview(token)) == "s3cret"
    settings.API_CLIENT_ENC_KEY = ""
    with pytest.raises(ImproperlyConfigured, match="API_CLIENT_ENC_KEY must be set"):
        crypto.encrypt_secret("x")
    with pytest.raises(ImproperlyConfigured, match="API_CLIENT_ENC_KEY must be set"):
        crypto.decrypt_secret(token)


# ----------------------------------------------------------------- verdicts
def entry(**kw):
    base = dict(server_only=False, tenant_bound=False, target_mode="tenant", tenant_apps_admitted=False,
                access="read", area="catalogue")
    return SimpleNamespace(**{**base, **kw})


def client(makerspace_id, client_type="server"):
    return SimpleNamespace(makerspace_id=makerspace_id, client_type=client_type)


def test_peer_may_reach_only_peer_area_reads():
    assert peer_may_reach(entry(), "GET") and peer_may_reach(entry(), "head") and peer_may_reach(entry())
    assert not peer_may_reach(entry(), "POST")
    assert not peer_may_reach(entry(access="write"), "GET")
    assert not peer_may_reach(entry(area="loans"), "GET")


def test_target_allows_matrix():
    tenant = SimpleNamespace(pk=7)
    assert target_allows(entry(server_only=True), client(7, "browser"), tenant, True) is False
    assert target_allows(entry(), client(None, PEER_CLIENT_TYPE), tenant, True) is False  # peer without a space
    assert target_allows(entry(access="write"), client(7, PEER_CLIENT_TYPE), tenant, True) is False
    assert target_allows(entry(), client(7, PEER_CLIENT_TYPE), tenant, True) is True
    assert target_allows(entry(tenant_bound=True), client(None), tenant, True) is False
    assert target_allows(entry(), client(7), tenant, False) is False  # unresolved target
    assert target_allows(entry(target_mode=TARGET_GLOBAL), client(None), None, True) is True
    assert target_allows(entry(target_mode=TARGET_GLOBAL), client(7), None, True) is False
    assert target_allows(entry(target_mode=TARGET_GLOBAL, tenant_apps_admitted=True), client(7), None, True) is True
    assert target_allows(entry(), client(7), SimpleNamespace(), True) is False  # no pk
    assert target_allows(entry(), client(7), SimpleNamespace(pk=8), True) is False  # other tenant
    assert target_allows(entry(), client(7), tenant, True) is True
    assert target_allows(entry(), client(None), tenant, True) is True  # platform client reaches any target


# ---------------------------------------------------------------- throttling
class FakeClient(SimpleNamespace):
    pass


def api_client(tier, makerspace=None):
    return FakeClient(rate_limit_tier=tier, client_id="cid-1", makerspace_id=getattr(makerspace, "pk", None),
                      makerspace=makerspace)


@pytest.mark.parametrize("tier,expected", [
    ("public", "public"), ("trusted", "trusted"), ("standard", "standard"),
    ("", "standard"), (None, "standard"), ("  ", "standard"), ("platinum", "standard"),
])
def test_throttle_tier_falls_back_to_standard(tier, expected):
    assert ClientTierRateThrottle()._tier(api_client(tier)) == expected


def test_throttle_cache_keys_by_client_id_member_or_fallback():
    throttle = ClientTierRateThrottle()
    throttle.scope = "client_standard"
    request = SimpleNamespace(api_client=api_client("standard"))
    assert throttle.get_cache_key(request, None) == "throttle_client_standard_cid-1"

    member = MemberPrincipalRateThrottle()
    member.scope = "member_scope"
    with_client = SimpleNamespace(api_client=api_client("standard"))
    assert member.get_cache_key(with_client, None) == "throttle_member_scope_cid-1"
    user = SimpleNamespace(is_authenticated=True, pk=42)
    assert member.get_cache_key(SimpleNamespace(api_client=None, user=user), None) == "throttle_member_scope_member:42"


def test_space_limit_can_only_lower_the_tier_rate(monkeypatch):
    space = SimpleNamespace(pk=3)
    throttle = ClientTierRateThrottle()
    throttle.num_requests, throttle.duration = 120, 60
    caps = {}
    monkeypatch.setattr("apps.managed_hosting.extra_quotas.quota_limit", lambda s, key: caps.get("cap"))
    throttle._apply_space_limit(api_client("standard"))  # platform client: untouched
    assert (throttle.num_requests, throttle.duration) == (120, 60)
    throttle._apply_space_limit(api_client("standard", space))  # no override
    assert (throttle.num_requests, throttle.duration) == (120, 60)
    caps["cap"] = 500  # a higher cap never raises the tier rate
    throttle._apply_space_limit(api_client("standard", space))
    assert (throttle.num_requests, throttle.duration) == (120, 60)
    caps["cap"] = 10
    throttle._apply_space_limit(api_client("standard", space))
    assert (throttle.num_requests, throttle.duration) == (10, 60)
    caps["cap"] = 0
    throttle.num_requests, throttle.duration = 120, 60
    throttle._apply_space_limit(api_client("standard", space))
    assert (throttle.num_requests, throttle.duration) == (0, 60)


def test_allow_request_without_api_client_uses_scoped_ip_throttle(monkeypatch):
    seen = []
    monkeypatch.setattr("rest_framework.throttling.ScopedRateThrottle.allow_request",
                        lambda self, request, view: seen.append("scoped") or True)
    assert ClientTierRateThrottle().allow_request(SimpleNamespace(api_client=None), None) is True
    assert seen == ["scoped"]


# ------------------------------------------------------------ person_scopes
def test_validate_scope_policy_exact_messages():
    space = SimpleNamespace(pk=5)
    v = person_scopes.validate
    for bad, message in (
        ([], "Choose at least one scope, each once."),
        (["account:read", "account:read"], "Choose at least one scope, each once."),
        (["bogus:scope"], "Unknown scope(s): bogus:scope."),
    ):
        with pytest.raises(ValueError) as caught:
            v(bad, makerspace=None, staff_space_ids=set())
        assert str(caught.value) == message
    with pytest.raises(ValueError, match="Staff scopes need the space they apply to."):
        v(["staff:read"], makerspace=None, staff_space_ids={5})
    with pytest.raises(ValueError, match="You hold no staff role in that space."):
        v(["staff:read"], makerspace=space, staff_space_ids={6})
    with pytest.raises(ValueError, match="A space is chosen only with staff scopes."):
        v(["account:read"], makerspace=space, staff_space_ids={5})
    assert v(["staff:read", "staff:write"], makerspace=space, staff_space_ids={5}) == ["staff:read", "staff:write"]
    assert v(["account:read", "public:read"], makerspace=None, staff_space_ids=set()) == ["account:read", "public:read"]


def test_catalog_lists_every_scope_with_group_and_staff_space_flag():
    rows = {row["value"]: row for row in person_scopes.catalog()}
    assert rows["staff:read"]["needs_space"] is True and rows["account:read"]["needs_space"] is False
    assert rows["account:write"]["group"] == "Acting as me"
    assert set(rows) >= {"account:read", "account:write", "staff:read", "staff:write"}


def _req(method, path):
    return getattr(RequestFactory(), method.lower())(path)


@pytest.mark.parametrize("path", ["/api/v1/auth/login", "/control/x", "/api/v1/admin/platform/y"])
def test_admit_refuses_credential_and_platform_paths(path):
    with pytest.raises(PermissionDenied) as caught:
        person_scopes.admit(_req("GET", path), {"account:read", "staff:read", "public:read"}, 1)
    assert str(caught.value.detail) == "Tokens cannot reach sign-in, security or credential routes."


def test_admit_account_routes_need_matching_read_or_write_scope():
    person_scopes.admit(_req("GET", "/api/v1/member/loans"), {"account:read"}, None)
    person_scopes.admit(_req("POST", "/api/v1/member/loans"), {"account:write"}, None)
    for method, scopes in (("GET", {"account:write"}), ("POST", {"account:read"}), ("DELETE", set())):
        with pytest.raises(PermissionDenied) as caught:
            person_scopes.admit(_req(method, "/api/v1/member/loans"), scopes, None)
        assert str(caught.value.detail) == "This token's scopes do not include your account routes."


def test_admit_public_routes_need_broad_or_area_scope():
    prefix = "/" + scope_registry._protected_prefixes()[0].rstrip("/")
    path = prefix + "/nothing-here"
    person_scopes.admit(_req("GET", path), {"public:read"}, None)
    person_scopes.admit(_req("POST", path), {"public:write"}, None)
    with pytest.raises(PermissionDenied) as caught:
        person_scopes.admit(_req("GET", path), {"public:write", "account:read"}, None)
    assert str(caught.value.detail) == "This token's scopes do not include this public route."


def _resolved_req(method, path):
    from django.urls import Resolver404, resolve
    request = _req(method, path)
    try:
        request.resolver_match = resolve(path)
    except Resolver404:
        pass
    return request


def test_admit_staff_routes_pin_one_space_and_refuse_unknown_routes():
    path = "/api/v1/admin/makerspace/5/data-exports"
    person_scopes.admit(_resolved_req("GET", path), {"staff:read"}, 5)
    cases = (
        ({"staff:write"}, 5, "This token's scopes do not include staff routes."),   # wrong scope for a read
        ({"staff:read"}, None, "This token's scopes do not include staff routes."),  # no space chosen
        ({"staff:read"}, 6, "This token reaches staff routes of its own space only."),
    )
    for scopes, space_id, message in cases:
        with pytest.raises(PermissionDenied) as caught:
            person_scopes.admit(_resolved_req("GET", path), scopes, space_id)
        assert str(caught.value.detail) == message
    with pytest.raises(PermissionDenied) as caught:
        person_scopes.admit(_resolved_req("GET", "/somewhere/else"), {"account:read", "staff:read"}, 5)
    assert str(caught.value.detail) == "Tokens cannot reach this route."
