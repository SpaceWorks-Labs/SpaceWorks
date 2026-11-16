"""Drafts, recurrence and publishing are distinct quota-consuming event surfaces."""
from datetime import timedelta

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events.models import Event, EventSeries
from apps.events.services_series import extend_series
from apps.events.services import publish
from apps.managed_hosting.space_quotas import SpaceQuotaReached
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.concurrency_helpers_cx7 import race_posts
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.return_helpers import make_member, make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_events]


def scenario(kind):
    space = make_space("cx7-event-creator")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"events"})
    space.enabled_features = sorted(set(space.enabled_features) | {"events.account_registration"})
    space.event_default_registration_audience = "accounts"
    space.resource_limit_overrides = {"events_monthly": 1, "events": 0}
    space.save(update_fields=["enabled_modules", "enabled_features", "event_default_registration_audience", "resource_limit_overrides"])
    tomorrow = timezone.now() + timedelta(days=1)
    if kind == "event":
        route = "admin-event-list-create"
        body = {"title": "Last draft", "description": "", "starts_at": tomorrow.isoformat(),
                "ends_at": (tomorrow + timedelta(hours=1)).isoformat(), "location": "",
                "capacity": 0, "is_public": False, "registration_audience": "accounts"}
    else:
        route = "admin-event-series-list-create"
        body = {"title": "Last series", "recurrence_timezone": "UTC",
                "dtstart_local_date": str(tomorrow.date()), "dtstart_local_time": "10:00:00",
                "recurrence_rule": "FREQ=DAILY;COUNT=1", "duration_minutes": 60,
                "registration_audience": "accounts"}
    return space, reverse(route, kwargs={"makerspace_id": space.pk}), body


def snapshot():
    return {model.__name__: list(model.objects.order_by("pk").values())
            for model in (Event, EventSeries, AuditLog)}


@pytest.mark.parametrize("kind", ["event", "series"])
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_draft_creators_consume_monthly_capacity_before_any_write(kind, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, url, body = scenario(kind)
    caller = callers(space, surface, settings, monkeypatch)[0]
    maximum = caller.post(url, body, format="json")
    assert maximum.status_code == 201
    assert Event.objects.filter(makerspace=space, status="draft").count() == 1
    assert EventSeries.objects.filter(makerspace=space).count() == (1 if kind == "series" else 0)
    before = snapshot()
    refused = caller.post(url, {**body, "title": "Excess"}, format="json")
    assert refused.status_code == 409
    assert refused.json()["code"] == "event_quota_reached"
    assert snapshot() == before


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", ["event", "series"])
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_racing_draft_creators_at_last_monthly_slot_admit_one(kind, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space, url, body = scenario(kind)
    pair = callers(space, surface, settings, monkeypatch)
    results = race_posts(pair, url, [{**body, "title": name} for name in ("First", "Second")])
    assert sorted(status for status, _ in results) == [201, 409]
    assert [body["code"] for status, body in results if status == 409] == ["event_quota_reached"]
    assert Event.objects.filter(makerspace=space).count() == 1
    action = "event.series_created" if kind == "series" else "event.created"
    assert AuditLog.objects.filter(makerspace=space, action=action).count() == 1


def test_draft_series_extension_refuses_only_new_occurrences_and_preserves_retry(settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, url, body = scenario("series")
    caller = callers(space, "browser", settings, monkeypatch)[0]
    assert caller.post(url, body, format="json").status_code == 201
    series = EventSeries.objects.get(makerspace=space)
    # Simulate a later recurrence template with one more occurrence to materialize.
    series.recurrence_rule = "FREQ=DAILY;COUNT=2"
    series.save(update_fields=["recurrence_rule"])
    before = snapshot()
    with pytest.raises(SpaceQuotaReached) as raised:
        extend_series(series)
    assert raised.value.status_code == 409
    assert str(raised.value.detail["code"]) == "event_quota_reached"
    assert snapshot() == before
    space.resource_limit_overrides["events_monthly"] = 2
    space.save(update_fields=["resource_limit_overrides"])
    _, created = extend_series(series)
    assert len(created) == 1
    assert Event.objects.filter(makerspace=space).count() == 2
    _, replay = extend_series(series)
    assert replay == []
    assert Event.objects.filter(makerspace=space).count() == 2


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_publish_live_limit_max_and_next_does_not_recount_drafts(surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, url, body = scenario("event")
    space.resource_limit_overrides = {"events_monthly": 2, "events": 1}
    space.save(update_fields=["resource_limit_overrides"])
    caller = callers(space, surface, settings, monkeypatch)[0]
    for title in ("First", "Second"):
        assert caller.post(url, {**body, "title": title}, format="json").status_code == 201
    first, second = Event.objects.filter(makerspace=space).order_by("pk")
    maximum = caller.post(reverse("admin-event-publish", kwargs={"pk": first.pk}), {}, format="json")
    assert maximum.status_code == 200
    before = snapshot()
    refused = caller.post(reverse("admin-event-publish", kwargs={"pk": second.pk}), {}, format="json")
    assert refused.status_code == 400
    assert refused.json()["code"] == "limit_reached"
    assert snapshot() == before
    assert Event.objects.filter(makerspace=space, status="published").count() == 1


@pytest.mark.django_db(transaction=True)
def test_two_publish_creators_at_last_live_slot_admit_one(settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space, _, _ = scenario("event")
    space.resource_limit_overrides = {"events": 1, "events_monthly": 2}
    space.save(update_fields=["resource_limit_overrides"])
    actor = make_member("cx7-event-publish-race", space)
    start = timezone.now() + timedelta(days=1)
    rows = [Event.objects.create(makerspace=space, title=f"Draft {index}", starts_at=start,
            ends_at=start + timedelta(hours=1), registration_audience="accounts", created_by=actor)
            for index in range(2)]
    assert race_creators(lambda index: publish(rows[index], actor=actor)) == [(201, "created"), (400, "limit_reached")]
    assert Event.objects.filter(makerspace=space, status="published").count() == 1
    assert Event.objects.filter(makerspace=space, status="draft").count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="event.published").count() == 1
