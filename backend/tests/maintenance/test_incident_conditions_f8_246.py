"""Decision 246 (lane F8): idempotency conditions for the incident register (223)."""
import pytest
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.maintenance.incidents import services
from apps.maintenance.incidents.models import Incident, IncidentAction
from tests.maintenance.test_incident_register_l3a import _world

pytestmark = pytest.mark.django_db


def _count(incident, action):
    return AuditLog.objects.filter(target_id=str(incident.pk), action=action).count()


def test_repeating_the_same_triage_status_changes_nothing_and_writes_no_second_audit_row():
    w = _world("f8-inc-status")
    incident = services.report(w.member, w.space, title="Burn", machine=w.machine, severity="medium")
    services.update(w.machines_mgr, incident, status="triaged")
    stamp = Incident.objects.get(pk=incident.pk).updated_at
    again = services.update(w.machines_mgr, incident, status="triaged")
    assert again.status == "triaged"
    assert _count(incident, "incident.status_changed") == 1
    assert Incident.objects.get(pk=incident.pk).updated_at == stamp


def test_repeating_the_same_field_edit_is_a_no_op():
    w = _world("f8-inc-edit")
    incident = services.report(w.member, w.space, title="Burn", machine=w.machine, severity="low")
    services.update(w.machines_mgr, incident, severity="high")
    assert _count(incident, "incident.updated") == 1
    services.update(w.machines_mgr, incident, severity="high")
    assert _count(incident, "incident.updated") == 1
    assert Incident.objects.get(pk=incident.pk).severity == "high"


def test_a_closed_incident_is_final_and_a_repeat_close_is_refused_without_a_new_row():
    w = _world("f8-inc-final")
    incident = services.report(w.member, w.space, title="Burn", machine=w.machine)
    for status in ("triaged", "resolved", "closed"):
        services.update(w.machines_mgr, incident, status=status)
    closed_at = Incident.objects.get(pk=incident.pk).closed_at
    rows = _count(incident, "incident.status_changed")
    services.update(w.machines_mgr, incident, status="closed")  # same status: no transition, no row
    assert _count(incident, "incident.status_changed") == rows
    with pytest.raises(ValidationError):
        services.update(w.head, incident, status="triaged")
    assert Incident.objects.get(pk=incident.pk).closed_at == closed_at


def test_marking_an_action_done_twice_leaves_it_done_and_marking_undone_clears_it():
    w = _world("f8-inc-action")
    incident = services.report(w.member, w.space, title="Burn", machine=w.machine)
    action = services.add_action(w.machines_mgr, incident, description="Replace guard")
    services.set_action_done(w.machines_mgr, action, done=True)
    services.set_action_done(w.machines_mgr, action, done=True)
    row = IncidentAction.objects.get(pk=action.pk)
    assert row.done_at is not None and row.done_by_id == w.machines_mgr.pk
    services.set_action_done(w.machines_mgr, action, done=False)
    row.refresh_from_db()
    assert row.done_at is None and row.done_by_id is None
    assert IncidentAction.objects.filter(incident=incident).count() == 1


def test_the_trusted_hook_called_twice_records_two_incidents_not_one_shared_row():
    """`record_incident` has no operation key: callers dedupe; it must never merge or overwrite rows."""
    w = _world("f8-inc-hook")
    first = services.record_incident(w.space, title="Dropped tool", severity="medium", machine=w.machine)
    second = services.record_incident(w.space, title="Dropped tool", severity="medium", machine=w.machine)
    assert first.pk != second.pk
    assert Incident.objects.filter(makerspace=w.space, title="Dropped tool").count() == 2
