"""Granting, renewing and revoking: authority, scope, validation, audit (decision 319)."""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.models import AuditLog
from apps.machines import access_grants as ag
from apps.machines.access_grants_services import bulk_grant, grant_access, revoke_access
from apps.machines.models import MachineAccessGrant
from tests.machines.certification_helpers import _member
from tests.parity_0120.machine_access.helpers import machine_manager, world

pytestmark = pytest.mark.django_db


def test_space_manager_grants_and_it_is_audited():
    w = world()
    row = grant_access(w.boss, w.space, w.member, machine=w.laser, note="Passed the walkthrough")
    assert row.granted_by == w.boss and row.source == "staff"
    assert ag.can_use(w.member, w.laser) == (True, None)
    assert AuditLog.objects.filter(action="machine_access.granted", makerspace=w.space).count() == 1


def test_granting_again_renews_the_live_grant_instead_of_duplicating():
    w = world()
    first = grant_access(w.boss, w.space, w.member, machine_type=w.kind)
    again = grant_access(w.boss, w.space, w.member, machine_type=w.kind,
                         expires_at=timezone.now() + timedelta(days=30))
    assert again.pk == first.pk and again.expires_at is not None
    assert MachineAccessGrant.objects.filter(member=w.member).count() == 1
    assert AuditLog.objects.filter(action="machine_access.renewed").count() == 1


def test_revoke_keeps_the_row_and_audits():
    w = world()
    row = grant_access(w.boss, w.space, w.member, machine=w.laser)
    revoke_access(w.boss, row, reason="left the course")
    row.refresh_from_db()
    assert row.revoked_at is not None and row.revoked_by == w.boss
    assert ag.can_use(w.member, w.laser) == (False, "no_machine_access")
    assert AuditLog.objects.filter(action="machine_access.revoked").count() == 1


def test_machine_manager_is_limited_to_their_machine_scope():
    w = world()
    manager = machine_manager(w, w.kind)
    grant_access(manager, w.space, w.member, machine=w.laser)
    grant_access(manager, w.space, w.member, machine_type=w.kind)
    with pytest.raises(PermissionDenied):
        grant_access(manager, w.space, w.member, machine=w.mill)
    with pytest.raises(PermissionDenied):
        grant_access(manager, w.space, w.member, machine_type=w.other)


def test_a_plain_member_cannot_grant():
    w = world()
    other, _ = _member(w.space, "pretender")
    with pytest.raises(PermissionDenied):
        grant_access(other, w.space, w.member, machine=w.laser)


def test_validation_one_target_future_expiry_active_member_same_space():
    w = world()
    with pytest.raises(ValidationError):
        grant_access(w.boss, w.space, w.member)
    with pytest.raises(ValidationError):
        grant_access(w.boss, w.space, w.member, machine=w.laser, machine_type=w.kind)
    with pytest.raises(ValidationError):
        grant_access(w.boss, w.space, w.member, machine=w.laser, expires_at=timezone.now() - timedelta(days=1))
    elsewhere = world("other")
    with pytest.raises(ValidationError):
        grant_access(w.boss, w.space, w.member, machine=elsewhere.laser)
    w.membership.status = "revoked"
    w.membership.save(update_fields=["status"])
    with pytest.raises(ValidationError):
        grant_access(w.boss, w.space, w.member, machine=w.laser)


def test_bulk_grant_reports_each_failure_without_hiding_the_rest():
    w = world()
    other, _ = _member(w.space, "second")
    outsider = world("outsider").member
    done, failed = bulk_grant(w.boss, w.space, [w.member, other, outsider], machine_type=w.kind)
    assert len(done) == 2 and [f["member_id"] for f in failed] == [outsider.pk]


def test_expiring_soon_notice_is_sent_once(monkeypatch):
    from apps.machines import notifications_machine_access as notes
    w = world()
    grant_access(w.boss, w.space, w.member, machine=w.laser, expires_at=timezone.now() + timedelta(days=3))
    sent = []
    monkeypatch.setattr(notes, "notify_access", lambda grant, event: sent.append((grant.pk, event)))
    assert notes.notify_expiring() == 1
    assert notes.notify_expiring() == 0
    assert sent[0][1] == "expiring"
