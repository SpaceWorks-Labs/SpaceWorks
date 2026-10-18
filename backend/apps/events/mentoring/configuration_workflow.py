"""Settings, recusals and attention controls use the event command boundary."""
from datetime import datetime, timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.events import event_authority
from apps.events.contributions import commands
from apps.events.contributions.errors import ProgrammeError, check_version
from apps.events.contributions.management_workflow import _valid, _zero
from apps.events.contributions.models_roles import EventRoleAssignment
from apps.events.contributions.ports import ports
from .models_queue import MentorProfile, MentorTeamAssignment, EventHelpType, OfficeHoursBooking
from .models_rounds import MentorConflict, MentorNomination, MentorRound, MentorRoundCheckin
from .models_operations import MentorAttentionPreference
from . import policy


def save_profile(*, actor, event_id, assignment_id, payload):
    initial = get_object_or_404(EventRoleAssignment, pk=assignment_id, event_id=event_id, role="mentor")

    def authorize(event):
        if actor.pk == initial.member_id:
            policy.mentor_for(actor, event, on_shift=False)
        else:
            event_authority.require(actor, event, "manage_team")

    def mutate(event, locks):
        role = get_object_or_404(EventRoleAssignment.objects.select_for_update(), pk=assignment_id,
            event=event, state="approved", imported_inert=False)
        row = get_object_or_404(MentorProfile.objects.select_for_update(), assignment=role, event=event)
        check_version(row, payload["expected_version"])
        for key in ("skills", "affiliation", "availability", "max_active_teams"):
            if key in payload:
                setattr(row, key, payload[key])
        if MentorTeamAssignment.objects.filter(mentor_assignment=role, ended_at__isnull=True).count() > row.max_active_teams:
            raise ProgrammeError("mentor_full", "End assignments before reducing capacity.")
        for window in row.availability:
            start, end = [datetime.fromisoformat(window[key].replace("Z", "+00:00")) for key in ("starts_at", "ends_at")]
            if not event.starts_at <= start < end <= event.ends_at:
                raise ValidationError({"availability": "Choose intervals inside this event."})
        for booking in OfficeHoursBooking.objects.filter(mentor_assignment=role, state="booked",
                slot__ends_at__gt=timezone.now()).select_related("slot"):
            if not policy.covers_interval(row.availability, booking.slot.starts_at, booking.slot.ends_at):
                raise ProgrammeError("active_bookings", "Reschedule booked office hours before changing availability.")
        _valid(row)
        # An explicit empty profile schedule means off duty. Keep the role's
        # compatibility schedule synchronized so fallback cannot revive it.
        if "availability" in payload:
            commands.changed(role, availability=row.availability)
        return commands.changed(row, **{key: getattr(row, key) for key in (
            "skills", "affiliation", "availability", "max_active_teams")})

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="mentor.profile", feature="events.mentoring", permission=False,
        authorize=authorize, account_ids=(initial.member_id,), mutate=mutate)


def save_help_type(*, actor, event_id, payload, type_id=None):
    if type_id is None and not all(key in payload for key in ("key", "label")):
        raise ValidationError("A category needs a key and label.")

    def mutate(event, locks):
        row = get_object_or_404(EventHelpType.objects.select_for_update(), event=event, pk=type_id) if type_id else EventHelpType(
            event=event, makerspace_id=event.makerspace_id)
        check_version(row, payload["expected_version"]) if type_id else _zero(payload)
        if type_id and "key" in payload and payload["key"] != row.key:
            raise ValidationError({"key": "A category key cannot change."})
        for key, value in payload.items():
            if key not in ("operation_id", "expected_version"):
                setattr(row, key, value)
        if EventHelpType.objects.filter(event=event, key=row.key).exclude(pk=row.pk).exists():
            raise ProgrammeError("category_exists", "This category key is already in use.")
        _valid(row)
        if type_id:
            row.version += 1
        row.save()
        return row

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="help.category", feature="events.mentoring", permission="manage_team", mutate=mutate,
        status=200 if type_id else 201)


def conflict(*, actor, event_id, payload):
    initial = get_object_or_404(EventRoleAssignment, event_id=event_id, pk=payload["mentor_assignment_id"], role="mentor")

    def authorize(event):
        if initial.member_id != actor.pk or payload["kind"] != "declared":
            event_authority.require(actor, event, "manage_team")
        else:
            policy.mentor_for(actor, event, on_shift=False)

    def mutate(event, locks):
        ports().teams.member_ids(event_id=event.pk, team_id=payload["team_id"])
        row = MentorConflict.objects.select_for_update().filter(event=event, mentor=initial,
            team_id=payload["team_id"], kind=payload["kind"], active=True).first()
        if row:
            check_version(row, payload["expected_version"])
            return commands.changed(row, active=payload["active"], reason=payload["reason"])
        _zero(payload)
        if not payload["active"]:
            raise ProgrammeError("not_found", "Not found.", status=404)
        return commands.new_row(MentorConflict, event, mentor=initial, team_id=payload["team_id"],
            kind=payload["kind"], reason=payload["reason"])

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="mentor.conflict", feature="events.mentoring", permission="mentor_queue",
        authorize=authorize, account_ids=(initial.member_id,), mutate=mutate)


def mute(*, actor, event_id, payload):
    def mutate(event, locks):
        row = MentorAttentionPreference.objects.select_for_update().filter(event=event, member=actor).first()
        if row:
            check_version(row, payload["expected_version"])
        else:
            _zero(payload)
            row = commands.new_row(MentorAttentionPreference, event, member=actor)
        return commands.changed(row, muted_until=timezone.now() + timedelta(minutes=payload["minutes"]) if payload["minutes"] else None)

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="mentor.attention.mute", feature="events.mentor_rounds", permission="mentor_queue", mutate=mutate)


def nominate(*, actor, event_id, round_id, payload):
    def mutate(event, locks):
        mentor, _ = policy.mentor_for(actor, event, on_shift=False)
        round = get_object_or_404(MentorRound.objects.select_for_update(), pk=round_id, event=event)
        check_version(round, payload["expected_version"])
        if not MentorRoundCheckin.objects.filter(round=round, team_id=payload["team_id"], mentor=mentor, away=False).exists():
            raise ProgrammeError("visit_required", "Complete a visit before nominating this team.")
        if MentorNomination.objects.filter(round=round, team_id=payload["team_id"], mentor=mentor).exists():
            raise ProgrammeError("already_nominated", "You already nominated this team in this round.")
        return commands.new_row(MentorNomination, event, mentor=mentor, round=round, team_id=payload["team_id"])

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="mentor.nominate", feature="events.mentor_rounds", permission="mentor_queue", mutate=mutate, status=201)
