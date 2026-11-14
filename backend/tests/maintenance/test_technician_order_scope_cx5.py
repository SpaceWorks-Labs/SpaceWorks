"""The uncovered Technician work-order query branches fail closed by tenant and coverage."""
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.maintenance.models import MaintenanceSchedule, WorkOrder
from apps.maintenance.views_work_orders import visible
from tests.maintenance.l16_helpers import in_house, switch, world
from tests.return_helpers import authenticated_client
from tests.refusal_helpers_mod2b import refused

pytestmark = pytest.mark.django_db


def scheduled(w, machine=None, **values):
    machine = machine or w.machine
    schedule = MaintenanceSchedule.objects.create(machine=machine, description="Inspect", interval_days=7,
                                                   next_due=timezone.localdate())
    return WorkOrder.objects.create(makerspace=w.space, subject_type="machine", machine=machine,
                                    schedule=schedule, title="Scheduled inspection", **values)


def ids(w, actor=None):
    return set(visible(actor or w.tech, w.space).values_list("pk", flat=True))


def test_no_contact_and_empty_coverage_admit_only_personally_assigned_orders():
    w = world("cx5-tech-empty")
    assigned = scheduled(w, assignee=w.tech)
    unassigned = scheduled(w)
    assert ids(w) == {assigned.pk}
    in_house(w)
    assert ids(w) == {assigned.pk}
    assert unassigned.pk not in ids(w)
    other = world("cx5-tech-empty-other")
    foreign = scheduled(other)
    assert foreign.pk not in ids(w)
    assert ids(other, w.tech) == set()


def test_type_coverage_admits_scheduled_work_only_and_archiving_revokes_it():
    w = world("cx5-tech-coverage")
    covered = scheduled(w)
    outside = scheduled(w, w.other)
    unscheduled = WorkOrder.objects.create(makerspace=w.space, subject_type="machine", machine=w.machine,
                                           title="Manager work")
    contact = in_house(w, coverage=({"kind": "machine_type", "machine_type": w.kind},))
    assert ids(w) == {covered.pk}
    assert outside.pk not in ids(w) and unscheduled.pk not in ids(w)
    contact.is_archived = True
    contact.save(update_fields=["is_archived"])
    assert ids(w) == set()


def test_assigned_technician_can_work_the_order_and_switches_restore_without_widening():
    w = world("cx5-tech-route")
    order = scheduled(w, assignee=w.tech)
    unrelated = scheduled(w, w.other)
    api = authenticated_client(w.tech)
    url = reverse("admin-work-order-status", args=[order.pk])
    refused(api.post(reverse("admin-work-order-status", args=[unrelated.pk]),
                     {"status": "in_progress"}, format="json"), 404, "not_found")
    switch(w.space, off=("machines.maintenance",))
    # Assignment gives this actor standing; the disabled capability is then disclosed.
    refused(api.post(url, {"status": "in_progress"}, format="json"), 404, "capability_disabled")
    refused(api.post(reverse("admin-work-order-status", args=[unrelated.pk]),
                     {"status": "in_progress"}, format="json"), 404, "not_found")
    order.refresh_from_db()
    unrelated.refresh_from_db()
    assert order.status == "open"
    assert unrelated.status == "open"
    assert not AuditLog.objects.filter(makerspace=w.space, action="work_order.started").exists()
    switch(w.space, on=("machines.maintenance",))
    result = api.post(url, {"status": "in_progress"}, format="json")
    assert result.status_code == 200 and result.json()["status"] == "in_progress"
    assert ids(w) == {order.pk}
    assert AuditLog.objects.filter(makerspace=w.space, action="work_order.started", target_id=str(order.pk)).count() == 1
