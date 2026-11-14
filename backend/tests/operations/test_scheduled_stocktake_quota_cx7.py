"""Scheduled sessions consume the same monthly stocktake allowance as staff forms."""
from datetime import timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from django.db import connection
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.managed_hosting.extra_quotas import ExtraQuotaReached
from apps.operations import stocktake_discipline as discipline
from apps.operations.models import StocktakeSchedule, StocktakeSession
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_stocktake]


def world():
    space = make_space("cx7-scheduled-quota")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"stocktake"})
    space.enabled_features = sorted(set(space.enabled_features) | {"stocktake.discipline"})
    space.resource_limit_overrides = {"stocktake_sessions_monthly": 1}
    space.save(update_fields=["enabled_modules", "enabled_features", "resource_limit_overrides"])
    due = timezone.localdate() - timedelta(days=1)
    rows = [StocktakeSchedule.objects.create(makerspace=space, name=f"Shelf {index}",
            interval_days=30, next_due=due) for index in range(2)]
    return space, rows


def dispatch(space, row):
    now, tz = timezone.now(), ZoneInfo("UTC")
    reminder = SimpleNamespace(subject=f"{row.pk}:{row.next_due}")
    message = discipline.build(space, reminder, now, tz)
    discipline.dispatch(space, reminder, message, now, tz)


def test_scheduled_stocktake_max_refuses_next_without_advancing_the_schedule(settings):
    settings.MANAGED_PLANS_ENABLED = False
    space, rows = world()
    dispatch(space, rows[0])
    assert StocktakeSession.objects.filter(makerspace=space).count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="stocktake.scheduled").count() == 1
    before = list(StocktakeSchedule.objects.order_by("pk").values())
    with pytest.raises(ExtraQuotaReached) as raised:
        dispatch(space, rows[1])
    assert raised.value.status_code == 409
    assert str(raised.value.detail["code"]) == "stocktake_sessions_monthly_quota_reached"
    assert list(StocktakeSchedule.objects.order_by("pk").values()) == before
    assert StocktakeSession.objects.filter(makerspace=space).count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="stocktake.scheduled").count() == 1
    # The original due-date replay creates nothing and remains successful at capacity.
    dispatch(space, rows[0])
    assert StocktakeSession.objects.filter(makerspace=space).count() == 1


@pytest.mark.django_db(transaction=True)
def test_two_different_schedules_racing_for_last_monthly_slot_have_one_winner(settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space, rows = world()
    assert race_creators(lambda index: dispatch(space, rows[index])) == [
        (201, "created"), (409, "stocktake_sessions_monthly_quota_reached")]
    assert StocktakeSession.objects.filter(makerspace=space).count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="stocktake.scheduled").count() == 1
    assert StocktakeSchedule.objects.filter(makerspace=space, next_due=rows[0].next_due).count() == 1
