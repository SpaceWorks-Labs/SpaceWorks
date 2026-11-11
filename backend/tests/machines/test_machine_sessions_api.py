"""L23 (#158): member and staff session routes, the switch, scoping and the type setting."""

from datetime import timedelta

import pytest

from apps.machines.models import MachineSession, MachineUsageEntry, MakerspaceMachineTypePolicy
from tests.machines.session_helpers import features, open_session, session_world
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def member_routes(machine_id, session_id=1):
    return [("get", f"/api/v1/member/machines/{machine_id}/session"),
            ("post", f"/api/v1/member/machines/{machine_id}/sessions/start"),
            ("get", "/api/v1/member/machine-sessions?makerspace=%s"),
            ("post", f"/api/v1/member/machine-sessions/{session_id}/stop")]


def test_member_previews_starts_lists_and_stops():
    w = session_world("api-member")
    client = authenticated_client(w.member)
    preview = client.get(f"/api/v1/member/machines/{w.machines[0].pk}/session")
    assert preview.status_code == 200, preview.content
    body = preview.json()
    assert body["can_start"] and body["billing"] and body["rate"]["unit_amount"] == "120.00"
    assert (body["rate"]["increment"], body["rate"]["minimum"], body["max_minutes"]) == (15, 30, 240)
    started = client.post(f"/api/v1/member/machines/{w.machines[0].pk}/sessions/start", {"digest": body["digest"]},
                          format="json")
    assert started.status_code == 201, started.content
    session = started.json()
    assert (session["status"], session["source"], session["charge_state"]) == ("live", "member_qr", "running")
    again = client.get(f"/api/v1/member/machines/{w.machines[0].pk}/session").json()
    assert not again["can_start"] and again["refusal"]["code"] == "session_already_live"
    assert again["live_session"]["id"] == session["id"]
    listed = client.get("/api/v1/member/machine-sessions?live=1").json()
    assert [row["id"] for row in listed] == [session["id"]]
    stopped = client.post(f"/api/v1/member/machine-sessions/{session['id']}/stop")
    assert stopped.status_code == 200 and stopped.json()["status"] == "closed"
    assert stopped.json()["charge_state"] in ("free", "raised")


def test_a_refusal_is_typed_on_start():
    w = session_world("api-refuse", checked_in=False)
    response = authenticated_client(w.member).post(f"/api/v1/member/machines/{w.machines[0].pk}/sessions/start",
                                                   {}, format="json")
    assert response.status_code == 409 and response.json()["code"] == "presence_required"


def test_switch_off_hides_every_route_and_keeps_the_data_and_manual_usage():
    w = session_world("api-off")
    row = open_session(w)
    features(w.space, remove={"machines.sessions"})
    member = authenticated_client(w.member)
    for method, path in member_routes(w.machines[0].pk, row.pk):
        response = getattr(member, method)(path.replace("%s", str(w.space.pk)))
        if "machine-sessions?" in path:
            assert response.status_code == 200 and response.json() == []
        else:
            assert response.status_code == 404, (path, response.status_code)
    staff = authenticated_client(w.staff)
    assert staff.get(f"/api/v1/admin/makerspaces/{w.space.pk}/machine-sessions").status_code == 404
    assert staff.post(f"/api/v1/admin/machine-sessions/{row.pk}/stop").status_code == 404
    assert MachineSession.objects.filter(pk=row.pk).exists()
    manual = staff.post(f"/api/v1/admin/machines/{w.machines[0].pk}/usage", {"hours": "1.50", "note": "manual"},
                        format="json")
    assert manual.status_code in (200, 201), manual.content
    assert MachineUsageEntry.objects.filter(machine=w.machines[0], source="manual").exists()


def test_a_stranger_cannot_see_the_machine():
    w = session_world("api-stranger")
    from tests.machines.eta_helpers import owner
    response = authenticated_client(owner("api-stranger-x")).get(f"/api/v1/member/machines/{w.machines[0].pk}/session")
    assert response.status_code == 404


def test_staff_start_stop_list_and_review_flow():
    w = session_world("api-staff")
    staff = authenticated_client(w.staff)
    base = f"/api/v1/admin/makerspaces/{w.space.pk}/machine-sessions"
    created = staff.post(base, {"machine_id": w.machines[0].pk, "member_id": w.member.pk}, format="json")
    assert created.status_code == 201, created.content
    session_id = created.json()["id"]
    assert created.json()["source"] == "staff" and created.json()["member_name"]
    live = staff.get(base + "?status=live").json()
    assert live["count"] == 1 and live["results"][0]["id"] == session_id
    from apps.machines.sessions_service import stop
    stop(MachineSession.objects.get(pk=session_id), actor=None, reason="max_length",
         at=MachineSession.objects.get(pk=session_id).started_at + timedelta(minutes=240))
    review = staff.get(base + "?status=review").json()
    assert [row["id"] for row in review["results"]] == [session_id] and review["results"][0]["needs_review"]
    amended = staff.post(f"/api/v1/admin/machine-sessions/{session_id}/amend", {"minutes": 50, "reason": "Left early"},
                         format="json")
    assert amended.status_code == 200 and amended.json()["minutes"] == 50
    confirmed = staff.post(f"/api/v1/admin/machine-sessions/{session_id}/confirm")
    assert confirmed.status_code == 200, confirmed.content
    assert confirmed.json()["charge_state"] == "raised" and confirmed.json()["payment"]["amount"] == "120.00"
    assert staff.get(base + "?status=review").json()["count"] == 0
    assert staff.post(f"/api/v1/admin/machine-sessions/{session_id}/confirm").json()["code"] == "session_final"


def test_a_machine_manager_of_another_type_cannot_act():
    from apps.machines.models import Machine, MachineType
    from tests.machines.test_machine_scope_authorization import _manager
    w = session_world("api-scope")
    other_type = MachineType.objects.create(makerspace=w.space, slug="api-scope-cnc", name="CNC")
    Machine.objects.create(makerspace=w.space, machine_type=other_type, name="CNC A")
    manager = _manager(w.space, "api-scope-cnc-manager", machine_type=other_type)
    row = open_session(w)
    client = authenticated_client(manager)
    listed = client.get(f"/api/v1/admin/makerspaces/{w.space.pk}/machine-sessions")
    assert listed.status_code == 200 and listed.json()["count"] == 0
    assert client.post(f"/api/v1/admin/machine-sessions/{row.pk}/stop").status_code == 403


def test_session_settings_per_type_through_the_settings_layer():
    w = session_world("api-settings")
    staff = authenticated_client(w.staff)
    url = f"/api/v1/admin/makerspaces/{w.space.pk}/machine-types/{w.kind.pk}/session-settings"
    assert staff.get(url).json() == {"session_max_minutes": 240}
    assert staff.put(url, {"session_max_minutes": 2}, format="json").status_code == 400
    changed = staff.put(url, {"session_max_minutes": 90}, format="json")
    assert changed.status_code == 200 and changed.json()["session_max_minutes"] == 90
    assert MakerspaceMachineTypePolicy.objects.get(makerspace=w.space, machine_type=w.kind).session_max_minutes == 90


def test_unattributed_device_session_is_assigned_then_confirmed():
    w = session_world("api-assign")
    row = open_session(w, member=None, source="device")
    from apps.machines.sessions_service import stop
    stop(row, actor=None, reason="device", minutes=35)
    staff = authenticated_client(w.staff)
    assert staff.post(f"/api/v1/admin/machine-sessions/{row.pk}/confirm").json()["code"] == "session_unattributed"
    assigned = staff.post(f"/api/v1/admin/machine-sessions/{row.pk}/assign",
                          {"member_id": w.member.pk, "reason": "Their print, per the log book."}, format="json")
    assert assigned.status_code == 200 and assigned.json()["member_id"] == w.member.pk
    confirmed = staff.post(f"/api/v1/admin/machine-sessions/{row.pk}/confirm").json()
    # Not billable: device sessions are billed through their job, never here.
    assert confirmed["status"] == "closed" and confirmed["charge_state"] == "none"
    assert MachineUsageEntry.objects.get(note=f"Machine session {row.pk}").member_id == w.member.pk
