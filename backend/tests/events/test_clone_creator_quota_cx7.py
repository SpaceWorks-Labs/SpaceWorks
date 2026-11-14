"""Event copies are new monthly drafts, even when the live-events cap is zero."""
import pytest
from django.db import connection

from apps.audit.models import AuditLog
from apps.events.models import Event
from tests.events.staff_grant_helpers import grant_fixture
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.concurrency_helpers_cx7 import race_posts

pytestmark = [pytest.mark.django_db, pytest.mark.area_events]


def scenario():
    space, _, _, source, _ = grant_fixture("edit_details")
    # This events-only fixture must explicitly install native sessions for device callers.
    space.enabled_modules = sorted(set(space.enabled_modules) | {"mobile"})
    space.save(update_fields=["enabled_modules"])
    space.resource_limit_overrides = {"events_monthly": 2, "events": 0}
    space.save(update_fields=["resource_limit_overrides"])
    return space, f"/api/v1/admin/events/{source.pk}/duplicate/"


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_event_clone_max_then_next_refusal_keeps_source_and_copies_unchanged(surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, url = scenario()
    caller = callers(space, surface, settings, monkeypatch)[0]
    assert caller.post(url, {}, format="json").status_code == 201
    assert Event.objects.filter(makerspace=space).count() == 2
    before = list(Event.objects.filter(makerspace=space).order_by("pk").values())
    audits = list(AuditLog.objects.filter(makerspace=space).order_by("pk").values())
    refused = caller.post(url, {}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (409, "event_quota_reached")
    assert list(Event.objects.filter(makerspace=space).order_by("pk").values()) == before
    assert list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()) == audits


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_two_event_clone_creators_at_last_monthly_slot_admit_one(surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space, url = scenario()
    results = race_posts(callers(space, surface, settings, monkeypatch), url, [{}, {}])
    assert sorted(status for status, _ in results) == [201, 409]
    assert [body["code"] for status, body in results if status == 409] == ["event_quota_reached"]
    assert Event.objects.filter(makerspace=space).count() == 2
