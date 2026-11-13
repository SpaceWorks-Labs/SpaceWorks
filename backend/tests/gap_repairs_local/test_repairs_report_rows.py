"""RP-5 builders: the numbers, and the per-viewer narrowing through the repairs authority."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.maintenance import work_orders
from apps.maintenance.models import RepairPart
from apps.maintenance.repairs import reports as rr
from tests.gap_repairs_local.helpers import hours_ago, issue, machine_manager, role, set_due, set_issue, world
from tests.maintenance.l16_helpers import in_house

pytestmark = pytest.mark.django_db


def ids(result, field):
    return [row[field] for row in result.records]


def test_open_work_orders_put_the_overdue_ones_first_and_skip_finished_work():
    w = world("rp5-wo")
    late = issue(w, "machine", w.machine, "Lens cracked")
    set_due(late, -2)
    later = issue(w, "bookable_space", w.room, "Door sticks")
    set_due(later, 5)
    undated = issue(w, "inventory_product", w.product, "Tip loose")
    done = issue(w, "machine", w.other, "Belt")
    work_orders.move(w.manager, done.work_order, "in_progress")
    work_orders.move(w.manager, done.work_order, "done", resolution="Tensioned")
    result = rr.build_work_orders(w.space.pk, actor=w.manager)
    assert result.field_order == rr.WORK_ORDER_FIELDS
    assert ids(result, "work_order_id") == [late.work_order_id, later.work_order_id, undated.work_order_id]
    first = result.records[0]
    assert first["overdue"] is True and first["area"] == "machines" and first["machine_type"] == "Laser"
    assert first["issue_id"] == late.pk and first["subject_name"] == "Laser A" and first["days_open"] == 0
    assert [row["overdue"] for row in result.records[1:]] == [False, False]
    assert rr.build_work_orders(w.space.pk, actor=w.manager, limit=1).records[0]["work_order_id"] == late.work_order_id


def test_a_technician_sees_only_their_own_work_orders():
    w = world("rp5-wo-tech")
    contact = in_house(w)
    mine = issue(w, "machine", w.machine, "Mine", contact=contact)
    issue(w, "machine", w.other, "Not mine")
    direct = work_orders.create_work_order(w.manager, w.space, subject_type="bookable_space", subject=w.room,
                                           title="Paint", assignee=w.tech)
    seen = set(ids(rr.build_work_orders(w.space.pk, actor=w.tech), "work_order_id"))
    assert seen == {mine.work_order_id, direct.pk}
    assert all(row["assigned"] for row in rr.build_work_orders(w.space.pk, actor=w.tech).records)


def test_a_machine_manager_sees_only_their_machine_types():
    w = world("rp5-mm")
    manager = machine_manager(w, w.kind)
    laser = issue(w, "machine", w.machine, "Laser")
    issue(w, "machine", w.other, "CNC")
    issue(w, "bookable_space", w.room, "Room")
    issue(w, "inventory_product", w.product, "Item")
    assert ids(rr.build_work_orders(w.space.pk, actor=manager), "work_order_id") == [laser.work_order_id]
    assert {(row["area"], row["machine_type"]) for row in rr.build_repair_time(w.space.pk, actor=manager).records} \
        == {("machines", "Laser")}


def test_the_inventory_and_booking_managers_see_their_own_area_only():
    w = world("rp5-areas")
    issue(w, "machine", w.machine, "Laser")
    item = issue(w, "inventory_product", w.product, "Item")
    room = issue(w, "bookable_space", w.room, "Room")
    assert ids(rr.build_work_orders(w.space.pk, actor=w.im), "work_order_id") == [item.work_order_id]
    booking_manager = role(w, "booking_manager")
    assert ids(rr.build_work_orders(w.space.pk, actor=booking_manager), "work_order_id") == [room.work_order_id]
    assert {row["area"] for row in rr.build_repair_time(w.space.pk, actor=booking_manager).records} == {"rooms"}


def test_rows_follow_the_switches_of_each_area():
    from tests.maintenance.l16_helpers import switch
    w = world("rp5-switch")
    issue(w, "machine", w.machine, "Laser")
    room = issue(w, "bookable_space", w.room, "Room")
    switch(w.space, off=("machines.repairs", "machines.maintenance"))
    w.space.refresh_from_db()
    assert ids(rr.build_work_orders(w.space.pk, actor=w.manager), "work_order_id") == [room.work_order_id]


def test_technician_workload_counts_open_started_overdue_and_fixed():
    w = world("rp5-load")
    contact = in_house(w)
    started = issue(w, "machine", w.machine, "Started", contact=contact)
    set_issue(started, state="in_progress")
    late = issue(w, "machine", w.machine, "Late", contact=contact)
    set_due(late, -1)
    fixed = issue(w, "machine", w.machine, "Fixed", contact=contact)
    set_issue(fixed, state="fixed", fixed_at=hours_ago(2))
    old = issue(w, "machine", w.machine, "Fixed long ago", contact=contact)
    set_issue(old, state="closed", fixed_at=timezone.now() - timedelta(days=40))
    from apps.maintenance.repairs import services_issues as svc
    svc.assign(w.manager, issue(w, "bookable_space", w.room, "Self"), myself=True)
    window = (timezone.now() - timedelta(days=7), timezone.now() + timedelta(minutes=1))
    rows = {row["technician"]: row for row in
            rr.build_technician_workload(w.space.pk, actor=w.manager, date_range=window).records}
    tess = rows["Tess Tech"]
    assert (tess["technician_kind"], tess["open_jobs"], tess["in_progress"], tess["overdue"],
            tess["fixed_in_period"]) == ("in_house", 2, 1, 1, 1)
    staff_rows = [row for name, row in rows.items() if name != "Tess Tech"]
    assert len(staff_rows) == 1 and staff_rows[0]["technician_kind"] == "staff"
    assert staff_rows[0]["open_jobs"] == 1
    assert "@" not in staff_rows[0]["technician"]
    everything = rr.build_technician_workload(w.space.pk, actor=w.manager).records
    assert next(row for row in everything if row["technician"] == "Tess Tech")["fixed_in_period"] == 2


def test_a_technician_workload_shows_only_their_own_jobs():
    w = world("rp5-load-tech")
    contact = in_house(w)
    issue(w, "machine", w.machine, "Mine", contact=contact)
    from tests.maintenance.l16_helpers import external
    issue(w, "machine", w.other, "Theirs", contact=external(w))
    assert ids(rr.build_technician_workload(w.space.pk, actor=w.tech), "technician") == ["Tess Tech"]


def test_repair_time_averages_and_medians_per_area_and_machine_type():
    w = world("rp5-time")
    now = timezone.now()
    for hours in (2, 4, 9):
        row = issue(w, "machine", w.machine, f"Fix {hours}")
        set_issue(row, state="fixed", created_at=now - timedelta(hours=hours + 1), fixed_at=now - timedelta(hours=1))
    issue(w, "machine", w.machine, "Still open")
    room = issue(w, "bookable_space", w.room, "Room")
    set_issue(room, state="closed", created_at=now - timedelta(hours=2), fixed_at=now - timedelta(hours=1))
    rows = {(row["area"], row["machine_type"]): row for row in rr.build_repair_time(w.space.pk, actor=w.manager).records}
    laser = rows[("machines", "Laser")]
    assert (laser["reported"], laser["fixed"], laser["open"]) == (4, 3, 1)
    assert laser["average_hours_to_fix"] == 5.0 and laser["median_hours_to_fix"] == 4.0
    assert rows[("rooms", None)]["median_hours_to_fix"] == 1.0
    window = (now + timedelta(minutes=1), None)
    later = {(row["area"], row["machine_type"]): row
             for row in rr.build_repair_time(w.space.pk, actor=w.manager, date_range=window).records}
    assert later[("machines", "Laser")]["fixed"] == 0 and later[("machines", "Laser")]["average_hours_to_fix"] is None
    assert later[("machines", "Laser")]["open"] == 1


def test_parts_used_and_needed_are_summed_per_part_in_the_period():
    w = world("rp5-parts")
    first = issue(w, "inventory_product", w.product, "One")
    second = issue(w, "inventory_product", w.product, "Two")
    RepairPart.objects.create(issue=first, kind="used", product=w.product, name="Tip", quantity=2)
    RepairPart.objects.create(issue=second, kind="used", product=w.product, name="Tip", quantity=3)
    RepairPart.objects.create(issue=second, kind="needed", name="Heater", quantity=1)
    machine = issue(w, "machine", w.machine, "Laser")
    RepairPart.objects.create(issue=machine, kind="needed", name="Lens", quantity=1)
    result = rr.build_parts_used(w.space.pk, actor=w.im)
    assert [(row["kind"], row["part"], row["quantity"], row["issues"]) for row in result.records] == [
        ("used", "Tip", 5, 2), ("needed", "Heater", 1, 1)]
    assert result.records[0]["product_id"] == w.product.pk and result.records[0]["area"] == "inventory"
    future = (timezone.now() + timedelta(minutes=1), None)
    assert rr.build_parts_used(w.space.pk, actor=w.manager, date_range=future).records == []


def test_no_viewer_means_no_rows():
    w = world("rp5-none")
    issue(w, "machine", w.machine, "Laser")
    for builder in (rr.build_work_orders, rr.build_technician_workload, rr.build_repair_time, rr.build_parts_used):
        assert builder(w.space.pk).records == []
