"""The machine-session workflow (lane L23, #158): start, stop, amend, assign, confirm.

One authority for every source (member QR, staff, device). Locks: write fence ->
machine (start) or session (every later step). A session is closed exactly once; what
staff decide afterwards is an append-only amendment. Finishing a session ("final")
writes ONE `MachineUsageEntry` (source `session`, minutes) so usage, meters and reports
keep seeing machine time, and raises its PENDING charge when it bills. A session stopped
by the member or by staff is final at once; an auto-stopped (flagged) or unattributed
one is final only when staff confirm it, after any correction.
"""

from django.utils.translation import gettext
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.machines import sessions_billing as billing
from apps.machines import sessions_state as state
from apps.machines.sessions_rules import SessionRefused, require_can_start

def _models():
    from apps.machines.models import Machine, MachineSession, MachineSessionAmendment, MachineUsageEntry
    return Machine, MachineSession, MachineSessionAmendment, MachineUsageEntry


def _fence(makerspace_id):
    from apps.encryption.write_fence import assert_mapped_write_allowed
    assert_mapped_write_allowed(makerspace_id)


def _locked_session(session):
    _machine, Session, _amendment, _usage = _models()
    return Session.objects.select_for_update(of=("self",)).select_related(
        "makerspace", "machine", "machine_type").get(pk=session.pk)




def start(machine, member, *, actor, source, digest=None, now=None):
    """Open a live session for `member` on `machine` (member QR or staff)."""
    from apps.payments.pricing import verify_digest
    Machine, Session, _amendment, _usage = _models()
    state.require_sessions(machine.makerspace)
    now = now or timezone.now()
    with transaction.atomic():
        _fence(machine.makerspace_id)
        machine = Machine.objects.select_for_update(no_key=True, of=("self",)).select_related(
            "makerspace", "machine_type").get(pk=machine.pk)
        require_can_start(machine, member, now=now)
        from apps.managed_hosting.extra_quotas import check_extra_quota
        # Decision 284: refuses the START of a member/staff session; a DEVICE-reported session is a fact
        # about a job that already ran (sessions_device) and is counted, never refused.
        check_extra_quota(machine.makerspace, "machine_sessions_monthly")
        rate = billing.start_quote(machine, member) if billing.billing_active(machine.makerspace) else None
        if rate is not None and digest:
            verify_digest(rate, digest)
        try:
            with transaction.atomic():
                session = Session.objects.create(
                    makerspace=machine.makerspace, machine=machine, machine_type=machine.machine_type, member=member,
                    source=source, started_at=now, started_by=actor,
                    billable=bool(rate is not None and rate.total > 0),
                    quote_snapshot=rate.to_snapshot() if rate is not None else {},
                    quote_digest=rate.digest if rate is not None else "")
        except IntegrityError:
            raise SessionRefused("machine_in_use", gettext("Someone is using this machine right now."))
        audit.record(actor, "machine_session.started", makerspace=session.makerspace, target=session, meta={
            "session_id": session.pk, "machine_id": session.machine_id, "source": source, "billable": session.billable,
            "member_id": getattr(member, "pk", None)})
    return session


def _write_usage(session, minutes, member, actor):
    from apps.machines.metering import MeteringUnit
    _machine, _session, _amendment, Usage = _models()
    hours = (Decimal(minutes) / Decimal(60)).quantize(Decimal("0.01"))
    return Usage.objects.create(
        machine=session.machine, member=member, started_at=session.started_at, hours=hours,
        duration_minutes=minutes, source=Usage.Source.SESSION, metering_unit=MeteringUnit.MINUTES,
        service_request=session.service_request, note=f"Machine session {session.pk}", logged_by=actor)


def _finalize(session, actor):
    minutes, member = state.effective_minutes(session), state.effective_member(session)
    _write_usage(session, minutes, member, actor)
    return billing.raise_charge(session, minutes=minutes, member=member, actor=actor)


def stop(session, *, actor, reason, at=None, minutes=None, flag=False):
    """Close a live session once. Auto-stop reasons (or ``flag``, e.g. adapter minutes that disagree with the
    wall clock, decision 336h) flag it for staff review, so its charge waits for a staff confirmation."""
    _machine, Session, _amendment, _usage = _models()
    with transaction.atomic():
        _fence(session.makerspace_id)
        session = _locked_session(session)
        if session.ended_at is not None:
            raise SessionRefused("session_closed", gettext("This session has already stopped."))
        end = max(at or timezone.now(), session.started_at)
        elapsed = round((end - session.started_at).total_seconds() / 60)
        session.ended_at, session.stop_reason, session.stopped_by = end, reason, actor
        session.flagged = flag or reason in Session.AUTO_STOP_REASONS
        session.duration_minutes = max(int(minutes if minutes is not None else elapsed), 0)
        session.save(update_fields=["ended_at", "stop_reason", "stopped_by", "flagged", "duration_minutes"])
        if session.flagged:
            audit.record(actor, "machine_session.auto_stopped", makerspace=session.makerspace, target=session, meta={
                "session_id": session.pk, "machine_id": session.machine_id, "reason": reason, "minutes": session.duration_minutes})
        else:
            audit.record(actor, "machine_session.stopped", makerspace=session.makerspace, target=session, meta={
                "session_id": session.pk, "machine_id": session.machine_id, "reason": reason, "minutes": session.duration_minutes})
        if not state.needs_review(session):
            _finalize(session, actor)
        if session.flagged:
            from apps.machines.notifications_sessions import notify_auto_stopped
            notify_auto_stopped(session)
    return session


def _reviewable(session):
    session = _locked_session(session)
    if session.ended_at is None:
        raise SessionRefused("session_live", gettext("Stop the session first."))
    if not state.needs_review(session):
        raise SessionRefused("session_final", gettext("This session is already final; its charge follows the usual "
                             "payment path."))
    return session


def amend(session, actor, *, minutes, reason):
    """Correct an auto-stopped session's duration before it is confirmed (audited)."""
    _machine, _session, Amendment, _usage = _models()
    with transaction.atomic():
        _fence(session.makerspace_id)
        session = _reviewable(session)
        before = state.effective_minutes(session)
        Amendment.objects.create(makerspace=session.makerspace, session=session, kind="correct", minutes=minutes,
                                 reason=reason, actor=actor)
        audit.record(actor, "machine_session.amended", makerspace=session.makerspace, target=session, meta={
            "session_id": session.pk, "machine_id": session.machine_id, "minutes_before": before, "minutes_after": minutes})
    return session


def assign(session, actor, *, member, reason):
    """Attribute an unattributed device session to a member (never to a guess: staff decide)."""
    _machine, _session, Amendment, _usage = _models()
    with transaction.atomic():
        _fence(session.makerspace_id)
        session = _reviewable(session)
        if session.member_id is not None:
            raise SessionRefused("session_attributed", gettext("This session already belongs to a member."))
        Amendment.objects.create(makerspace=session.makerspace, session=session, kind="assign", member=member,
                                 reason=reason, actor=actor)
        audit.record(actor, "machine_session.assigned", makerspace=session.makerspace, target=session, meta={
            "session_id": session.pk, "machine_id": session.machine_id, "member_id": member.pk})
    return session


def confirm(session, actor):
    """Staff confirm a session under review: it becomes final and its charge is raised."""
    _machine, _session, Amendment, _usage = _models()
    with transaction.atomic():
        _fence(session.makerspace_id)
        session = _reviewable(session)
        if state.effective_member_id(session) is None:
            raise SessionRefused("session_unattributed", gettext("Assign this session to a member first."))
        minutes = state.effective_minutes(session)
        Amendment.objects.create(makerspace=session.makerspace, session=session, kind="confirm", minutes=minutes,
                                 actor=actor)
        audit.record(actor, "machine_session.confirmed", makerspace=session.makerspace, target=session, meta={
            "session_id": session.pk, "machine_id": session.machine_id, "minutes": minutes})
        session = _locked_session(session)
        _finalize(session, actor)
    return session
