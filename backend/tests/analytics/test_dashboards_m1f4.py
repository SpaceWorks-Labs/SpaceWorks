"""Dashboard authority is per widget; queue-only homes never invoke analytics."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts import rbac
from apps.hardware_requests.models import HardwareRequest, PublicToolLoan
from apps.machines.models import Machine, MachineType, MachineUsageEntry, MachineServiceRequest, ServiceBucket
from apps.operations import dashboard_widgets
from apps.operations.dashboard_widgets import WIDGETS, visible_widgets
from apps.operations.report_registry import REPORT_REGISTRY
from tests.fixed_roles.helpers import assign_builtin_roles, staff_account
from tests.modules.family_helpers import account, client, family_space
from tests.operations.report_assertions import assert_report_disclosure_safe

pytestmark = pytest.mark.django_db
MODULES = ("reports", "public_inventory", "request_workflow", "guest_handover", "scanner",
           "machines", "machine_service", "bookings", "events", "membership", "mobile", "notifications")
INVENTORY = {"loan-throughput", "overdue-loans", "stock-health", "most-lent", "qr-scans", "top-borrowers"}
MACHINES = {"machine-usage", "machine-usage-heatmap", "machine-downtime", "service-queue-times",
            "machine-errors", "machine-service", "consumable-usage", "consumable-pools"}


def lab(slug="dashboard-m1f4"):
    return family_space(slug, *MODULES, loans=True)


def url(space):
    return f"/api/v1/admin/makerspace/{space.pk}/dashboard"


def keys(payload):
    return {widget["key"] for widget in payload["widgets"]}


@pytest.mark.parametrize("roles,expected", [
    (("inventory_manager",), INVENTORY),
    (("machine_manager",), MACHINES),
    (("event_manager",), {"event-funnel"}),
    (("booking_manager",), {"booking-occupancy"}),
    (("event_manager", "booking_manager"), {"event-funnel", "booking-occupancy"}),
    (("inventory_manager", "machine_manager"), INVENTORY | MACHINES | {"machine-usage-members"}),
    (("space_manager",), {widget.key for widget in WIDGETS}),
])
def test_fixed_role_widget_sets_and_legacy_counts(roles, expected):
    space = lab()
    actor = staff_account(space, "dashboard-staff", *roles)
    response = client(actor).get(url(space))
    assert response.status_code == 200, response.data
    assert keys(response.data) == expected
    assert "scope_mode" in response.data and "pending_prints" in response.data
    for widget in response.data["widgets"]:
        assert widget["chart_spec"] is not None
        assert widget["data"] is not None
        assert widget["default_period"] == 30
        assert_report_disclosure_safe(widget["data"], aggregate=not REPORT_REGISTRY[widget["key"]].identity_bearing)


@pytest.mark.parametrize("module,hidden", [
    ("reports", {widget.key for widget in WIDGETS}),
    ("machines", MACHINES | {"machine-usage-members"}),
    ("request_workflow", {"loan-throughput", "overdue-loans", "most-lent", "top-borrowers"}),
    ("membership", {"membership-growth"}),
    ("events", {"event-funnel"}),
    ("bookings", {"booking-occupancy", "booking-top-members"}),
    ("mobile", {"mobile-devices"}),
])
def test_source_module_off_hides_widgets(module, hidden):
    space = lab()
    actor = staff_account(space, "dashboard-module-owner", "space_manager")
    space.enabled_modules = [key for key in space.enabled_modules if key != module]
    space.save(update_fields=["enabled_modules"])
    assert hidden.isdisjoint({widget.key for widget in visible_widgets(actor, space)})


def test_identity_widgets_need_module_action_and_audit(monkeypatch):
    space = lab()
    actor = staff_account(space, "dashboard-disclosure", "space_manager")
    original = rbac.can
    for denied, forbidden in ((rbac.Action.VIEW_AUDIT, {"top-borrowers", "overdue-loans", "booking-top-members", "machine-usage-members"}),
                              (rbac.Action.MANAGE_BOOKINGS, {"booking-occupancy", "booking-top-members"})):
        monkeypatch.setattr(rbac, "can", lambda user, action, tenant, denied=denied: action != denied and original(user, action, tenant))
        assert forbidden.isdisjoint({widget.key for widget in visible_widgets(actor, space)})


def test_machine_widgets_keep_assigned_types_and_tenant():
    space, other = lab(), lab("dashboard-foreign")
    laser = MachineType.objects.create(makerspace=space, name="Laser", slug="laser")
    printer = MachineType.objects.create(makerspace=space, name="Printer", slug="printer")
    foreign = MachineType.objects.create(makerspace=other, name="Foreign", slug="foreign")
    allowed = None
    for tenant, kind in ((space, laser), (space, printer), (other, foreign)):
        machine = Machine.objects.create(makerspace=tenant, machine_type=kind, name=kind.name)
        MachineUsageEntry.objects.create(machine=machine, hours="2.00", started_at=timezone.now())
        if kind == laser:
            allowed = machine.pk
    actor = staff_account(space, "dashboard-machine-staff", "machine_manager", machine_types=[laser])
    response = client(actor).get(url(space))
    assert response.status_code == 200, response.data
    usage = next(widget for widget in response.data["widgets"] if widget["key"] == "machine-usage")
    assert usage["data"]["meta"]["deferred"] is True
    data = client(actor).get(f"/api/v1/admin/makerspace/{space.pk}/analytics/machine-usage", {
        "start": usage["data"]["meta"]["start"], "end": usage["data"]["meta"]["end"],
    })
    assert data.status_code == 200, data.data
    assert {row["machine_id"] for row in data.data["typed_rows"]} == {allowed}
    assert client(actor).get(url(other)).status_code == 404


def test_handover_only_gets_three_queues_and_no_analytics():
    space, other = lab(), lab("handover-foreign")
    actor = staff_account(space, "dashboard-handover", "handover")
    borrower = account("dashboard-handover-borrower")  # Requesters are member accounts.
    now = timezone.now()
    for tenant in (space, other):
        HardwareRequest.objects.create(makerspace=tenant, requester=borrower, status="accepted")
        HardwareRequest.objects.create(makerspace=tenant, requester=borrower, status="issued", return_due_at=now - timedelta(days=1))
        direct = HardwareRequest.objects.create(makerspace=tenant, requester=borrower, status="issued", return_due_at=now - timedelta(days=1))
        PublicToolLoan.objects.create(makerspace=tenant, requester=borrower, request=direct,
                                     target_type="product", target_id=1, target_label="Drill", due_at=direct.return_due_at)
        kind = MachineType.objects.create(makerspace=tenant, name="Laser", slug="laser")
        machine = Machine.objects.create(makerspace=tenant, machine_type=kind, name="Laser")
        bucket = ServiceBucket.objects.create(machine=machine, name="Queue")
        MachineServiceRequest.objects.create(makerspace=tenant, requester=borrower, member=borrower,
                                             bucket=bucket, assigned_machine=machine, status="completed", title="Pickup")
    with patch("apps.operations.reports.report_data", side_effect=AssertionError("No analytics for handover")):
        response = client(actor).get(url(space))
    assert response.status_code == 200, response.data
    assert response.data["widgets"] == []
    assert response.data["scope_mode"] == "handover"
    assert response.data["queue_tiles"] == {"ready_to_issue": 1, "due_returns": 2, "pickups": 1}
    assert "low_stock" not in response.data and "pending_payments" not in response.data


def test_member_is_not_staff_and_unservable_tenants_are_refused():
    space, member = lab(), account("dashboard-plain-member")
    assign_builtin_roles(member, space, "member")
    assert client(member).get(url(space)).status_code == 403
    # Staff authority lives on a separate tenant-bound staff account.
    actor = staff_account(space, "dashboard-plain-staff", "space_manager")
    space.archived_at = timezone.now()
    space.save(update_fields=["archived_at"])
    assert client(actor).get(url(space)).status_code == 404
    assert visible_widgets(actor, space) == ()


def test_dashboard_counters_return_without_executing_any_report_builder():
    space = lab()
    actor = staff_account(space, "dashboard-report-dispatch", "space_manager")
    with patch("apps.operations.reports.report_data", side_effect=AssertionError("No synchronous analytics")) as render:
        response = client(actor).get(url(space))
    assert response.status_code == 200, response.data
    assert "pending_requests" in response.data
    assert response.data["widgets"]
    assert all(widget["data"]["meta"]["deferred"] for widget in response.data["widgets"])
    render.assert_not_called()


def test_changed_report_actions_cannot_be_bypassed_by_widget_metadata(monkeypatch):
    space = lab()
    actor = staff_account(space, "dashboard-registry-boundary", "inventory_manager")
    monkeypatch.setitem(REPORT_REGISTRY, "most-lent", replace(REPORT_REGISTRY["most-lent"], required_action=rbac.Action.MANAGE_MAKERSPACE))
    assert "most-lent" not in {widget.key for widget in visible_widgets(actor, space)}


def test_widget_window_supplies_local_calendar_labels_for_independent_requests():
    from apps.makerspaces.local_time import to_local

    space = lab()
    actor = staff_account(space, "dashboard-local-period", "space_manager")
    space.timezone = "Asia/Kolkata"
    space.save(update_fields=["timezone"])
    # At 20:00 UTC the tenant has already moved to the next calendar day.
    from datetime import datetime, timezone as dt_timezone
    now = datetime(2026, 10, 16, 20, tzinfo=dt_timezone.utc)
    with patch("django.utils.timezone.now", return_value=now):
        widgets = dashboard_widgets.build_widgets(actor, space)
    today = to_local(space, now).date()
    assert str(today) == "2026-10-17"
    for widget in widgets:
        assert widget["data"]["meta"] == {"deferred": True,
            "start": (today - timedelta(days=29)).isoformat(), "end": today.isoformat()}
