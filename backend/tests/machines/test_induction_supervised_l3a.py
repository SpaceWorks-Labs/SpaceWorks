"""Release 0.12.0 L3a (decision 223): induction events and supervised workshop sessions."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.events.models import EventRegistration
from apps.machines import induction, supervised
from apps.machines.models import (
    CertificationGrant, EventInductionLink, GuestCertificationGrant, Machine, MachineSession, SupervisedUse,
)
from apps.machines.sessions_rules import SessionRefused
from tests.events.checkin_helpers import make_event, register
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import make_user
from tests.machines.certification_helpers import _certification, _machine_type, _manager, _member, _space

pytestmark = pytest.mark.django_db

FEATURES = {"machines.induction_events", "machines.supervised_sessions"}


def _world(slug="l3a"):
    space = _space(slug, modules=("machines", "events"))
    space.enabled_features = sorted(set(space.enabled_features or []) | FEATURES)
    space.save(update_fields=["enabled_features"])
    machine_type = _machine_type(space)
    cert = _certification(space, machine_type)
    machine = Machine.objects.create(makerspace=space, machine_type=machine_type, name="Laser A")
    manager, _ = _manager(space, f"{slug}-mgr", machine_type)
    return SimpleNamespace(space=space, type=machine_type, cert=cert, machine=machine, manager=manager)


def _attended(w, user):
    event = make_event(w.space, starts_at=timezone.now() - timedelta(hours=1), ends_at=timezone.now() + timedelta(hours=1))
    register(event, user, status=EventRegistration.Status.ATTENDED)
    return event


def _induction_event(w, user):
    event = _attended(w, user)
    induction.link(event, w.cert, actor=w.manager)
    return event


def test_link_then_grant_to_member_audits_event_as_source():
    w = _world()
    user, membership = _member(w.space, "l3a-attendee")
    event = _induction_event(w, user)
    results = induction.grant_from_induction(event, [user.pk], actor=w.manager)
    assert [r["status"] for r in results] == ["granted"]
    grant = CertificationGrant.objects.get(membership=membership, certification_type=w.cert)
    row = AuditLog.objects.filter(action="certification.granted", target_id=str(grant.pk)).get()
    assert row.meta["source_event_id"] == event.pk
    assert induction.holds_certification(user, w.type, w.space)
    # A second click does not double-grant.
    again = induction.grant_from_induction(event, [user.pk], actor=w.manager)
    assert again[0]["status"] == "already_certified"
    assert CertificationGrant.objects.filter(membership=membership).count() == 1


def test_only_checked_in_attendees_and_linked_events_can_be_granted():
    w = _world()
    user, _ = _member(w.space, "l3a-absent")
    event = make_event(w.space, starts_at=timezone.now() - timedelta(hours=1), ends_at=timezone.now() + timedelta(hours=1))
    register(event, user, status=EventRegistration.Status.REGISTERED)
    with pytest.raises(ValidationError):  # not an induction event yet
        induction.grant_from_induction(event, [user.pk], actor=w.manager)
    induction.link(event, w.cert, actor=w.manager)
    with pytest.raises(ValidationError):  # registered, never checked in
        induction.grant_from_induction(event, [user.pk], actor=w.manager)
    assert not CertificationGrant.objects.exists()


def test_grant_refused_before_event_starts_and_without_authority():
    w = _world()
    user, _ = _member(w.space, "l3a-early")
    future = make_event(w.space, starts_at=timezone.now() + timedelta(days=1), ends_at=timezone.now() + timedelta(days=2))
    register(future, user, status=EventRegistration.Status.ATTENDED)
    induction.link(future, w.cert, actor=w.manager)
    with pytest.raises(ValidationError):
        induction.grant_from_induction(future, [user.pk], actor=w.manager)
    event = _induction_event(w, user)
    other, _ = _member(w.space, "l3a-nobody")
    with pytest.raises(PermissionDenied):
        induction.link(event, w.cert, actor=other)
    with pytest.raises(PermissionDenied):
        induction.grant_from_induction(event, [user.pk], actor=other)


def test_switch_off_leaves_no_surface():
    w = _world()
    w.space.enabled_features = sorted(set(w.space.enabled_features) - {"machines.induction_events"})
    w.space.save(update_fields=["enabled_features"])
    event = make_event(w.space)
    with pytest.raises(NotFound):
        induction.link(event, w.cert, actor=w.manager)


def test_guest_pass_holder_is_certified_through_the_narrow_path(monkeypatch):
    w = _world()
    guest = make_user("l3a-guest", access_status=User.AccessStatus.ACTIVE)  # an account with no membership
    event = _induction_event(w, guest)
    monkeypatch.setattr(induction, "guest_pass_window", lambda *a, **k: None)
    refused = induction.grant_from_induction(event, [guest.pk], actor=w.manager)
    assert refused[0]["status"] == "refused" and refused[0]["code"] == "guest_pass_required"
    ends = timezone.now() + timedelta(hours=5)
    monkeypatch.setattr(induction, "guest_pass_window", lambda *a, **k: SimpleNamespace(valid_until=ends))
    results = induction.grant_from_induction(event, [guest.pk], actor=w.manager)
    assert results[0]["status"] == "granted" and results[0]["guest"] is True
    grant = GuestCertificationGrant.objects.get(user=guest)
    assert grant.source_event_id == event.pk and grant.expires_at == ends
    assert induction.holds_certification(guest, w.type, w.space)
    assert not induction.holds_certification(guest, w.type, w.space, include_guest=False)
    assert AuditLog.objects.filter(action="certification.guest_granted", target_id=str(grant.pk)).exists()
    induction.revoke_guest_grant(grant, actor=w.manager)
    assert not induction.holds_certification(guest, w.type, w.space)


def test_certified_member_may_instruct_and_supervisees_use_only_while_open():
    w = _world()
    instructor, membership = _member(w.space, "l3a-instructor")
    CertificationGrant.objects.create(certification_type=w.cert, membership=membership, granted_by=w.manager)
    student, _ = _member(w.space, "l3a-student")
    outsider, _ = _member(w.space, "l3a-outsider")
    assert supervised.may_instruct(instructor, w.machine) and not supervised.may_instruct(outsider, w.machine)
    with pytest.raises(PermissionDenied):
        supervised.open_session(w.machine, outsider)
    session = supervised.open_session(w.machine, instructor)
    assert supervised.open_session_for(w.machine).pk == session.pk
    assert not supervised.may_use_supervised(student, w.machine)  # not added yet
    supervised.add_supervisee(session, student, actor=instructor)
    assert supervised.may_use_supervised(student, w.machine)
    assert not supervised.may_use_supervised(outsider, w.machine)
    use = supervised.start_use(session, student, actor=instructor, note="First cut")
    assert use.instructor_id == instructor.pk
    supervised.close_session(session, actor=instructor)
    assert not supervised.may_use_supervised(student, w.machine)
    assert SupervisedUse.objects.get(pk=use.pk).ended_at is not None
    assert AuditLog.objects.filter(action="machine_session.supervised_closed").exists()


def test_supervised_session_is_exclusive_and_needs_a_supervisee_first():
    w = _world()
    student, _ = _member(w.space, "l3a-student2")
    session = supervised.open_session(w.machine, w.manager)
    with pytest.raises(SessionRefused) as raised:
        supervised.start_use(session, student, actor=w.manager)
    assert raised.value.code == "not_supervised"
    with pytest.raises(SessionRefused):
        supervised.open_session(w.machine, w.manager)  # one open session per machine
    supervised.close_session(session, actor=w.manager)
    MachineSession.objects.create(
        makerspace=w.space, machine=w.machine, machine_type=w.type, member=student, source="staff",
        started_at=timezone.now())
    with pytest.raises(SessionRefused):
        supervised.open_session(w.machine, w.manager)  # a live member session holds the machine


def test_supervised_surface_is_off_with_the_capability():
    w = _world()
    w.space.enabled_features = sorted(set(w.space.enabled_features) - {"machines.supervised_sessions"})
    w.space.save(update_fields=["enabled_features"])
    with pytest.raises(NotFound):
        supervised.open_session(w.machine, w.manager)
    assert supervised.open_session_for(w.machine) is None
    student, _ = _member(w.space, "l3a-off")
    assert not supervised.may_use_supervised(student, w.machine)


def test_induction_and_supervised_api_round_trip():
    w = _world()
    student, _ = _member(w.space, "l3a-api-student")
    event = _attended(w, student)
    staff = APIClient()
    staff.force_authenticate(w.manager)
    base = f"/api/v1/admin/makerspaces/{w.space.pk}/events/{event.pk}/induction"
    # Decision 224(b): a type-scoped Machine Manager who does not run the event cannot link it;
    # a Space Manager (event authority as well as machine authority) can.
    refused = staff.post(base, {"certification_type_id": w.cert.pk}, format="json")
    assert refused.status_code == 403 and not EventInductionLink.objects.filter(event=event).exists()
    head = APIClient()
    head.force_authenticate(staff_account(w.space, "l3a-api-head", "space_manager"))
    created = head.post(base, {"certification_type_id": w.cert.pk}, format="json")
    assert created.status_code == 201
    overview = staff.get(base).json()
    assert [a["user_id"] for a in overview["attendees"]] == [student.pk] and overview["can_grant"]
    granted = staff.post(f"{base}/grant", {"user_ids": [student.pk]}, format="json")
    assert granted.status_code == 200 and granted.json()["results"][0]["status"] == "granted"
    assert EventInductionLink.objects.filter(event=event).count() == 1
    # Final audit: a supervisee must be in the picker's pool -- present now, or registered for the linked event.
    opened = staff.post(f"/api/v1/member/machines/{w.machine.pk}/supervised-sessions", {"event_id": event.pk}, format="json")
    assert opened.status_code == 201
    sid = opened.json()["id"]
    added = staff.post(f"/api/v1/member/supervised-sessions/{sid}/supervisees", {"user_id": student.pk}, format="json")
    assert added.status_code == 200 and added.json()["participants"][0]["user"] == student.pk
    closed = staff.post(f"/api/v1/member/supervised-sessions/{sid}/close", {}, format="json")
    assert closed.status_code == 200 and closed.json()["is_open"] is False


def test_supervisee_must_be_a_member_or_hold_a_machine_guest_pass_and_clear_the_minors_rule(monkeypatch):
    """Final audit 0.12.0 M8 (decisions 223(d)/(k))."""
    from apps.makerspaces import minors_guard
    from apps.makerspaces.models import GuestPass
    w = _world("l3a-m8")
    instructor, membership = _member(w.space, "l3a-m8-instructor")
    CertificationGrant.objects.create(certification_type=w.cert, membership=membership, granted_by=w.manager)
    session = supervised.open_session(w.machine, instructor)
    stranger = make_user("l3a-m8-stranger")
    with pytest.raises(SessionRefused) as refused:
        supervised.add_supervisee(session, stranger, actor=instructor)
    assert refused.value.code == "guest_pass_machines_not_allowed"
    now = timezone.now()
    row = GuestPass.objects.create(
        makerspace=w.space, holder=stranger, kind="day", valid_from=now - timedelta(hours=1),
        valid_until=now + timedelta(hours=3), pass_date=timezone.localdate(),
        entitlements={"machines": "none"})
    with pytest.raises(SessionRefused):
        supervised.add_supervisee(session, stranger, actor=instructor)  # pass says no machines
    # Entitlements are frozen once a pass exists (guest-pass guard trigger): a pass that allows supervised machines is a new one.
    guest = make_user("l3a-m8-guest")
    GuestPass.objects.create(
        makerspace=w.space, holder=guest, kind="day", valid_from=now - timedelta(hours=1),
        valid_until=now + timedelta(hours=3), pass_date=timezone.localdate(),
        entitlements={"machines": "supervised"})
    assert supervised.add_supervisee(session, guest, actor=instructor).user_id == guest.pk
    calls = []
    monkeypatch.setattr(minors_guard, "require_minor_clearance", lambda *args, **kw: calls.append(args[2]))
    supervised.start_use(session, guest, actor=instructor)
    assert calls == ["machine"]

def test_guest_grant_integrity_error_is_a_typed_refusal_not_a_500(monkeypatch):
    """Final audit 0.12.0 (m22): a concurrent duplicate that hits the DB is reported, never raised."""
    from django.db import IntegrityError
    w = _world()
    guest = make_user("l3a-guest-race", access_status=User.AccessStatus.ACTIVE)
    event = _induction_event(w, guest)

    def boom(*a, **k):
        raise IntegrityError("duplicate")
    monkeypatch.setattr(induction, "_grant_one", boom)
    results = induction.grant_from_induction(event, [guest.pk], actor=w.manager)
    assert results[0]["status"] == "refused" and results[0]["code"] == "grant_conflict"

