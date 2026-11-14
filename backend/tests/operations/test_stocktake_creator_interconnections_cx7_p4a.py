"""Monthly capacity is shared by manual counts and the gated schedule worker."""
import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.operations import reminder_sweeper
from apps.operations.models import StocktakeSchedule, StocktakeSession
from apps.operations.models_reminders import ReminderSchedule
from apps.operations.services_stocktake_workflow import create_stocktake
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.operations.test_scheduled_stocktake_quota_cx7 import dispatch, world
from tests.return_helpers import make_member

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_stocktake]


@pytest.mark.django_db(transaction=True)
def test_manual_and_scheduled_creators_race_for_one_monthly_slot(settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space, schedules = world()
    actor = make_member("p4a-count-manager", space)
    assert race_creators(lambda index: create_stocktake(actor, space, {"notes": "Manual"})
                         if index == 0 else dispatch(space, schedules[0])) == [
                             (201, "created"), (409, "stocktake_sessions_monthly_quota_reached")]
    assert StocktakeSession.objects.filter(makerspace=space).count() == 1
    assert AuditLog.objects.filter(makerspace=space, action__in=["stocktake.created", "stocktake.scheduled"]).count() == 1
    schedules[0].refresh_from_db()
    scheduled_won = StocktakeSession.objects.filter(makerspace=space, notes=schedules[0].name).exists()
    assert (schedules[0].next_due > schedules[1].next_due) is scheduled_won


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("key,field", [("stocktake", "enabled_modules"),
                                       ("stocktake.discipline", "enabled_features")])
def test_scheduled_creator_off_has_no_intent_or_session_on_restores_retained_schedule(key, field, settings):
    settings.MANAGED_PLANS_ENABLED = False
    space, schedules = world()
    # One due subject, so the restored worker reaches exactly the configured max.
    schedules[1].is_active = False
    schedules[1].save(update_fields=["is_active"])
    original = list(getattr(space, field))
    setattr(space, field, [value for value in original if value != key])
    space.save(update_fields=[field])
    before = list(StocktakeSchedule.objects.order_by("pk").values())
    audits = list(AuditLog.objects.filter(makerspace=space).order_by("pk").values())
    off = reminder_sweeper.run_reminder_sweep(now=timezone.now(), source_keys=["stocktake.scheduled"])
    assert off == {"dispatched": 0, "skipped": 1, "failed": 0}
    assert StocktakeSession.objects.filter(makerspace=space).count() == 0
    assert ReminderSchedule.objects.filter(makerspace=space).count() == 0
    assert list(StocktakeSchedule.objects.order_by("pk").values()) == before
    assert list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()) == audits
    setattr(space, field, original)
    space.save(update_fields=[field])
    on = reminder_sweeper.run_reminder_sweep(now=timezone.now(), source_keys=["stocktake.scheduled"])
    assert on == {"dispatched": 1, "skipped": 0, "failed": 0}
    assert StocktakeSession.objects.filter(makerspace=space).count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="stocktake.scheduled").count() == 1


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_stocktake_module_off_retains_same_creator_payload_then_on_admits_it(surface, settings, monkeypatch):
    space, _ = world()
    caller = callers(space, surface, settings, monkeypatch)[0]
    space.enabled_modules.remove("stocktake")
    space.save(update_fields=["enabled_modules"])
    url = reverse("stocktakes", args=[space.pk])
    before = list(AuditLog.objects.filter(makerspace=space).order_by("pk").values())
    refused = caller.post(url, {"notes": "Retained"}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (404, "module_disabled")
    assert StocktakeSession.objects.filter(makerspace=space).count() == 0
    assert list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()) == before
    space.enabled_modules.append("stocktake")
    space.save(update_fields=["enabled_modules"])
    assert caller.post(url, {"notes": "Retained"}, format="json").status_code == 201
    assert StocktakeSession.objects.filter(makerspace=space, notes="Retained").count() == 1
