"""MOD-2: the work-order move and assign HTTP routes, every state edge and refusal."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.maintenance.models import MaintenanceLog, WorkOrder
from tests.maintenance.l16_helpers import switch, world
from tests.return_helpers import authenticated_client, make_member

pytestmark = pytest.mark.django_db


def _order(w, **extra):
    fields = dict(makerspace=w.space, subject_type="machine", machine=w.machine, title="Replace belt")
    fields.update(extra)
    return WorkOrder.objects.create(**fields)


def _move(user, order, status, **body):
    return authenticated_client(user).post(
        reverse("admin-work-order-status", args=[order.pk]), {"status": status, **body}, format="json")


def _assign(user, order, assignee_id):
    return authenticated_client(user).post(
        reverse("admin-work-order-assign", args=[order.pk]), {"assignee_id": assignee_id}, format="json")


def _audits(order, action):
    return AuditLog.objects.filter(action=action, target_id=str(order.pk)).count()


def test_every_allowed_edge_moves_and_audits_once():
    w = world("wo-edges")
    order = _order(w)
    for status in ("in_progress", "on_hold", "in_progress", "done"):
        response = _move(w.manager, order, status, resolution="Belt replaced" if status == "done" else "")
        assert response.status_code == 200, response.content
        assert response.json()["status"] == status
    order.refresh_from_db()
    assert order.status == "done" and order.closed_by_id == w.manager.pk and order.closed_at
    assert order.log_id and MaintenanceLog.objects.get(pk=order.log_id).summary == "Belt replaced"
    assert _audits(order, "work_order.closed") == 1
    assert _audits(order, "work_order.held") == 1


@pytest.mark.parametrize(("start", "target"), [
    ("done", "in_progress"), ("cancelled", "on_hold"), ("open", "done"), ("on_hold", "done"),
    ("done", "cancelled")])
def test_forbidden_edges_are_refused_with_no_audit_and_no_change(start, target):
    w = world("wo-bad")
    order = _order(w, status=start)
    response = _move(w.manager, order, target)
    assert response.status_code == 400
    order.refresh_from_db()
    assert order.status == start
    assert not AuditLog.objects.filter(target_id=str(order.pk), action__startswith="work_order.").exists()


def test_open_is_not_a_target_and_unknown_status_is_rejected_at_the_boundary():
    w = world("wo-enum")
    order = _order(w)
    assert _move(w.manager, order, "open").status_code == 400
    assert _move(w.manager, order, "<script>alert(1)</script>").status_code == 400
    assert authenticated_client(w.manager).post(
        reverse("admin-work-order-status", args=[order.pk]), {}, format="json").status_code == 400


def test_closing_twice_is_refused_and_writes_one_log_and_one_audit():
    w = world("wo-twice")
    order = _order(w, status="in_progress")
    assert _move(w.manager, order, "done", resolution="ok").status_code == 200
    assert _move(w.manager, order, "done", resolution="ok").status_code == 400
    assert MaintenanceLog.objects.filter(machine=w.machine).count() == 1
    assert _audits(order, "work_order.closed") == 1


def test_resolution_is_truncated_to_4000_and_unicode_kept():
    w = world("wo-unicode")
    order = _order(w, status="in_progress")
    text = "تم الإصلاح 🔧 " + "x" * 5000
    assert _move(w.manager, order, "cancelled", resolution=text).status_code == 200
    order.refresh_from_db()
    assert len(order.resolution) == 4000 and order.resolution.startswith("تم الإصلاح 🔧")


def test_negative_cost_is_refused_and_zero_cost_is_accepted():
    w = world("wo-cost")
    order = _order(w, status="in_progress")
    assert _move(w.manager, order, "done", cost="-1").status_code == 400
    order.refresh_from_db()
    assert order.status == "in_progress"
    assert _move(w.manager, order, "done", cost="0.000", resolution="free").status_code == 200


def test_taking_the_machine_down_follows_start_and_close():
    w = world("wo-down")
    order = _order(w, takes_machine_down=True)
    _move(w.manager, order, "in_progress")
    w.machine.refresh_from_db()
    assert w.machine.status == "maintenance"
    _move(w.manager, order, "cancelled")
    w.machine.refresh_from_db()
    assert w.machine.status == "idle"


def test_another_open_down_order_keeps_the_machine_in_maintenance():
    w = world("wo-down2")
    first, second = _order(w, takes_machine_down=True), _order(w, takes_machine_down=True, title="Second")
    _move(w.manager, first, "in_progress")
    _move(w.manager, second, "in_progress")
    _move(w.manager, first, "cancelled")
    w.machine.refresh_from_db()
    assert w.machine.status == "maintenance"


@pytest.mark.parametrize("route", ["move", "assign"])
def test_signed_out_other_tenant_and_plain_member_are_refused(route):
    w = world("wo-roles")
    order = _order(w)
    other = world("wo-roles-other")
    outsider = make_member("wo-outsider", other.space)
    plain = make_member("wo-plain", w.space, membership_role="member", role="requester")

    def call(user):
        if route == "move":
            return _move(user, order, "in_progress")
        return _assign(user, order, w.manager.pk)

    url = reverse("admin-work-order-status" if route == "move" else "admin-work-order-assign", args=[order.pk])
    assert APIClient().post(url, {"status": "in_progress", "assignee_id": 1}, format="json").status_code in (401, 403)
    assert call(outsider).status_code == 404  # never leaks that the id exists
    assert call(plain).status_code in (403, 404)
    order.refresh_from_db()
    assert order.status == "open" and order.assignee_id is None


def test_inventory_manager_cannot_move_a_machine_order_but_can_move_an_item_order():
    w = world("wo-im")
    machine_order = _order(w)
    item_order = _order(w, subject_type="inventory_product", machine=None, product=w.product, title="Item")
    assert _move(w.im, machine_order, "in_progress").status_code in (403, 404)
    assert _move(w.im, item_order, "in_progress").status_code == 200


def test_machine_capability_off_refuses_then_on_restores_with_data_kept():
    w = world("wo-switch")
    order = _order(w)
    switch(w.space, off=("machines.maintenance",))
    assert _move(w.manager, order, "in_progress").status_code == 404
    order.refresh_from_db()
    assert order.status == "open"
    switch(w.space, on=("machines.maintenance",))
    assert _move(w.manager, order, "in_progress").status_code == 200


def test_assign_sets_clears_audits_and_refuses_non_staff_and_closed_orders():
    w = world("wo-assign")
    order = _order(w)
    assert _assign(w.manager, order, w.tech.pk).status_code == 200
    order.refresh_from_db()
    assert order.assignee_id == w.tech.pk
    assert _assign(w.manager, order, None).status_code == 200
    order.refresh_from_db()
    assert order.assignee_id is None
    assert _audits(order, "work_order.assigned") == 2
    assert _assign(w.manager, order, 99999999).status_code == 400
    assert _assign(w.manager, order, 0).status_code == 400
    bystander = make_member("wo-bystander", w.space, membership_role="member", role="requester")
    assert _assign(w.manager, order, bystander.pk).status_code == 400
    _move(w.manager, order, "cancelled")
    assert _assign(w.manager, order, w.tech.pk).status_code == 400
