"""Team-place allocation shares C's locked helper, never volunteer signup counts."""
from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.events.contributions import commands
from apps.events.contributions.allocation import require_place_locked
from apps.events.contributions.errors import ProgrammeError, check_version, require_state
from apps.events.contributions.models_shifts import EventShift, EventShiftSignup
from apps.events.contributions.ports import ports
from .models_queue import OfficeHoursBooking
from . import policy


def cancel_locked(*, actor, event, booking_id, locks, reason_code):
    from django.db import connection
    from apps.audit.services import record
    from apps.events import event_authority
    if not connection.in_atomic_block or locks.event_id != event.pk:
        raise RuntimeError("Office-hour cancellation requires workflow locks.")
    row = get_object_or_404(OfficeHoursBooking.objects.select_for_update(), pk=booking_id, event=event)
    if reason_code == "role_withdrawn":
        if row.mentor_assignment.member_id != actor.pk:
            event_authority.require(actor, event, "manage_team")
    elif reason_code == "team_cancelled":
        ports().teams.require_member(actor_id=actor.pk, event_id=event.pk, team_id=row.team_id)
    elif reason_code == "slot_changed":
        event_authority.require(actor, event, "manage_team")
    else:
        raise ProgrammeError("invalid_reason", "Unknown cancellation reason.", status=400)
    if row.state == "cancelled":
        return row
    commands.changed(row, state="cancelled", cancelled_at=timezone.now())
    from apps.events.contributions.notifications import cancelled_booking_locked
    cancelled_booking_locked(row)
    record(actor, "event.office_hours.cancelled", makerspace=event.makerspace, target=row,
           meta={"event_id": event.pk, "reason_code": reason_code})
    return row


def book(*, actor, event_id, slot_id, payload):
    initial = get_object_or_404(EventShift, pk=slot_id, event_id=event_id, kind="office_hours")
    mentor_id = initial.mentor_assignment.member_id
    def authorize(event):
        commands.active_member(actor)
        ports().teams.require_member(actor_id=actor.pk, event_id=event.pk, team_id=payload["team_id"])
        ports().teams.require_eligible(event_id=event.pk, team_id=payload["team_id"], at=timezone.now())
        ports().teams.require_practice(event_id=event.pk, team_id=payload["team_id"], practice_run_id=None)

    def mutate(event, locks):
        slot = get_object_or_404(EventShift.objects.select_for_update(), pk=slot_id, event=event, kind="office_hours")
        check_version(slot, payload["expected_version"])
        if slot.state != "open" or slot.starts_at <= timezone.now() or slot.signup_deadline <= timezone.now():
            raise ProgrammeError("slot_closed", "This slot is closed.")
        mentor = slot.mentor_assignment
        if mentor.member_id not in locks.account_ids:
            raise ProgrammeError("scope_changed", "The office-hour mentor changed; refresh this slot.")
        assignment, profile = policy.mentor_for(mentor.member, event, at=slot.starts_at, assignment_id=mentor.pk)
        from .models_queue import MentorProfile
        profile = MentorProfile.objects.select_for_update().get(pk=profile.pk, event=event)
        if not policy.in_windows(profile.availability or mentor.availability, slot.ends_at - timedelta(microseconds=1)):
            raise ProgrammeError("booking_conflict", "The mentor is unavailable.")
        if not policy.visit_eligible(assignment=assignment, profile=profile,
                                     team_id=payload["team_id"], at=slot.starts_at):
            raise ProgrammeError("booking_conflict", "The mentor is unavailable.")
        overlaps = OfficeHoursBooking.objects.filter(event=event, state="booked",
            slot__starts_at__lt=slot.ends_at, slot__ends_at__gt=slot.starts_at)
        own = overlaps.filter(team_id=payload["team_id"])
        if own.exists():
            raise ProgrammeError("booking_conflict", "Your team has an overlapping booking.", conflicts=[
                {"booking_id": row.pk, "starts_at": row.slot.starts_at.isoformat(),
                 "ends_at": row.slot.ends_at.isoformat()} for row in own.select_related("slot")])
        if overlaps.filter(mentor_assignment=mentor).exclude(slot=slot).exists() or EventShiftSignup.objects.filter(
            member_id=mentor.member_id, state="approved", shift__starts_at__lt=slot.ends_at,
            shift__ends_at__gt=slot.starts_at).exists():
            raise ProgrammeError("booking_conflict", "The mentor is unavailable.")
        require_place_locked(slot, booked=slot.bookings.filter(state="booked").count())
        return commands.new_row(OfficeHoursBooking, event, slot=slot, team_id=payload["team_id"],
            booked_by=actor, mentor_assignment=mentor, operation_uuid=payload["operation_id"])

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="office_hours.book", feature="events.mentoring", permission=False,
        authorize=authorize, mutate=mutate, account_ids=(mentor_id,), authority_ids=(mentor_id,), status=201)


def cancel(*, actor, event_id, booking_id, payload):
    initial = get_object_or_404(OfficeHoursBooking, pk=booking_id, event_id=event_id)

    def authorize(event):
        commands.active_member(actor)
        ports().teams.require_member(actor_id=actor.pk, event_id=event.pk, team_id=initial.team_id)
        ports().teams.require_eligible(event_id=event.pk, team_id=initial.team_id, at=timezone.now())

    def mutate(event, locks):
        slot = EventShift.objects.select_for_update().get(pk=initial.slot_id, event=event)
        row = OfficeHoursBooking.objects.select_for_update().get(pk=booking_id, event=event)
        check_version(row, payload["expected_version"])
        require_state(row, "booked")
        if timezone.now() >= slot.starts_at:
            raise ProgrammeError("slot_started", "Ask an organizer to cancel a started slot.")
        return cancel_locked(actor=actor, event=event, booking_id=row.pk, locks=locks, reason_code="team_cancelled")

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="office_hours.cancel", feature="events.mentoring", permission=False, authorize=authorize, mutate=mutate)
