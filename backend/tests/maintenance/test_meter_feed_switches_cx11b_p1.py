"""Usage meters and issued maintenance-calendar tokens survive their policy switches."""
from datetime import timedelta

import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.machines.models import MachineUsageEntry
from apps.maintenance.models import MaintenanceSchedule
from apps.maintenance.meters import meter_due
from apps.maintenance.calendar_feed import issue
from tests.inventory.switch_support_cx11b_p1 import prove_route
from tests.modules.switch_matrix_object_helpers import object_world, retained
from tests.modules.test_switch_matrix_objects_rest_support import _no_write, switch

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_machines, pytest.mark.area_inventory]


@pytest.mark.parametrize("key", ["maintenance.meters", "machines.maintenance", "machines"])
def test_meter_policy_off_hides_due_state_and_restores_same_immutable_usage(key):
    space, _, objects = object_world(False)
    machine = objects["machine"]
    row = MaintenanceSchedule.objects.create(machine=machine, description="Retained usage inspection", interval_days=30,
        next_due=timezone.localdate() + timedelta(days=30), trigger="usage", usage_hours=1)
    usage = MachineUsageEntry.objects.create(machine=machine, hours=2)
    objects.update(schedule=row, usage=usage)
    before = retained(objects)
    assert meter_due(row) is True
    original = switch(space, key)
    row.machine.makerspace = space
    with connection.execute_wrapper(_no_write):
        assert meter_due(row) is False
    switch(space, key, original=original)
    row.machine.makerspace = space
    assert meter_due(row) is True
    assert retained(objects) == before


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["maintenance.calendar_feed", "machines.maintenance", "machines"])
def test_maintenance_feed_switch_retains_issued_token_and_seeded_schedule(key, native):
    space, client, objects = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    row = MaintenanceSchedule.objects.create(machine=objects["machine"], description="Retained calendar inspection",
        interval_days=30, next_due=timezone.localdate() + timedelta(days=3))
    feed, token = issue(actor, space)
    objects.update(schedule=row, feed=feed)
    url = reverse("maintenance-feed-calendar", kwargs={"makerspace_id": space.pk, "raw_token": token})
    prove_route(space, client, objects, key, lambda c: c.get(url),
                off=(404, "feature_disabled" if key == "maintenance.calendar_feed" else "capability_disabled"),
                check=lambda r: _contains_machine(r, objects["machine"].name))


def _contains_machine(response, name):
    assert name.encode() in response.content

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
