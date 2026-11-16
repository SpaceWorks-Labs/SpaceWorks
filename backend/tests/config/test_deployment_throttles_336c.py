"""Decision 336(c): every DRF route without its own throttle has a deployment-wide ceiling.

One baseline counts each request: per signed device, per account, or per API client / client IP. Views with
their own throttles keep exactly theirs; signature-verified provider webhooks opt out. The baseline never reads
the database on the request path, and a `DevicePrincipal` (no `pk`) never crashes it.
"""
from uuid import uuid4

import pytest
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.devices.principal import DevicePrincipal
from apps.managed_hosting import throttle_rates
from config import throttles
from tests.return_helpers import make_user

pytestmark = pytest.mark.django_db
RATES = throttles.FixedWindowRateThrottle.THROTTLE_RATES


class Probe(APIView):
    """A route that declares no throttle of its own, so it gets the deployment baseline."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"ok": True})


def call(user=None, ip="203.0.113.10"):
    request = APIRequestFactory().get("/probe", REMOTE_ADDR=ip)
    if user is not None:
        force_authenticate(request, user=user)
    return Probe.as_view()(request)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    """Mid-window, so a test's few requests never straddle a fixed-window boundary."""
    monkeypatch.setattr(throttles.FixedWindowRateThrottle, "timer", staticmethod(lambda: 1_000_030.0))


@pytest.fixture
def tight(monkeypatch):
    def set_rate(scope, rate):
        monkeypatch.setitem(RATES, scope, rate)
    return set_rate


def device(name="reader"):
    return DevicePrincipal(uuid4(), 1, "adapter", 1, name)


def test_the_baseline_is_configured_with_generous_settings_driven_rates():
    configured = settings.REST_FRAMEWORK
    assert tuple(configured["DEFAULT_THROTTLE_CLASSES"]) == (
        "config.throttles.DeploymentDeviceRateThrottle",
        "config.throttles.DeploymentUserRateThrottle",
        "config.throttles.DeploymentAnonRateThrottle",
    )
    rates = configured["DEFAULT_THROTTLE_RATES"]
    for scope in ("deployment_anon", "deployment_user", "deployment_device"):
        assert throttle_rates.per_second(rates[scope]) >= 5      # at least 300/min: a ceiling, not a limiter
    assert [type(t).__name__ for t in Probe().get_throttles()] == [
        "DeploymentDeviceRateThrottle", "DeploymentUserRateThrottle", "DeploymentAnonRateThrottle"]


def test_signed_out_callers_are_limited_per_ip(tight):
    tight("deployment_anon", "2/min")
    assert [call().status_code for _ in range(2)] == [200, 200]
    refused = call()
    assert refused.status_code == 429 and int(refused["Retry-After"]) >= 1
    assert call(ip="198.51.100.7").status_code == 200       # another address has its own budget


def test_signed_in_callers_are_limited_per_account_not_by_the_anonymous_budget(tight):
    tight("deployment_anon", "1/min")
    tight("deployment_user", "2/min")
    first, second = make_user(f"thr-a-{uuid4().hex[:6]}"), make_user(f"thr-b-{uuid4().hex[:6]}")
    assert [call(first).status_code for _ in range(2)] == [200, 200]
    assert call(first).status_code == 429
    assert call(second).status_code == 200                  # same IP, different account
    assert call(first, ip="198.51.100.8").status_code == 429  # changing network does not reset an account


def test_a_signed_device_is_counted_per_device_and_never_crashes(tight):
    tight("deployment_device", "1/min")
    tight("deployment_user", "1/min")
    reader, printer = device("reader"), device("printer")
    assert call(reader).status_code == 200                  # DevicePrincipal has no pk: no AttributeError
    assert call(reader).status_code == 429
    assert call(printer).status_code == 200                 # two machines behind one NAT do not share a budget


def test_a_missing_rate_disables_that_baseline_instead_of_failing_every_request(monkeypatch):
    monkeypatch.delitem(RATES, "deployment_anon")
    assert all(call().status_code == 200 for _ in range(5))


def test_the_baseline_reads_overrides_from_the_cache_only(tight):
    tight("deployment_anon", "100/min")
    cache.delete(throttle_rates.CACHE_KEY)
    with CaptureQueriesContext(connection) as queries:
        assert call().status_code == 200
    assert not [q for q in queries.captured_queries if "platformthrottlerate" in q["sql"].lower()]
    cache.set(throttle_rates.CACHE_KEY, {"deployment_anon": "1/min"}, 60)   # a superadmin override, once cached
    assert call(ip="192.0.2.50").status_code == 200
    assert call(ip="192.0.2.50").status_code == 429


def test_a_view_with_its_own_throttles_keeps_only_those():
    from apps.makerspaces.handle_views import HandleCheckView

    names = [type(t).__name__ for t in HandleCheckView().get_throttles()]
    assert not [name for name in names if name.startswith("Deployment")]


def test_signature_verified_provider_webhooks_are_exempt():
    from apps.integrations.views_bounce import BounceWebhookView, ProviderBounceWebhookView
    from apps.integrations.views_messaging_webhooks import MetaMessagingWebhookView, TwilioMessagingWebhookView
    from apps.operations.cloud_jobs.tick_views import FreeTickView
    from apps.payments.views import RazorpayWebhookView, StripeWebhookView
    from apps.payments_rail.views_connect import StripeConnectWebhookView

    for view in (StripeWebhookView, RazorpayWebhookView, StripeConnectWebhookView, BounceWebhookView,
                 ProviderBounceWebhookView, TwilioMessagingWebhookView, MetaMessagingWebhookView, FreeTickView):
        assert list(view.throttle_classes) == [], view.__name__


def test_the_new_rates_are_documented_and_on_the_environment_surface():
    from apps.backup.settings_policy import ENV_SURFACE

    names = {"THROTTLE_DEPLOYMENT_ANON", "THROTTLE_DEPLOYMENT_USER", "THROTTLE_DEPLOYMENT_DEVICE",
             "THROTTLE_PROFILE_LOOKUP", "THROTTLE_PROFILE_LOOKUP_DAILY", "THROTTLE_HANDLE_CHECK",
             "THROTTLE_HANDLE_CHECK_DAILY"}
    assert names <= ENV_SURFACE
