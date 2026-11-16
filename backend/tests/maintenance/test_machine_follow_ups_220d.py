"""Decision 220(d)1-2: a member reports a problem from a machine-time booking (the booking
payload says it is machine time) and from their own machine session (a `session` source
filed on that machine, so it reaches the machine type's manager)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.bookings.models import BookableSpace
from apps.bookings.services_bookings import create_booking
from apps.machines.models import MachineSession
from apps.maintenance.models import IssueReport
from tests.fixed_roles.helpers import staff_account
from tests.machines.certification_helpers import _member
from tests.maintenance.l16_helpers import switch, tomorrow, world
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db
REPORT = "/api/v1/member/issues"


def test_member_booking_payload_flags_machine_time():
    w = world("f220-time")
    switch(w.space, on=("machines.time_booking",))
    time = BookableSpace.objects.create(makerspace=w.space, name="Laser A time", machine=w.machine,
                                        machine_type=w.kind, approval_mode=BookableSpace.ApprovalMode.INSTANT)
    member, _ = _member(w.space, "f220-time-member")
    start, end = tomorrow()
    create_booking(time, member=member, actor=member, starts_at=start, ends_at=end)
    later = timedelta(hours=3)  # no overlap between the member's two bookings
    create_booking(w.room, member=member, actor=member, starts_at=start + later, ends_at=end + later)
    response = authenticated_client(member).get(f"/api/v1/public/{w.space.slug}/my-bookings/?period=upcoming")
    assert response.status_code == 200, response.content
    flags = {row["space_name"]: row["machine_time"] for row in response.json()["results"]}
    assert flags == {"Laser A time": True, "Wood shop": False}


def _session_world(slug, *, sessions=True):
    w = world(slug)
    if sessions:
        switch(w.space, on=("machines.sessions",))
    member, _ = _member(w.space, f"{slug}-member")
    now = timezone.now()
    session = MachineSession.objects.create(
        makerspace=w.space, machine=w.machine, machine_type=w.kind, member=member, source="member_qr",
        started_at=now - timedelta(hours=1), ended_at=now - timedelta(minutes=5), stop_reason="member",
        duration_minutes=55)
    return w, member, session


def _report(member, w, session):
    return authenticated_client(member).post(REPORT, {
        "makerspace_id": w.space.pk, "machine_session_id": session.pk, "title": "Bed not level",
        "description": "The bed drifted during my session."}, format="json")


def test_a_session_report_files_on_the_machine_and_reaches_its_type_manager():
    w, member, session = _session_world("f220-sess")
    response = _report(member, w, session)
    assert response.status_code == 201, response.content
    issue = IssueReport.objects.get(pk=response.json()["id"])
    assert (issue.source, issue.area, issue.subject_type, issue.machine_id, issue.machine_session_id) == (
        "session", "machines", "machine", w.machine.pk, session.pk)
    laser = staff_account(w.space, "f220-sess-laser", "machine_manager", machine_types=[w.kind])
    cnc = staff_account(w.space, "f220-sess-cnc", "machine_manager", machine_types=[w.other_kind])
    assert authenticated_client(laser).get(f"/api/v1/admin/issues/{issue.pk}").status_code == 200
    assert authenticated_client(cnc).get(f"/api/v1/admin/issues/{issue.pk}").status_code == 404


def test_only_the_sessions_member_reports_and_only_while_both_switches_are_on():
    w, member, session = _session_world("f220-sess-gate")
    other, _ = _member(w.space, "f220-sess-gate-other")
    assert _report(other, w, session).status_code in (400, 403, 404)
    switch(w.space, off=("machines.sessions",))
    assert _report(member, w, session).status_code in (400, 403, 404)
    switch(w.space, on=("machines.sessions",), off=("machines.issue_reporting",))
    assert _report(member, w, session).status_code in (400, 403, 404)
    assert not IssueReport.objects.filter(machine_session=session).exists()


def test_a_session_is_one_source_only():
    w, member, session = _session_world("f220-sess-one")
    response = authenticated_client(member).post(REPORT, {
        "makerspace_id": w.space.pk, "machine_session_id": session.pk, "machine_job_id": 1,
        "title": "x", "description": "y"}, format="json")
    assert response.status_code == 400
