"""L16 (#95, #128 C-8/C-9): per-parent switches, their prerequisites, off = 404, purge."""

import pytest

from rest_framework.exceptions import NotFound

from apps.maintenance import work_orders
from apps.maintenance.models import IssueReport, WorkOrder
from apps.maintenance.repairs import services_issues as svc
from apps.maintenance.repairs.report_scope import visible_work_orders
from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.capability_purge import preview, purge_capability
from tests.maintenance.l16_helpers import loan, switch, world
from tests.return_helpers import authenticated_client, make_user

pytestmark = pytest.mark.django_db
KEYS = ("machines.repairs", "machines.issue_reporting", "inventory.maintenance", "inventory.repairs",
        "inventory.issue_reporting", "bookings.room_maintenance", "bookings.room_repairs", "bookings.issue_reporting")


def test_every_reserved_key_is_now_a_visible_switch_and_repairs_need_maintenance():
    for key in KEYS:
        definition = FEATURES[key]
        assert definition.frontend_exposed and "Reserved" not in definition.description, key
        assert not definition.default_enabled
    assert FEATURES["machines.repairs"].requires_features == ("machines.maintenance",)
    assert FEATURES["inventory.repairs"].requires_features == ("inventory.maintenance",)
    assert FEATURES["bookings.room_repairs"].requires_features == ("bookings.room_maintenance",)


def test_with_every_switch_off_the_staff_surfaces_answer_404_and_keep_data():
    w = world("l16-sw")
    svc.open_issue(w.manager, w.space, subject_type="machine", subject=w.machine, title="Noise")
    switch(w.space, off=KEYS + ("machines.maintenance",))
    client = authenticated_client(w.manager)
    for path in ("issues", "technicians", "my-jobs", "subject-maintenance", "technician-defaults"):
        assert client.get(f"/api/v1/admin/makerspaces/{w.space.pk}/{path}").status_code == 404, path
    assert IssueReport.objects.filter(makerspace=w.space).count() == 1


def test_one_parent_off_hides_only_its_own_issues():
    w = world("l16-sw-parent")
    machine = svc.open_issue(w.manager, w.space, subject_type="machine", subject=w.machine, title="Noise")
    room = svc.open_issue(w.manager, w.space, subject_type="bookable_space", subject=w.room, title="Leak")
    switch(w.space, off=("machines.repairs", "machines.issue_reporting"))
    rows = authenticated_client(w.manager).get(f"/api/v1/admin/makerspaces/{w.space.pk}/issues").json()["results"]
    assert [row["id"] for row in rows] == [room.pk] and machine.pk not in [row["id"] for row in rows]


@pytest.mark.parametrize(("subject_type", "subject_name", "feature"), [
    ("machine", "machine", "machines.repairs"),
    ("inventory_product", "product", "inventory.repairs"),
    ("bookable_space", "room", "bookings.room_repairs"),
])
def test_retained_repair_orders_obey_switch_in_maintenance_and_reports(subject_type, subject_name, feature):
    w = world("l16-retained")
    subject = getattr(w, subject_name)
    repair = svc.open_issue(w.manager, w.space, subject_type=subject_type, subject=subject, title="Repair")
    ordinary = work_orders.create_work_order(w.manager, w.space, subject_type=subject_type,
                                             subject=subject, title="Routine maintenance")
    other_type, other_subject = ("bookable_space", w.room) if subject_type == "machine" else ("machine", w.other)
    unrelated = svc.open_issue(w.manager, w.space, subject_type=other_type, subject=other_subject,
                               title="Other repair")
    client = authenticated_client(w.manager)
    path = f"/api/v1/admin/makerspaces/{w.space.pk}/work-orders"
    switch(w.space, off=(feature,))
    request, borrower = loan(w)
    report_only = svc.file_report(w.space, reporter=borrower, source="loan", origin=request,
                                  subject_type="inventory_product", subject=w.product,
                                  title="Notify-only report", description="Loose handle", validated=[])

    visible = {row["id"] for row in client.get(path).json()}
    assert ordinary.pk in visible and repair.work_order_id not in visible
    assert unrelated.work_order_id in visible
    reported = set(visible_work_orders(w.manager, w.space).values_list("pk", flat=True))
    assert ordinary.pk in reported and repair.work_order_id not in reported
    assert unrelated.work_order_id in reported
    issue_path = f"/api/v1/admin/makerspaces/{w.space.pk}/issues"
    issues = {row["id"] for row in client.get(issue_path).json()["results"]}
    assert repair.pk not in issues and unrelated.pk in issues and report_only.pk in issues
    assert client.get(f"/api/v1/admin/issues/{repair.pk}").status_code == 404
    assert client.get(f"/api/v1/admin/issues/{report_only.pk}").status_code == 200
    for endpoint, payload in (("status", {"status": "in_progress"}), ("assign", {"assignee_id": w.manager.pk})):
        response = client.post(f"/api/v1/admin/work-orders/{repair.work_order_id}/{endpoint}", payload,
                               format="json")
        assert response.status_code == 404
    with pytest.raises(NotFound):
        work_orders.move(w.manager, repair.work_order, "in_progress")
    with pytest.raises(NotFound):
        work_orders.assign(w.manager, repair.work_order, w.manager)
    assert WorkOrder.objects.get(pk=repair.work_order_id).status == "open"
    work_orders.move(w.manager, ordinary, "in_progress")
    switch(w.space, on=(feature,))
    assert repair.work_order_id in {row["id"] for row in client.get(path).json()}
    assert client.get(f"/api/v1/admin/issues/{repair.pk}").status_code == 200
    work_orders.move(w.manager, repair.work_order, "in_progress")


def test_a_superadmin_purges_one_parents_repair_records_after_it_is_switched_off():
    w = world("l16-purge")
    svc.open_issue(w.manager, w.space, subject_type="machine", subject=w.machine, title="Noise")
    room = svc.open_issue(w.manager, w.space, subject_type="bookable_space", subject=w.room, title="Leak")
    assert preview(w.space, "machines.repairs")["issues"] == 1
    root = make_user("l16-purge-root", role="superadmin")
    switch(w.space, off=("machines.repairs",))
    w.space.refresh_from_db()
    purge_capability(w.space, "machines.repairs", root)
    assert list(IssueReport.objects.filter(makerspace=w.space).values_list("pk", flat=True)) == [room.pk]
