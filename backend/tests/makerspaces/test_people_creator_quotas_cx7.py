"""Membership definitions and free donation campaigns enforce capacity on every client."""
import pytest
from django.db import connection
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.makerspaces.models import MemberUnit, MembershipPlan
from apps.payments.donations.models import DonationCampaign
from apps.payments.models import Payment
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.concurrency_helpers_cx7 import race_posts
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
KEYS = [pytest.param("member_units", marks=pytest.mark.area_membership),
        pytest.param("membership_plans", marks=pytest.mark.area_membership),
        pytest.param("donation_campaigns", marks=pytest.mark.area_payments_ledger)]


def scenario(key):
    space = make_space("cx7-people-capacity")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"membership", "member_accounts"})
    space.enabled_features = sorted((set(space.enabled_features) | {"membership.units", "finance.donations"})
                                    - {"charges.enabled", "charges.donations", "charges.membership"})
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["enabled_modules", "enabled_features", "resource_limit_overrides"])
    if key == "member_units":
        route, model = "admin-member-units", MemberUnit
        bodies = [{"name": name} for name in ("North", "South")]
    elif key == "membership_plans":
        route, model = "admin-membership-plans", MembershipPlan
        bodies = [{"name": name, "interval": "monthly", "amount": "0", "currency": "usd"}
                  for name in ("First", "Second")]
    else:
        route, model = "admin-donation-campaigns", DonationCampaign
        bodies = [{"name": name, "slug": name.lower(), "kind": "campaign", "goal_amount": "10.00"}
                  for name in ("First", "Second")]
    return space, reverse(route, kwargs={"makerspace_id": space.pk}), model, bodies


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_people_definition_max_next_refusal_keeps_rows_and_never_charges(key, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, url, model, bodies = scenario(key)
    caller = callers(space, surface, settings, monkeypatch)[0]
    assert caller.post(url, bodies[0], format="json").status_code == 201
    rows = list(model.objects.filter(makerspace=space).order_by("pk").values())
    audits = list(AuditLog.objects.filter(makerspace=space).order_by("pk").values())
    refused = caller.post(url, bodies[1], format="json")
    assert refused.status_code == 409
    assert refused.json()["code"] == f"{key}_quota_reached"
    assert list(model.objects.filter(makerspace=space).order_by("pk").values()) == rows
    assert list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()) == audits
    assert model.objects.filter(makerspace=space).count() == 1
    assert Payment.objects.filter(makerspace=space).count() == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_two_people_definition_creators_racing_at_last_slot_admit_one(key, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space, url, model, bodies = scenario(key)
    pair = callers(space, surface, settings, monkeypatch)
    results = race_posts(pair, url, bodies)
    assert sorted(status for status, _ in results) == [201, 409]
    assert [body["code"] for status, body in results if status == 409] == [f"{key}_quota_reached"]
    assert model.objects.filter(makerspace=space).count() == 1
    assert Payment.objects.filter(makerspace=space).count() == 0


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_campaign_feature_off_hides_creator_and_restore_preserves_capacity(surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, url, model, bodies = scenario("donation_campaigns")
    caller = callers(space, surface, settings, monkeypatch)[0]
    assert caller.post(url, bodies[0], format="json").status_code == 201
    before = list(model.objects.filter(makerspace=space).values())
    space.enabled_features = [key for key in space.enabled_features if key != "finance.donations"]
    space.save(update_fields=["enabled_features"])
    off = caller.post(url, bodies[1], format="json")
    assert (off.status_code, off.json()["code"]) == (404, "feature_disabled")
    assert list(model.objects.filter(makerspace=space).values()) == before
    space.enabled_features.append("finance.donations")
    space.resource_limit_overrides = {"donation_campaigns": 2}
    space.save(update_fields=["enabled_features", "resource_limit_overrides"])
    assert caller.post(url, bodies[1], format="json").status_code == 201
    assert model.objects.filter(makerspace=space).count() == 2
    assert Payment.objects.filter(makerspace=space).count() == 0
