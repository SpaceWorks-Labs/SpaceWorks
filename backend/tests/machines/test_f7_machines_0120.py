"""Decision 230 (d), lane F7: machines follow-ups. Written, not run (consolidation runs it)."""

from datetime import date
from types import SimpleNamespace

import pytest
from django.http import Http404

from apps.bookings import admission, admission_readiness, busy_overlay
from apps.machines import service_workflow_review as review
from apps.machines import supervised
from apps.machines.sessions_rules import SessionRefused
from apps.maintenance.repairs import views_maintenance

pytestmark = pytest.mark.django_db


def test_minor_cannot_open_supervised_session(monkeypatch):
    import apps.makerspaces.minors as minors
    monkeypatch.setattr("apps.makerspaces.community_policy.minors_on", lambda space: True)
    monkeypatch.setattr(minors, "is_minor", lambda profile, policy: True)
    monkeypatch.setattr(minors, "profile_for", lambda space, user: object())
    monkeypatch.setattr("apps.makerspaces.community_policy.policy_for", lambda space: object())
    with pytest.raises(SessionRefused) as refused:
        supervised._require_adult_instructor(SimpleNamespace(), SimpleNamespace())
    assert refused.value.code == "instructor_must_be_adult"


def test_adult_instructor_passes(monkeypatch):
    monkeypatch.setattr("apps.makerspaces.community_policy.minors_on", lambda space: False)
    supervised._require_adult_instructor(SimpleNamespace(), SimpleNamespace())


def test_resubmit_reruns_intake_gates(monkeypatch):
    calls = []
    monkeypatch.setattr("apps.machines.job_intake.require_member_job_gate", lambda *a: calls.append("gate"))
    monkeypatch.setattr("apps.machines.certifications.require_certification_for_member",
                        lambda *a, **k: calls.append("cert"))
    machine_type = SimpleNamespace()
    row = SimpleNamespace(queue_id=1, queue=SimpleNamespace(machine_type=machine_type), makerspace=object())
    review._require_intake_gates(row, object())
    assert calls == ["gate", "cert"]


def test_machine_linked_resource_takes_no_booking_with_time_booking_off(monkeypatch):
    monkeypatch.setattr("apps.makerspaces.platform.feature_enabled", lambda space, key: False)
    machine_space = SimpleNamespace(machine_id=7, makerspace=object())
    room = SimpleNamespace(machine_id=None, makerspace=object())
    assert admission.machine_time_booking_off(machine_space) is True
    assert admission.machine_time_booking_off(room) is False
    with pytest.raises(Exception):
        admission._refuse_machine_time_booking_off(machine_space)
    readiness = admission_readiness._time_booking(machine_space)
    assert readiness["state"] == admission_readiness.BLOCKED
    assert admission_readiness._time_booking(room) is None
    window = (date(2026, 1, 1), date(2026, 1, 2))
    assert busy_overlay._machine_time_booking_off(machine_space, *window)[0]["severity"] == busy_overlay.BLOCK
    assert busy_overlay._machine_time_booking_off(room, *window) == []


def test_technician_schedule_run_out_of_scope_is_404(monkeypatch):
    monkeypatch.setattr("apps.machines.access.can_manage_machine", lambda a, m: False)
    monkeypatch.setattr("apps.machines.access.can_operate_machine", lambda a, m: False)
    monkeypatch.setattr(views_maintenance.authority, "technician_on_machine", lambda a, m: False)
    with pytest.raises(Http404):
        views_maintenance._require_schedule_authority(object(), object())


def test_warranty_status_uses_space_local_date(monkeypatch):
    from apps.machines import serializers_machines as sm
    from django.utils import timezone
    from datetime import datetime, timezone as tz
    seen = []
    monkeypatch.setattr("apps.makerspaces.capability_eligibility.configuration_feature_enabled", lambda *a: True)
    monkeypatch.setattr(sm, "warranty_status", lambda warranty, today: seen.append(today) or "active")
    monkeypatch.setattr(timezone, "now", lambda: datetime(2026, 1, 1, 20, 0, tzinfo=tz.utc))
    obj = SimpleNamespace(makerspace=SimpleNamespace(timezone="Asia/Kolkata"), warranty=object())
    sm.MachineSerializer().get_warranty_status(obj)
    assert seen == [date(2026, 1, 2)]
