"""Machines D6/D7 (MT3/MT5/MT6): work orders, the downtime ledger and lockout."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.machines import role_scope
from apps.machines.lockout import MachineLockedOut, blocking_schedules
from apps.machines.models import MachineDowntime
from apps.machines.service_workflow import start
from apps.maintenance.models import MaintenanceLog, MaintenanceSchedule, WorkOrder
from apps.maintenance.work_orders import create_work_order, move
from tests.machines.eta_helpers import approved, world
from tests.return_helpers import authenticated_client, make_user

pytestmark = pytest.mark.django_db


def maintained(slug):
    w = world(slug)
    w.space.enabled_features = sorted(set(w.space.enabled_features or []) | {"machines.maintenance"})
    w.space.save(update_fields=["enabled_features"])
    return w


def test_a_work_order_that_takes_the_machine_down_opens_and_closes_downtime():
    w = maintained("wo-down")
    machine = w.machines[0]
    order = create_work_order(w.staff, w.space, subject_type="machine", subject=machine, title="Replace belt",
                              takes_machine_down=True, priority="high")
    order = move(w.staff, order, "in_progress")
    machine.refresh_from_db()
    assert machine.status == "maintenance"
    period = MachineDowntime.objects.get(machine=machine)
    assert period.ended_at is None and period.reason == "Replace belt"
    order = move(w.staff, order, "done", resolution="Belt replaced")
    machine.refresh_from_db()
    period.refresh_from_db()
    assert machine.status == "idle" and period.ended_at is not None
    assert order.log_id and MaintenanceLog.objects.filter(pk=order.log_id, machine=machine).exists()
    actions = set(AuditLog.objects.filter(target_id=str(order.pk)).values_list("action", flat=True))
    assert {"work_order.created", "work_order.started", "work_order.closed"} <= actions
    with pytest.raises(Exception):
        move(w.staff, order, "in_progress")


def test_work_orders_are_switch_and_scope_gated_over_the_api():
    w = maintained("wo-api")
    client = authenticated_client(w.staff)
    base = f"/api/v1/admin/makerspaces/{w.space.pk}/work-orders"
    created = client.post(base, {"subject_type": "machine", "subject_id": w.machines[0].pk, "title": "Clean lens"},
                          format="json")
    assert created.status_code == 201, created.content
    assert [row["id"] for row in client.get(base).json()] == [created.json()["id"]]
    member = make_user("wo-api-member", access_status="active")
    assert authenticated_client(member).get(base).status_code in (403, 404)
    w.space.enabled_features = [key for key in w.space.enabled_features if key != "machines.maintenance"]
    w.space.save(update_fields=["enabled_features"])
    assert client.get(base).json() == []
    assert WorkOrder.objects.filter(makerspace=w.space).count() == 1  # data kept


def test_status_changes_record_downtime_with_reason_and_expected_back():
    from apps.machines.services import set_status
    w = maintained("wo-ledger")
    machine = w.machines[0]
    back = timezone.now() + timedelta(days=2)
    set_status(machine, w.staff, "offline", reason="Waiting for a part", expected_back_at=back)
    row = MachineDowntime.objects.get(machine=machine, ended_at__isnull=True)
    assert (row.kind, row.reason, row.expected_back_at) == ("offline", "Waiting for a part", back)
    set_status(machine, w.staff, "idle")
    row.refresh_from_db()
    assert row.ended_at is not None
    response = authenticated_client(w.staff).get(f"/api/v1/admin/machines/{machine.pk}/downtime")
    assert response.status_code == 200 and response.json()["summary"]["periods"] == 1


def test_overdue_blocking_schedule_locks_the_machine_out_after_grace():
    w = maintained("wo-lockout")
    machine = w.machines[0]
    MaintenanceSchedule.objects.create(machine=machine, description="Laser alignment", interval_days=30,
                                       next_due=timezone.localdate() - timedelta(days=1), blocks_use=True)
    assert blocking_schedules(machine)
    row = approved(w, 10, created=-5)
    with pytest.raises(MachineLockedOut):
        start(row, w.staff, role_scope.EXEMPT, machine_id=machine.pk)
    from apps.machines.models import MakerspaceMachineTypePolicy
    MakerspaceMachineTypePolicy.objects.create(makerspace=w.space, machine_type=w.kind, grace_days=3)
    assert not blocking_schedules(machine)
    response = authenticated_client(w.staff).get(f"/api/v1/admin/machines/{machine.pk}/lockout")
    assert response.status_code == 200 and response.json()["locked"] is False
