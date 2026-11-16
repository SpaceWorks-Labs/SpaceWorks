"""Scheduled stocktakes are routeless worker behavior, with retained policy and schedule."""
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.operations.models import StocktakePolicy, StocktakeSchedule, StocktakeSession
from apps.operations.reminder_sweeper import run_reminder_sweep
from tests.modules.switch_matrix_object_helpers import object_world, retained
from tests.modules.test_switch_matrix_objects_rest_support import _no_write, switch

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory, pytest.mark.area_stocktake]


@pytest.mark.parametrize("key", ["stocktake.discipline", "stocktake"])
def test_stocktake_worker_off_keeps_policy_and_on_creates_one_blind_session(key):
    space, _, _ = object_world(False)
    now = timezone.now()
    policy = StocktakePolicy.objects.create(makerspace=space, blind_default=True, variance_threshold=1)
    row = StocktakeSchedule.objects.create(makerspace=space, name="Retained count", interval_days=30,
        next_due=now.date() - timedelta(days=2), blind=True)
    objects = {"schedule": row, "policy": policy}
    before, count = retained(objects), StocktakeSession.objects.filter(makerspace=space).count()
    original = switch(space, key)
    with connection.execute_wrapper(_no_write):
        assert run_reminder_sweep(now=now, source_keys=["stocktake.scheduled"]) == {
            "dispatched": 0, "skipped": 1, "failed": 0}
    assert retained(objects) == before
    assert StocktakeSession.objects.filter(makerspace=space).count() == count
    switch(space, key, original=original)
    assert run_reminder_sweep(now=now, source_keys=["stocktake.scheduled"]) == {
        "dispatched": 1, "skipped": 0, "failed": 0}
    assert StocktakeSession.objects.filter(makerspace=space, blind=True, variance_threshold=1).count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="stocktake.scheduled").count() == 1
    assert run_reminder_sweep(now=now, source_keys=["stocktake.scheduled"]) == {
        "dispatched": 0, "skipped": 0, "failed": 0}
    assert StocktakeSession.objects.filter(makerspace=space).count() == count + 1
