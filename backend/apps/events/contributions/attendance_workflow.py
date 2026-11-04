"""Shift attendance never changes attendee check-in. Hours need a second person."""
from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from . import commands
from .errors import ProgrammeError, check_version, require_state
from .models_shifts import (EventShift, EventShiftSignup, EventShiftAttendance,
                            EventContributionHours, EventContributionHoursEntry)
from .ports import ports
from .sources import sync_shift_locked
from .role_policy import require_requirements


def counted_minutes(start, end, breaks=0):
    if start is None or end is None or end < start or breaks < 0:
        raise ProgrammeError("invalid_interval", "Check the attendance interval.", status=400)
    elapsed = int((end - start).total_seconds() // 60)
    if breaks > elapsed:
        raise ProgrammeError("invalid_break", "Break time exceeds the shift interval.", status=400)
    return elapsed - breaks


def command(*, actor, event_id, signup_id, payload, action, staff=False):
    row = get_object_or_404(EventShiftSignup, pk=signup_id, event_id=event_id)
    verification = action in ("verify_hours", "adjust_hours", "no_show")

    def authorize(event):
        if not staff and not verification:
            commands.owned(EventShiftSignup, event_id=event.pk, pk=signup_id, actor=actor)
        if action in ("verify_hours", "adjust_hours") and row.member_id == actor.pk:
            raise ProgrammeError("self_verification_forbidden", "Another organizer must verify your hours.", status=403)

    def mutate(event, locks):
        shift = EventShift.objects.select_for_update().get(pk=row.shift_id, event=event)
        signup = EventShiftSignup.objects.select_for_update().get(pk=signup_id, event=event)
        check_version(signup, payload["expected_version"])
        require_state(signup, "approved")
        attendance = get_object_or_404(EventShiftAttendance.objects.select_for_update(), signup=signup)
        now = timezone.now()
        occurred = payload.get("occurred_at", now) if staff else now
        if occurred > now or occurred < shift.starts_at - timedelta(minutes=shift.grace_minutes) or occurred > shift.ends_at + timedelta(minutes=shift.grace_minutes):
            if action in ("check_in", "check_out"):
                raise ProgrammeError("invalid_interval", "Choose a nonfuture time inside the duty window.", status=400)
        if staff and "occurred_at" in payload and not payload.get("reason", "").strip():
            raise ProgrammeError("reason_required", "Explain the desk correction.", status=400)
        if action == "no_show":
            if now < shift.ends_at:
                raise ProgrammeError("shift_not_ended", "The shift has not ended.")
            require_state(attendance, "scheduled")
            commands.changed(attendance, state="no_show", actor=actor, source="staff")
            sync_shift_locked(signup_id=signup.pk, actor_id=actor.pk, locks=locks)
        elif action == "check_in":
            require_state(attendance, "scheduled")
            if not shift.starts_at - timedelta(minutes=shift.grace_minutes) <= occurred < shift.ends_at:
                raise ProgrammeError("shift_not_started", "Check-in is outside this shift's window.")
            if EventShiftAttendance.objects.filter(signup__member_id=signup.member_id,
                event=event, state="checked_in").exclude(pk=attendance.pk).exists():
                raise ProgrammeError("shift_conflict", "Finish your other duty first.")
            require_requirements(actor_id=signup.member_id, assignment_id=signup.assignment_id, shift_id=shift.pk)
            commands.changed(attendance, state="checked_in", checked_in_at=occurred, actor=actor,
                             source="staff" if staff else "self")
        elif action == "check_out":
            require_state(attendance, "checked_in")
            if occurred > shift.ends_at + timedelta(minutes=shift.grace_minutes):
                raise ProgrammeError("shift_closed", "Ask the desk to correct the attendance interval.")
            breaks = payload.get("break_minutes", attendance.break_minutes) if staff else attendance.break_minutes
            minutes = counted_minutes(attendance.checked_in_at, occurred, breaks)
            if EventShiftAttendance.objects.filter(event=event, signup__member_id=signup.member_id,
                state="checked_out", checked_in_at__lt=occurred,
                checked_out_at__gt=attendance.checked_in_at).exclude(pk=attendance.pk).exists():
                raise ProgrammeError("shift_conflict", "This attendance interval overlaps already counted work.")
            commands.changed(attendance, state="checked_out", checked_out_at=occurred, break_minutes=breaks, actor=actor)
            commands.new_row(EventContributionHours, event, signup=signup, minutes=minutes)
            sync_shift_locked(signup_id=signup.pk, actor_id=actor.pk, locks=locks)
        elif action in ("verify_hours", "adjust_hours"):
            require_state(attendance, "checked_out")
            hours = get_object_or_404(EventContributionHours.objects.select_for_update(), signup=signup)
            if action == "verify_hours":
                require_state(hours, "pending")
                minutes = counted_minutes(attendance.checked_in_at, attendance.checked_out_at, attendance.break_minutes)
            else:
                require_state(hours, "verified", "adjusted")
                minutes = payload["minutes"]
                if minutes > 1440 or not payload.get("reason", "").strip():
                    raise ProgrammeError("invalid_adjustment", "Supply bounded minutes and a reason.", status=400)
            kind = "verified" if action == "verify_hours" else "adjusted"
            commands.new_row(EventContributionHoursEntry, event, hours=hours, actor=actor,
                previous_version=hours.version, minutes=minutes, kind=kind, reason=payload.get("reason", ""))
            commands.changed(hours, minutes=minutes, state=kind)
            from apps.events.certificates.contribution_proof import invalidate_role_locked
            invalidate_role_locked(event=event, assignment_id=signup.assignment_id, actor=actor)
        else:
            raise ProgrammeError("invalid_transition", "Unknown attendance command.", status=400)
        if staff and "occurred_at" in payload:
            from .models_shifts import EventShiftAttendanceCorrection
            commands.new_row(EventShiftAttendanceCorrection, event, attendance=attendance, actor=actor,
                kind=action, occurred_at=occurred, reason=payload["reason"])
        return commands.changed(signup)

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action=f"shift.{action}", feature="events.volunteering",
        permission="manage_volunteers" if staff or verification else False,
        authorize=authorize, account_ids=(row.member_id,), mutate=mutate)
