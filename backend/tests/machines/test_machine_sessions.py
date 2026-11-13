"""L23 (#158): start rules, one live session, frozen-rate charge math, review flow, triggers."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.machines import sessions_service as service
from apps.machines.models import MachineSession, MachineSessionAmendment, MachineUsageEntry
from apps.machines.sessions_rules import SessionRefused
from apps.payments.models import Payment
from tests.machines.session_helpers import check_in, features, open_session, price, session_world
from tests.rbac_f6_helpers import community_member

pytestmark = pytest.mark.django_db


def refused(w, member=None, machine=None):
    with pytest.raises(Exception) as caught:
        service.start(machine or w.machines[0], member or w.member, actor=member or w.member, source="member_qr")
    detail = getattr(caught.value, "detail", {})
    return detail.get("code") if isinstance(detail, dict) else str(detail)


def payment(session):
    return Payment.objects.filter(subject_type="machine_session", subject_id=session.pk).first()


def test_each_refusal_has_its_typed_code(monkeypatch):
    w = session_world("ses-rules")
    w.member.access_status = "suspended"
    w.member.save(update_fields=["access_status"])
    assert refused(w) == "member_restricted"
    other = community_member(w.space, "nocheckin")
    assert refused(w, other.user) == "presence_required"
    other.status = "revoked"
    other.save(update_fields=["status"])
    assert refused(w, other.user) == "membership_required"
    fresh = community_member(w.space, "fresh")
    check_in(w.space, fresh)
    # Decision 319: a space manager's machine access grant decides, not a certification.
    from apps.machines.models import MachineAccessGrant
    w.machines[0].open_to_all_members = False
    w.machines[0].save(update_fields=["open_to_all_members"])
    assert refused(w, fresh.user) == "no_machine_access"
    MachineAccessGrant.objects.create(makerspace=w.space, member=fresh.user, machine_type=w.kind)
    w.machines[0].status = "maintenance"
    w.machines[0].save(update_fields=["status"])
    assert refused(w, fresh.user) == "machine_unavailable"
    w.machines[0].status = "idle"
    w.machines[0].save(update_fields=["status"])
    monkeypatch.setattr("apps.machines.lockout.blocking_schedules", lambda machine, today=None: [w.machines[0]])
    assert refused(w, fresh.user) == "machine_locked_out"
    monkeypatch.undo()
    from tests.machines.test_requires_booking import bookable, booking
    booking(bookable(w, w.machines[0]), community_member(w.space, "booker").user)
    assert refused(w, fresh.user) == "machine_booked"
    second = community_member(w.space, "second")
    check_in(w.space, second)
    service.start(w.machines[1], second.user, actor=second.user, source="member_qr")
    assert refused(w, fresh.user, w.machines[1]) == "machine_in_use"
    assert refused(w, second.user, w.machines[1]) == "session_already_live"


def test_staff_start_runs_the_member_checks_and_cannot_override():
    w = session_world("ses-staff", checked_in=False)
    with pytest.raises(SessionRefused) as caught:
        service.start(w.machines[0], w.member, actor=w.staff, source="staff")
    assert caught.value.code == "presence_required"


def test_one_live_session_per_machine_and_per_member_machine_is_db_enforced():
    w = session_world("ses-unique")
    open_session(w)
    other = community_member(w.space, "other")
    with pytest.raises(IntegrityError), transaction.atomic():
        open_session(w, member=other.user)
    with pytest.raises(IntegrityError), transaction.atomic():
        open_session(w)


@pytest.mark.parametrize("minutes,billed,amount", [(10, 30, "60.00"), (40, 45, "90.00"), (0, 0, None)])
def test_member_stop_charges_the_frozen_rate_with_increment_and_minimum(minutes, billed, amount):
    w = session_world(f"ses-math-{minutes}")
    row = service.start(w.machines[0], w.member, actor=w.member, source="member_qr")
    assert row.billable and row.quote_digest
    price(w.space, rate="999.00")  # a later price change never touches a running session
    closed = service.stop(row, actor=w.member, reason="member", at=row.started_at + timedelta(minutes=minutes))
    assert not closed.flagged and closed.duration_minutes == minutes
    charge = payment(row)
    if amount is None:
        assert charge is None
    else:
        assert (charge.status, charge.amount, charge.member_id) == ("pending", Decimal(amount), w.member.pk)
        assert charge.pricing_snapshot["lines"][0]["detail"]["billed_minutes"] == billed
        assert charge.pricing_snapshot["session"]["start_digest"] == row.quote_digest
    usage = MachineUsageEntry.objects.get(note=f"Machine session {row.pk}")
    assert (usage.source, usage.duration_minutes, usage.member_id) == ("session", minutes, w.member.pk)


def test_start_refuses_a_changed_price_digest():
    w = session_world("ses-digest")
    with pytest.raises(Exception) as caught:
        service.start(w.machines[0], w.member, actor=w.member, source="member_qr", digest="0" * 64)
    assert caught.value.detail["code"] == "price_changed"
    assert not MachineSession.objects.filter(member=w.member).exists()


def test_billing_off_records_time_but_never_a_charge():
    w = session_world("ses-free")
    features(w.space, remove={"charges.machines"})
    row = service.start(w.machines[0], w.member, actor=w.member, source="member_qr")
    service.stop(row, actor=w.member, reason="member", at=row.started_at + timedelta(minutes=50))
    assert not row.billable and payment(row) is None
    assert MachineUsageEntry.objects.filter(note=f"Machine session {row.pk}", duration_minutes=50).exists()


def test_auto_stopped_session_is_held_amended_then_confirmed():
    w = session_world("ses-review")
    row = service.start(w.machines[0], w.member, actor=w.member, source="member_qr")
    closed = service.stop(row, actor=None, reason="max_length", at=row.started_at + timedelta(minutes=240))
    assert closed.flagged and payment(row) is None
    assert not MachineUsageEntry.objects.filter(note=f"Machine session {row.pk}").exists()
    service.amend(row, w.staff, minutes=20, reason="Forgot to stop; left after 20 minutes.")
    service.confirm(row, w.staff)
    charge = payment(row)
    assert charge.amount == Decimal("60.00")  # 20 minutes -> the 30-minute minimum at 120/h
    assert MachineUsageEntry.objects.get(note=f"Machine session {row.pk}").duration_minutes == 20
    with pytest.raises(SessionRefused) as again:
        service.amend(row, w.staff, minutes=10, reason="late")
    assert again.value.code == "session_final"
    assert list(MachineSessionAmendment.objects.filter(session=row).values_list("kind", flat=True)) == [
        "correct", "confirm"]


def test_a_member_stopped_session_is_final_and_cannot_be_amended():
    w = session_world("ses-final")
    row = service.start(w.machines[0], w.member, actor=w.member, source="member_qr")
    service.stop(row, actor=w.member, reason="member")
    with pytest.raises(SessionRefused) as caught:
        service.amend(row, w.staff, minutes=5, reason="x")
    assert caught.value.code == "session_final"
    with pytest.raises(SessionRefused) as stopped:
        service.stop(row, actor=w.member, reason="member")
    assert stopped.value.code == "session_closed"


def test_a_closed_session_and_its_amendments_are_append_only_in_the_database():
    w = session_world("ses-trigger")
    row = service.start(w.machines[0], w.member, actor=w.member, source="member_qr")
    service.stop(row, actor=None, reason="closing", at=row.started_at + timedelta(minutes=30))
    service.amend(row, w.staff, minutes=15, reason="closed early")
    for statement in ("UPDATE machines_machinesession SET duration_minutes = 1 WHERE id = %s",
                      "DELETE FROM machines_machinesession WHERE id = %s",
                      "UPDATE machines_machinesessionamendment SET minutes = 1 WHERE session_id = %s",
                      "DELETE FROM machines_machinesessionamendment WHERE session_id = %s"):
        with pytest.raises(Exception), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(statement, [row.pk])
    live = open_session(w, machine=w.machines[1], member=community_member(w.space, "live").user)
    MachineSession.objects.filter(pk=live.pk).update(device_job_ref="still-open")  # a live row may change
    with pytest.raises(Exception), transaction.atomic():
        MachineSession.objects.filter(pk=live.pk).update(started_at=timezone.now())


def test_audit_rows_name_every_step():
    from apps.audit.models import AuditLog
    w = session_world("ses-audit")
    row = service.start(w.machines[0], w.member, actor=w.member, source="member_qr")
    service.stop(row, actor=None, reason="check_out", at=row.started_at + timedelta(minutes=45))
    service.amend(row, w.staff, minutes=40, reason="checked out a little later")
    service.confirm(row, w.staff)
    actions = set(AuditLog.objects.filter(makerspace=w.space, action__startswith="machine_session.").values_list(
        "action", flat=True))
    assert actions >= {"machine_session.started", "machine_session.auto_stopped", "machine_session.amended",
                       "machine_session.confirmed", "machine_session.charge_raised"}
