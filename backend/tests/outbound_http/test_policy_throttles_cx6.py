"""Address-policy edge cases and real per-account fixed-window throttles."""
import socket
from ipaddress import ip_network

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import RequestFactory, override_settings

from apps.outbound_policy import OutboundRefused, is_public_https, refusal, resolve
from apps.outbound_throttles import AnthiasPlayerThrottle, ImageAdapterTestThrottle
from apps.managed_hosting.throttle_rates import CACHE_KEY
from tests.accounts.ua1_helpers import person


@pytest.mark.parametrize("address", ["bad-ip", "", "0.1.2.3", "::", "fec0::1", "ff02::1",
    "64:ff9b:1::a9fe:a9fe", "2002:7f00:1::1", "::ffff:127.0.0.1"])
def test_forbidden_addresses_remain_forbidden_with_both_operator_allowances(address):
    assert refusal(address, allow_private=True, allow_loopback=True) == "blocked_address"


def test_extra_ipv6_networks_and_scoped_address_literals_are_checked():
    assert refusal("2606:4700::1", extra_blocked=(ip_network("2606:4700::/32"),)) == "blocked_address"
    assert refusal("2606:4700::1", extra_blocked=(ip_network("10.0.0.0/8"),)) is None
    assert refusal("fe80::1%eth0", allow_private=True) == "blocked_address"


@pytest.mark.parametrize("answer", [[], [(socket.AF_UNIX, 1, 0, "", ("93.184.216.34", 443))]])
def test_empty_or_unsupported_dns_answers_fail_closed(monkeypatch, answer):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: answer)
    with pytest.raises(OutboundRefused) as error:
        resolve("https://resolver.test")
    assert error.value.reason == ("dns_failed" if not answer else "blocked_address")


@pytest.mark.parametrize("failure", [socket.gaierror("missing"), UnicodeError("invalid host"), ValueError("invalid port")])
def test_dns_failures_have_one_non_disclosing_reason(monkeypatch, failure):
    def dns(*args, **kwargs):
        raise failure

    monkeypatch.setattr(socket, "getaddrinfo", dns)
    with pytest.raises(OutboundRefused) as error:
        resolve("https://resolver.test")
    assert error.value.reason == "dns_failed"
    assert is_public_https("https://resolver.test") is False


def test_duplicate_dns_answers_are_pinned_once_and_with_path_keeps_the_same_addresses(monkeypatch):
    calls = []
    answer = (socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("2606:4700::1", 8443, 0, 0))

    def dns(*args, **kwargs):
        calls.append((args, kwargs))
        return [answer, answer]

    monkeypatch.setattr(socket, "getaddrinfo", dns)
    target = resolve("https://[2606:4700::1]:8443/path?q=value", ports={8443})
    assert len(calls) == 1
    assert target.host_header == "[2606:4700::1]:8443"
    assert target.request_target == "/path?q=value"
    assert len(target.addresses) == 1
    assert target.addresses[0].ip == "2606:4700::1"
    next_target = target.with_path("/next")
    assert next_target.addresses is target.addresses
    assert (next_target.hostname, next_target.port, next_target.request_target) == ("2606:4700::1", 8443, "/next")


@pytest.mark.django_db
@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                                       "LOCATION": "cx6-outbound-rate"}})
@pytest.mark.parametrize("kind", [AnthiasPlayerThrottle, ImageAdapterTestThrottle])
def test_outbound_rate_limit_is_per_account_and_reopens_at_the_exact_window_boundary(kind):
    cache.clear()
    try:
        cache.set(CACHE_KEY, {kind.scope: "2/min"})
        first, second = person("cx6-outbound-first"), person("cx6-outbound-second")
        request = RequestFactory().post("/")
        request.user = first
        throttle = kind()
        clock = [120.0]
        throttle.timer = lambda: clock[0]
        assert throttle.rate == "2/min"
        assert [throttle.allow_request(request, None) for _ in range(3)] == [True, True, False]
        assert throttle.wait() == 60.0
        request.user = second
        assert throttle.allow_request(request, None) is True
        request.user = first
        clock[0] = 180.0
        assert throttle.allow_request(request, None) is True
        request.user = AnonymousUser()
        assert throttle.get_cache_key(request, None) is None
        assert throttle.allow_request(request, None) is True
    finally:
        cache.clear()
