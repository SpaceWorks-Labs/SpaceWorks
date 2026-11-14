"""Concrete staff creators beyond inventory: browser and attested native requests."""
import pytest
from django.db import connection
from django.urls import reverse

from apps.apiclients.models import ApiClient
from apps.audit.models import AuditLog
from apps.integrations.models_destinations import NotificationDestination
from apps.operations.models import StocktakeSession
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.concurrency_helpers_cx7 import race_posts
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
CASES = [pytest.param("api_clients", marks=pytest.mark.area_auth),
         pytest.param("webhook_endpoints", marks=pytest.mark.area_notifications),
         pytest.param("stocktake_sessions_monthly", marks=pytest.mark.area_inventory)]


def creator_callers(space, key, surface, settings, monkeypatch):
    pair = callers(space, surface, settings, monkeypatch)
    if key == "api_clients" and surface != "browser":
        from django.utils import timezone
        from apps.accounts.mfa_crypto import totp
        from apps.accounts.models_mfa import UserMFA
        from apps.makerspaces.secrets import decrypt_value
        factor = UserMFA.objects.get(user__username=f"{space.slug}-{surface}")
        code = totp(decrypt_value(factor.secret), int(timezone.now().timestamp() // 30) + 1)
        proof = pair[0].post("/api/v1/auth/reauth", {
            "password": "strong-device-password", "code": code}, format="json")
        assert proof.status_code == 200, proof.data
        assert proof.data["verified"] is True
    return pair


def scenario(key):
    space = make_space("cx7-staff-creator")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"notifications", "stocktake", "webhook"})
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["enabled_modules", "resource_limit_overrides"])
    if key == "api_clients":
        route, model = "admin-api-clients", ApiClient
        bodies = [{"label": label, "client_type": "server", "scopes": ["public:read"],
                   "allowed_origins": ["https://example.com"]} for label in ("First", "Second")]
    elif key == "webhook_endpoints":
        route, model = "admin-notification-destinations", NotificationDestination
        bodies = [{"label": label, "channel": "webhook", "webhook_url": "https://8.8.8.8/hooks"}
                  for label in ("First", "Second")]
    else:
        route, model = "stocktakes", StocktakeSession
        bodies = [{"notes": label} for label in ("First", "Second")]
    return space, reverse(route, kwargs={"makerspace_id": space.pk}), model, bodies


@pytest.mark.parametrize("key", CASES)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_staff_creator_last_slot_next_exact_refusal_and_unchanged_rows(key, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, url, model, bodies = scenario(key)
    caller = creator_callers(space, key, surface, settings, monkeypatch)[0]
    maximum = caller.post(url, bodies[0], format="json")
    assert maximum.status_code == 201
    before = list(model.objects.filter(makerspace=space).order_by("pk").values())
    audits = list(AuditLog.objects.filter(makerspace=space).order_by("pk").values())
    refused = caller.post(url, bodies[1], format="json")
    expected = (400, "limit_reached") if key == "api_clients" else (409, f"{key}_quota_reached")
    assert (refused.status_code, refused.json()["code"]) == expected
    assert list(model.objects.filter(makerspace=space).order_by("pk").values()) == before
    assert list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()) == audits
    assert model.objects.filter(makerspace=space).count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("key", CASES)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_staff_creators_racing_for_last_slot_admit_one(key, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space, url, model, bodies = scenario(key)
    pair = creator_callers(space, key, surface, settings, monkeypatch)
    results = race_posts(pair, url, bodies)
    status, code = (400, "limit_reached") if key == "api_clients" else (409, f"{key}_quota_reached")
    assert sorted(actual for actual, _ in results) == sorted([201, status])
    assert [body["code"] for actual, body in results if actual == status] == [code]
    assert model.objects.filter(makerspace=space).count() == 1
