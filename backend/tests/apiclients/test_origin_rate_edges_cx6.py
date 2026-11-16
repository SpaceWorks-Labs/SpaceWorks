"""Origins and real throttling counters, with tenant quota policy left intact."""
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.test import RequestFactory, override_settings

from apps.apiclients.models import ApiClient
from apps.apiclients.origin_validation import validate_exact_origins
from apps.apiclients.throttling import ClientTierRateThrottle, MemberPrincipalRateThrottle
from apps.managed_hosting.throttle_rates import CACHE_KEY
from apps.makerspaces.models import Makerspace
from tests.accounts.ua1_helpers import person


@pytest.mark.parametrize("value,message", [
    (None, "At least one allowed origin is required."),
    (["https://host.test/path"], "Origins must be bare scheme://host[:port] values without credentials or paths."),
    (["https://host.test?q=1"], "Origins must be bare scheme://host[:port] values without credentials or paths."),
    (["https://host.test#fragment"], "Origins must be bare scheme://host[:port] values without credentials or paths."),
    (["https://"], "Origins must be bare scheme://host[:port] values without credentials or paths."),
    (["https://host.test:word"], "Origin port is invalid."),
    (["https://host.test:-1"], "Origin port is invalid."),
    (["https://host\u2003.test"], "Origin host must be exact and cannot contain a wildcard."),
])
def test_additional_origin_grammar_refusals_are_exact(value, message):
    with pytest.raises(ValueError) as error:
        validate_exact_origins(value)
    assert str(error.value) == message


@pytest.mark.django_db
@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                                       "LOCATION": "cx6-client-rate"}})
@pytest.mark.parametrize("cap,expected", [(0, [False, False, False]), (1, [True, False, False]),
                                         (None, [True, True, False]), (50, [True, True, False])])
def test_tenant_cap_can_only_lower_the_clients_tier_and_clients_have_independent_counters(cap, expected):
    cache.clear()
    try:
        cache.set(CACHE_KEY, {"client_standard": "2/min"})
        space = Makerspace.objects.create(name="Rate cap", slug="cx6-rate-cap",
            resource_limit_overrides={} if cap is None else {"api_requests_per_minute": cap})
        first, _ = ApiClient.issue(label="First", makerspace=space,
            scopes=["public:catalogue:read"], allowed_origins=["https://rate.test"])
        second, _ = ApiClient.issue(label="Second", makerspace=space,
            scopes=["public:catalogue:read"], allowed_origins=["https://rate.test"])
        request = RequestFactory().get("/")
        request.api_client = first
        throttle = ClientTierRateThrottle()
        throttle.timer = lambda: 120.0
        assert [throttle.allow_request(request, None) for _ in range(3)] == expected
        assert (throttle.num_requests, throttle.duration) == (min(cap, 2) if cap is not None else 2, 60)
        request.api_client = second
        assert throttle.allow_request(request, None) is (cap != 0)
    finally:
        cache.clear()


@pytest.mark.django_db
@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                                       "LOCATION": "cx6-member-rate"}})
def test_member_fallback_separates_people_even_at_the_same_address():
    cache.clear()
    try:
        cache.set(CACHE_KEY, {"api_client_manage": "1/min"})
        first, second = person("cx6-rate-first"), person("cx6-rate-second")
        request = RequestFactory().get("/", REMOTE_ADDR="192.0.2.1")
        request.user = first
        throttle = MemberPrincipalRateThrottle()
        throttle.timer = lambda: 120.0
        view = SimpleNamespace(throttle_scope="api_client_manage")
        assert throttle.allow_request(request, view) is True
        assert throttle.allow_request(request, view) is False
        request.user = second
        assert throttle.allow_request(request, view) is True
    finally:
        cache.clear()
