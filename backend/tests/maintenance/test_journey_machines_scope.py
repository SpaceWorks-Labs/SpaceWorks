"""Machines journey (0.12.0): per-type reach in audit rows, and machine-time booking reports.

* A type-scoped Machine Manager who also reads audit (combined with Inventory Manager)
  reads only the machine-area rows of the types they are linked to; the Space Manager
  still reads every row; a machine row that names no machine or type fails closed.
* A problem reported from a booking of one machine's time is filed on THAT machine (the
  machines area), so it reaches the machine's type-scoped manager; with machine reporting
  off it stays a room report.
"""

import pytest

from apps.audit import services as audit
from apps.bookings.models import BookableSpace
from apps.bookings.services_bookings import create_booking
from apps.maintenance.models import IssueReport
from tests.audit_explorer_helpers import client_for, superadmin
from tests.fixed_roles.helpers import staff_account
from tests.machines.certification_helpers import _member
from tests.maintenance.l16_helpers import switch, tomorrow, world
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db
AUDIT = "/api/v1/admin/audit-logs"


def _seen(actor, space):
    response = client_for(actor).get(AUDIT, {"makerspace": space.pk})
    assert response.status_code == 200, response.data
    return {row["action"] for row in response.data["results"]}


def test_audit_machine_rows_follow_the_readers_machine_types():
    w = world("jm-audit")
    root = superadmin("jm-audit-root")
    audit.record(root, "machine.status_changed", makerspace=w.space, target=w.machine)
    audit.record(root, "machine_downtime.started", makerspace=w.space, target=w.other)
    audit.record(root, "machine_type.policy_updated", makerspace=w.space, target=w.space,
                 meta={"machine_type_id": w.other_kind.pk})
    audit.record(root, "machine.created", makerspace=w.space, target=w.space)  # names nothing
    laser = staff_account(w.space, "jm-audit-laser", "inventory_manager", "machine_manager",
                          machine_types=[w.kind])
    cnc = staff_account(w.space, "jm-audit-cnc", "inventory_manager", "machine_manager",
                        machine_types=[w.other_kind])
    unlinked = staff_account(w.space, "jm-audit-none", "inventory_manager", "machine_manager")
    owner = staff_account(w.space, "jm-audit-sm", "space_manager")
    assert _seen(laser, w.space) == {"machine.status_changed"}
    assert _seen(cnc, w.space) == {"machine_downtime.started", "machine_type.policy_updated"}
    assert _seen(unlinked, w.space) == set()
    assert {"machine.status_changed", "machine_downtime.started", "machine_type.policy_updated",
            "machine.created"} <= _seen(owner, w.space)


def _machine_booking(slug):
    w = world(slug)
    switch(w.space, on=("machines.time_booking",))
    time = BookableSpace.objects.create(makerspace=w.space, name="Laser A time", machine=w.machine,
                                        machine_type=w.kind, approval_mode=BookableSpace.ApprovalMode.INSTANT)
    member, _ = _member(w.space, f"{slug}-member")
    start, end = tomorrow()
    booking = create_booking(time, member=member, actor=member, starts_at=start, ends_at=end)
    return w, member, booking


def _report(member, w, booking):
    return authenticated_client(member).post("/api/v1/member/issues", {
        "makerspace_id": w.space.pk, "booking_id": booking.pk, "title": "Tube flickers",
        "description": "The laser tube flickers and cuts unevenly."}, format="json")


def test_a_machine_time_booking_reports_on_the_machine_and_reaches_its_type_manager():
    w, member, booking = _machine_booking("jm-book")
    response = _report(member, w, booking)
    assert response.status_code == 201, response.content
    issue = IssueReport.objects.get(pk=response.json()["id"])
    assert (issue.area, issue.subject_type, issue.machine_id, issue.booking_id) == (
        "machines", "machine", w.machine.pk, booking.pk)
    laser = staff_account(w.space, "jm-book-laser", "machine_manager", machine_types=[w.kind])
    cnc = staff_account(w.space, "jm-book-cnc", "machine_manager", machine_types=[w.other_kind])
    assert authenticated_client(laser).get(f"/api/v1/admin/issues/{issue.pk}").status_code == 200
    assert authenticated_client(cnc).get(f"/api/v1/admin/issues/{issue.pk}").status_code == 404


def test_with_machine_reporting_off_a_machine_time_booking_stays_a_room_report():
    w, member, booking = _machine_booking("jm-book-off")
    switch(w.space, off=("machines.issue_reporting",))
    response = _report(member, w, booking)
    assert response.status_code == 201, response.content
    issue = IssueReport.objects.get(pk=response.json()["id"])
    assert (issue.area, issue.subject_type, issue.room_id) == ("rooms", "bookable_space", booking.space_id)
