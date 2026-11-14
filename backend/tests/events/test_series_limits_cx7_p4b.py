"""Series generation/publishing/editing uses both live and monthly creator budgets."""
from datetime import time, timedelta

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events.models import Event, EventSeries
from apps.events.services_series import create_series, extend_series, publish_series, update_series
from apps.payments.models import Payment
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.return_helpers import make_member, make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_events]
OPERATIONS = ["publish", "extend_draft", "extend_published", "update_draft", "update_published", "schedule"]


def setup(operation, key):
    space = make_space("cx7-p4b-series")
    space.enabled_modules = sorted((set(space.enabled_modules) | {"events", "member_accounts"}) - {"payments"})
    space.enabled_features = sorted((set(space.enabled_features) | {"events.account_registration"})
                                    - {"charges.enabled", "charges.events"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    actor = make_member("cx7-p4b-series-manager", space)
    rows = []
    for index in range(2):
        series, _ = create_series(makerspace=space, actor=actor, title=f"Series {index}",
            recurrence_timezone="UTC", dtstart_local_date=(timezone.now() + timedelta(days=2)).date(),
            dtstart_local_time=time(10), recurrence_rule="FREQ=DAILY;COUNT=1", duration_minutes=60,
            registration_audience="accounts", payment_amount=10)
        if operation in {"extend_published", "update_published", "schedule"}:
            publish_series(series, actor=actor)
            series.refresh_from_db()
        if operation != "schedule":
            series.recurrence_rule = "FREQ=DAILY;COUNT=2"
            series.save(update_fields=["recurrence_rule"])
        rows.append(series)
    # At max-1 for one additional occurrence, or max-2 for schedule replacement.
    cap = (2 if operation == "publish" else 3) if key == "events" else (4 if operation == "schedule" else 3)
    space.resource_limit_overrides = {key: cap}
    space.save(update_fields=["resource_limit_overrides"])
    return space, actor, rows


def invoke(operation, row, actor):
    if operation == "publish":
        return publish_series(row, actor=actor)
    if operation.startswith("extend"):
        return extend_series(row, actor=actor)
    changes = {"recurrence_rule": "FREQ=DAILY;COUNT=2"} if operation == "schedule" else {"title": "Updated"}
    return update_series(row, actor=actor, effective_from=timezone.now(), **changes)


def request(client, operation, row):
    if operation == "publish" or operation.startswith("extend"):
        route = "admin-event-series-publish" if operation == "publish" else "admin-event-series-extend"
        return client.post(reverse(route, kwargs={"pk": row.pk}), {}, format="json")
    body = {"recurrence_rule": "FREQ=DAILY;COUNT=2", "effective_from": timezone.now().isoformat()} \
        if operation == "schedule" else {"title": "Updated"}
    return client.patch(reverse("admin-event-series-detail", kwargs={"pk": row.pk}), body, format="json")


def snapshot():
    return [list(model.objects.order_by("pk").values()) for model in (Event, EventSeries, AuditLog, Payment)]


CASES = [(operation, key) for operation in OPERATIONS for key in ("events", "events_monthly")
         if key != "events" or "draft" not in operation]


@pytest.mark.parametrize("operation,key", CASES)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_series_max_then_next_refusal_rolls_back_every_projection(operation, key, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, _, rows = setup(operation, key)
    client = callers(space, surface, settings, monkeypatch)[0]
    assert request(client, operation, rows[0]).status_code == 200
    before = snapshot()
    refused = request(client, operation, rows[1])
    expected = (400, "limit_reached") if key == "events" else (409, "event_quota_reached")
    assert (refused.status_code, refused.json()["code"]) == expected
    assert snapshot() == before
    assert Payment.objects.filter(makerspace=space).count() == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("operation,key", CASES)
def test_independent_series_racing_for_last_capacity_admit_one(operation, key, settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space, actor, rows = setup(operation, key)
    before = Event.objects.filter(makerspace=space).count()
    expected = (400, "limit_reached") if key == "events" else (409, "event_quota_reached")
    assert race_creators(lambda index: invoke(operation, rows[index], actor)) == [(201, "created"), expected]
    assert Event.objects.filter(makerspace=space).count() == before + (2 if operation == "schedule" else 1)
    assert Payment.objects.filter(makerspace=space).count() == 0


@pytest.mark.parametrize("operation", OPERATIONS)
def test_series_events_off_keeps_projection_then_on_restores_with_rail_and_charges_off(operation, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, _, rows = setup(operation, "events_monthly")
    client = callers(space, "browser", settings, monkeypatch)[0]
    saved = space.enabled_modules
    space.enabled_modules = [key for key in saved if key != "events"]
    space.save(update_fields=["enabled_modules"])
    before = snapshot()
    refused = request(client, operation, rows[0])
    assert (refused.status_code, refused.json()["code"]) == (404, "module_disabled")
    assert snapshot() == before
    space.enabled_modules = saved
    space.save(update_fields=["enabled_modules"])
    assert request(client, operation, rows[0]).status_code == 200
    assert Payment.objects.filter(makerspace=space).count() == 0
