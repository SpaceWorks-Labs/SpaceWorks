"""Repair creation and retained subject schedules, on both staff transports."""
from datetime import date

import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.urls import reverse

from apps.maintenance.repairs import maintenance_subjects
from tests.maintenance.l16_helpers import world
from tests.modules.switch_matrix_object_helpers import client_for
from tests.inventory.switch_support_cx11b_p1 import prove_route, staff_outsiders

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory,
              pytest.mark.area_machines, pytest.mark.area_bookings]
AREAS = [("machines.repairs", "machine", "machine", "machines", "machines.maintenance"),
         ("inventory.repairs", "inventory_product", "product", None, "inventory.maintenance"),
         ("bookings.room_repairs", "bookable_space", "room", "bookings", "bookings.room_maintenance")]
CASES = [(feature, kind, target, key) for feature, kind, target, parent, maintenance in AREAS
         for key in (feature, maintenance, *([parent] if parent else ["loans.enabled"]))]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("feature,kind,target,key", CASES)
def test_repair_switch_refuses_before_writes_and_restores_subject(feature, kind, target, key, native):
    w = world("p1-repair")
    client = client_for(w.manager, w.space, native)
    subject = getattr(w, target)
    url = reverse("admin-issues", kwargs={"makerspace_id": w.space.pk})
    body = {"subject_type": kind, "subject_id": subject.pk, "title": "Retained repair"}
    prove_route(w.space, client, {"subject": subject}, key,
                lambda c: c.post(url, body, format="json"), off=(404, "capability_disabled"), on=(201, None), outsiders=staff_outsiders(native))


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["inventory.maintenance", "loans.enabled"])
def test_inventory_maintenance_switch_retains_schedule_and_resumes_updates(native, key):
    w = world("p1-upkeep")
    row = maintenance_subjects.create_schedule(w.manager, w.space, subject_type="inventory_product",
        subject=w.product, description="Retained inspection", interval_days=30, next_due=date(2099, 1, 1))
    url = reverse("admin-subject-maintenance-detail", kwargs={"pk": row.pk})
    prove_route(w.space, client_for(w.manager, w.space, native), {"schedule": row, "product": w.product},
                key, lambda c: c.patch(url, {"description": "Updated inspection"}, format="json"),
                off=(404, "capability_disabled"), outsiders=staff_outsiders(native))

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
