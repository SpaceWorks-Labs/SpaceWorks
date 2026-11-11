"""GAP2 M1 (#100, #102, #94): maintenance cost reaches the finance ledger, scoped per area. Local only."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.machines.models_membership_scope import MembershipMachineTypeScope
from apps.maintenance import services_workflows, work_orders
from apps.maintenance.ledger import SOURCE_MACHINE, SOURCE_SUBJECT
from apps.maintenance.models import MaintenanceSchedule, WorkOrder
from apps.maintenance.repairs import maintenance_subjects as subjects
from apps.makerspaces.models import MakerspaceMembership
from apps.payments.finance_rows import money_rows
from apps.payments.finance_scope import entry_q, finance_view
from apps.payments.models_ledger_entries import LedgerEntry
from apps.payments.models_settings import MakerspacePaymentSettings
from tests.maintenance.l16_helpers import switch, world
from tests.return_helpers import authenticated_client, make_member

pytestmark = pytest.mark.django_db
D = Decimal


def _schedule(w, subject_type="inventory_product", subject=None):
    return subjects.create_schedule(w.manager, w.space, subject_type=subject_type, subject=subject or w.product,
                                    description="Clean tips", interval_days=30,
                                    next_due=timezone.localdate() + timedelta(days=1))


def _machine_schedule(w):
    return MaintenanceSchedule.objects.create(machine=w.machine, description="Mirror clean", interval_days=7,
                                              next_due=timezone.localdate(), created_by=w.manager)


def test_a_machine_log_with_a_cost_posts_one_maintenance_expense_tagged_with_its_type():
    w = world("gap-m1-log")
    log = services_workflows.log_maintenance(w.machine, actor=w.manager, summary="Lens swap", cost=D("12.50"),
                                             cost_method="cash")
    entry = LedgerEntry.objects.get(source_kind=SOURCE_MACHINE, source_id=str(log.pk))
    assert (entry.kind, entry.category, entry.domain, entry.machine_type_id) == (
        "expense", "maintenance", "machines", w.kind.pk)
    assert (entry.amount, entry.method, entry.account, entry.created_by_id) == (D("12.50"), "cash", "cash", w.manager.pk)
    assert "Laser A" in entry.description


def test_no_cost_or_zero_cost_records_nothing():
    w = world("gap-m1-none")
    services_workflows.log_maintenance(w.machine, actor=w.manager, summary="Dusted")
    services_workflows.log_maintenance(w.machine, actor=w.manager, summary="Checked", cost=D("0"))
    assert not LedgerEntry.objects.filter(makerspace=w.space).exists()


def test_the_space_default_currency_is_used_and_an_explicit_one_wins():
    w = world("gap-m1-ccy")
    MakerspacePaymentSettings.objects.update_or_create(makerspace=w.space, defaults={"default_currency": "inr"})
    first = services_workflows.log_maintenance(w.machine, actor=w.manager, summary="A", cost=D("5"))
    second = services_workflows.log_maintenance(w.machine, actor=w.manager, summary="B", cost=D("5"),
                                                cost_currency="EUR", cost_method="bank_transfer")
    rows = {row.source_id: row for row in LedgerEntry.objects.filter(source_kind=SOURCE_MACHINE)}
    assert (rows[str(first.pk)].currency, rows[str(first.pk)].method) == ("inr", "other")
    assert (rows[str(second.pk)].currency, rows[str(second.pk)].account) == ("eur", "bank")


def test_a_bad_method_refuses_the_whole_log():
    from rest_framework.exceptions import ValidationError
    from apps.maintenance.models import MaintenanceLog
    w = world("gap-m1-bad")
    with pytest.raises(ValidationError):
        services_workflows.log_maintenance(w.machine, actor=w.manager, summary="X", cost=D("3"), cost_method="gold")
    assert not MaintenanceLog.objects.filter(machine=w.machine).exists()


def test_completing_a_machine_schedule_and_closing_a_work_order_both_reach_the_ledger():
    w = world("gap-m1-wo")
    services_workflows.complete_due(_machine_schedule(w), actor=w.manager, summary="Done", cost=D("8"))
    order = WorkOrder.objects.create(makerspace=w.space, subject_type=WorkOrder.Subject.MACHINE, machine=w.machine,
                                     title="Belt", created_by=w.manager)
    work_orders.move(w.manager, order, "in_progress")
    order = work_orders.move(w.manager, order, "done", resolution="Belt replaced", log_cost=D("20"),
                             log_cost_method="upi")
    amounts = sorted(LedgerEntry.objects.filter(source_kind=SOURCE_MACHINE).values_list("amount", "method"))
    assert amounts == [(D("8.00"), "other"), (D("20.00"), "upi")]
    assert LedgerEntry.objects.filter(source_id=str(order.log_id)).exists()


def test_item_and_room_runs_store_the_cost_and_post_to_their_own_domain():
    w = world("gap-m1-subject")
    item_log = subjects.run(w.manager, _schedule(w), summary="Tips cleaned", cost=D("4.00"), cost_method="cash")
    room_log = subjects.run(w.manager, _schedule(w, "bookable_space", w.room), summary="Floor sealed",
                            cost=D("60.00"))
    assert item_log.cost == D("4.00") and room_log.cost == D("60.00")
    item = LedgerEntry.objects.get(source_kind=SOURCE_SUBJECT, source_id=str(item_log.pk))
    room = LedgerEntry.objects.get(source_kind=SOURCE_SUBJECT, source_id=str(room_log.pk))
    assert (item.domain, item.machine_type_id, item.category) == ("inventory", None, "maintenance")
    assert (room.domain, room.amount) == ("bookings", D("60.00"))
    assert "Wood shop" in room.description


def test_the_run_api_accepts_a_cost_and_returns_it():
    w = world("gap-m1-api")
    schedule = _schedule(w)
    response = authenticated_client(w.manager).post(f"/api/v1/admin/subject-maintenance/{schedule.pk}/run",
                                                    {"summary": "Done", "cost": "9.99", "cost_method": "card"},
                                                    format="json")
    assert response.status_code == 201, response.content
    assert response.json()["cost"] == "9.99"
    assert LedgerEntry.objects.get(source_kind=SOURCE_SUBJECT).method == "card"
    bad = authenticated_client(w.manager).post(f"/api/v1/admin/subject-maintenance/{schedule.pk}/run",
                                               {"summary": "Done", "cost": "-1"}, format="json")
    assert bad.status_code == 400


def test_a_covering_technician_records_spending_even_without_finance_rights():
    from tests.maintenance.l16_helpers import in_house
    w = world("gap-m1-tech")
    schedule = _schedule(w)
    in_house(w, coverage=[{"kind": "inventory"}])
    log = subjects.run(w.tech, schedule, summary="Done by tech", cost=D("3"))
    entry = LedgerEntry.objects.get(source_kind=SOURCE_SUBJECT, source_id=str(log.pk))
    assert entry.created_by_id == w.tech.pk
    assert not finance_view(w.tech, w.space.pk).sees("inventory")


def test_each_manager_sees_only_their_areas_maintenance_spend_and_reports_include_it():
    w = world("gap-m1-scope")
    switch(w.space, on=("finance.ledger",))
    services_workflows.log_maintenance(w.machine, actor=w.manager, summary="Laser", cost=D("10"))
    services_workflows.log_maintenance(w.other, actor=w.manager, summary="CNC", cost=D("11"))
    subjects.run(w.manager, _schedule(w), summary="Item", cost=D("12"))
    subjects.run(w.manager, _schedule(w, "bookable_space", w.room), summary="Room", cost=D("13"))
    booking = make_member("gap-m1-bm", w.space, membership_role="booking_manager")
    laser_manager = make_member("gap-m1-mm", w.space, membership_role="machine_manager")
    membership = MakerspaceMembership.staff_tracks.get(user=laser_manager, makerspace=w.space)
    MembershipMachineTypeScope.objects.create(membership=membership, machine_type=w.kind)
    seen = lambda user: sorted(LedgerEntry.objects.filter(entry_q(finance_view(user, w.space.pk)))  # noqa: E731
                               .values_list("amount", flat=True))
    assert seen(booking) == [D("13.00")]
    assert seen(laser_manager) == [D("10.00")]
    assert seen(w.im) == [D("12.00")]
    assert seen(w.manager) == [D("10.00"), D("11.00"), D("12.00"), D("13.00")]
    expenses = sum(row.amount for row in money_rows(w.space) if row.column == "expenses")
    assert expenses == D("46.00")
    url = f"/api/v1/admin/makerspace/{w.space.pk}/finance/entries"
    rows = authenticated_client(booking).get(url).json()["results"]
    assert [(row["domain"], row["category"]) for row in rows] == [("bookings", "maintenance")]


def test_a_blank_method_records_other():
    w = world("gap-m1-blank")
    response = authenticated_client(w.manager).post(f"/api/v1/admin/subject-maintenance/{_schedule(w).pk}/run",
                                                    {"summary": "Done", "cost": "2.00", "cost_method": ""},
                                                    format="json")
    assert response.status_code == 201, response.content
    assert LedgerEntry.objects.get(source_kind=SOURCE_SUBJECT).method == "other"
