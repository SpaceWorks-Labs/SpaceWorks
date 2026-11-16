"""The per-space API rate cap has an exact HTTP boundary, through HMAC middleware."""
import pytest
from cryptography.fernet import Fernet
from django.core.cache import cache
from django.urls import reverse

from apps.managed_hosting.throttle_rates import CACHE_KEY
from tests.apiclients.test_staff_reads_lane_f import read
from apps.apiclients.models import ApiClient
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("suffix", ["", ".space-works.tech"])
def test_last_request_passes_next_returns_typed_429_and_other_client_is_independent(suffix, settings, monkeypatch):
    settings.PLATFORM_DOMAIN_SUFFIX = suffix
    settings.INFRA_HOSTS = {"testserver"}
    settings.MANAGED_PLANS_ENABLED = False
    settings.API_CLIENT_AUTH_REQUIRED = True
    settings.APICLIENT_REQUIRE_NONCE = False
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                                   "LOCATION": "cx7-http-api-limit"}}
    cache.clear()
    cache.set(CACHE_KEY, {"client_standard": "120/min"})
    monkeypatch.setattr("apps.apiclients.throttling.ClientTierRateThrottle.timer", lambda *_: 120.0)
    space = make_space("cx7-http-api-limit")
    space.resource_limit_overrides = {"api_requests_per_minute": 1}
    space.public_site_enabled = True
    space.save(update_fields=["resource_limit_overrides", "public_site_enabled"])
    path = reverse("public-inventory", kwargs={"makerspace_slug": space.slug})
    first, secret = ApiClient.issue(label="First", makerspace=space, client_type="server",
                                    allowed_origins=["https://integration.example"], scopes=["public:read"])
    second, second_secret = ApiClient.issue(label="Second", makerspace=space, client_type="server",
                                            allowed_origins=["https://integration.example"], scopes=["public:read"])
    try:
        maximum = read(first, secret, path, HTTP_HOST="testserver")
        assert maximum.status_code == 200
        refused = read(first, secret, path, HTTP_HOST="testserver")
        assert refused.status_code == 429
        assert refused.json()["code"] == "throttled"
        assert refused["Retry-After"] == "60"
        assert read(second, second_secret, path, HTTP_HOST="testserver").status_code == 200
    finally:
        cache.clear()
