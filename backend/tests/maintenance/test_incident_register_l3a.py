"""Release 0.12.0 L3a (decision 223): the safety incident register."""

from types import SimpleNamespace

import pytest
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.test import APIClient

from apps.accounts.rbac import Action
from apps.audit.models import AuditLog
from apps.machines.models import Machine
from apps.maintenance.incidents import services
from apps.maintenance.incidents.models import Incident
from apps.maintenance.incidents.scope import visible_incidents
from tests.machines.certification_helpers import _machine_type, _manager, _member, _space

pytestmark = pytest.mark.django_db


def _world(slug="inc", feature=True):
    space = _space(slug, modules=("machines",), certifications=False)
    if feature:
        space.enabled_features = sorted(set(space.enabled_features or []) | {"safety.incidents"})
        space.save(update_fields=["enabled_features"])
    machine_type = _machine_type(space)
    machine = Machine.objects.create(makerspace=space, machine_type=machine_type, name="Saw")
    head, _ = _manager(space, f"{slug}-head", actions=(Action.MANAGE_MAKERSPACE,))
    machines_mgr, _ = _manager(space, f"{slug}-mm", machine_type)
    stock_mgr, _ = _manager(space, f"{slug}-stock", actions=(Action.EDIT_INVENTORY,))
    member, _ = _member(space, f"{slug}-member")
    return SimpleNamespace(space=space, type=machine_type, machine=machine, head=head, machines_mgr=machines_mgr,
                           stock_mgr=stock_mgr, member=member)


def test_member_reports_and_area_follows_the_link():
    w = _world()
    incident = services.report(w.member, w.space, title="Blade guard slipped", kind="near_miss", severity="high",
                               machine=w.machine, location="Wood shop")
    assert incident.reporter_id == w.member.pk and incident.area == Incident.Area.MACHINES
    assert incident.status == Incident.Status.REPORTED
    row = AuditLog.objects.get(action="incident.reported", target_id=str(incident.pk))
    assert row.meta["machine_id"] == w.machine.pk and row.meta["severity"] == "high"
    unplaced = services.report(w.member, w.space, title="Slippery floor")
    assert unplaced.area == Incident.Area.OTHER


def test_member_cannot_set_staff_only_fields_or_report_when_not_a_member():
    w = _world()
    with pytest.raises(PermissionDenied):
        services.report(w.member, w.space, title="x", sponsor_user=w.head)
    outsider, _ = _member(_space("inc-other", modules=("machines",)), "inc-outsider")
    with pytest.raises(PermissionDenied):
        services.report(outsider, w.space, title="Not mine")


def test_area_managers_read_only_their_own_area_and_other_is_space_manager_only():
    w = _world()
    on_machine = services.report(w.member, w.space, title="Machine", machine=w.machine)
    unplaced = services.report(w.member, w.space, title="Unplaced")
    lending = services.report(w.head, w.space, title="Lending", area="lending")
    assert set(visible_incidents(w.head, w.space)) == {on_machine, unplaced, lending}
    assert set(visible_incidents(w.machines_mgr, w.space)) == {on_machine}
    assert set(visible_incidents(w.stock_mgr, w.space)) == {lending}
    assert not visible_incidents(w.member, w.space).exists()


def test_triage_transitions_actions_and_area_authority():
    w = _world()
    incident = services.report(w.member, w.space, title="Burn", machine=w.machine, severity="medium")
    with pytest.raises(PermissionDenied):
        services.update(w.stock_mgr, incident, status="triaged")
    triaged = services.update(w.machines_mgr, incident, status="triaged", severity="high")
    assert triaged.status == "triaged" and triaged.severity == "high" and triaged.triaged_by_id == w.machines_mgr.pk
    action = services.add_action(w.machines_mgr, incident, description="Replace guard", assignee=w.machines_mgr)
    done = services.set_action_done(w.machines_mgr, action, done=True)
    assert done.done_at is not None and done.done_by_id == w.machines_mgr.pk
    services.update(w.machines_mgr, incident, status="resolved", resolution_note="Guard replaced")
    closed = services.update(w.machines_mgr, incident, status="closed")
    assert closed.closed_at is not None
    with pytest.raises(ValidationError):
        services.update(w.head, incident, status="in_progress")  # closed is final
    actions = set(AuditLog.objects.filter(target_id=str(incident.pk)).values_list("action", flat=True))
    assert {"incident.reported", "incident.status_changed", "incident.updated"} <= actions


def test_record_incident_is_the_trusted_hook_and_inert_when_off():
    w = _world()
    guest, _ = _member(_space("inc-guest-home", modules=("machines",)), "inc-guest")
    recorded = services.record_incident(
        w.space, title="Guest dropped a tool", severity="medium", sponsor_user=guest, machine=w.machine, actor=None)
    assert recorded.sponsor_user_id == guest.pk and recorded.reporter_id is None
    off = _world("inc-off", feature=False)
    assert services.record_incident(off.space, title="Nothing") is None
    assert not Incident.objects.filter(makerspace=off.space).exists()
    with pytest.raises(NotFound):
        services.report(off.member, off.space, title="Off")


def test_incident_api_member_report_and_staff_register():
    w = _world()
    member = APIClient()
    member.force_authenticate(w.member)
    url = f"/api/v1/member/makerspaces/{w.space.pk}/incidents"
    created = member.post(url, {"title": "Spark", "kind": "near_miss", "machine_id": w.machine.pk}, format="json")
    assert created.status_code == 201 and created.json()["area"] == "machines"
    assert member.get(url).json()["count"] == 1
    staff = APIClient()
    staff.force_authenticate(w.machines_mgr)
    listed = staff.get(f"/api/v1/admin/makerspaces/{w.space.pk}/incidents").json()
    assert [row["title"] for row in listed["results"]] == ["Spark"]
    incident_id = listed["results"][0]["id"]
    patched = staff.patch(f"/api/v1/admin/incidents/{incident_id}", {"status": "triaged"}, format="json")
    assert patched.status_code == 200 and patched.json()["status"] == "triaged"
    added = staff.post(f"/api/v1/admin/incidents/{incident_id}/actions", {"description": "Brief the crew"}, format="json")
    assert added.status_code == 201
    other = APIClient()
    other.force_authenticate(w.stock_mgr)
    assert other.get(f"/api/v1/admin/incidents/{incident_id}").status_code == 404
