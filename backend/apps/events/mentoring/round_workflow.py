"""Optional round lifecycle and generation-fenced ten-minute leases."""
from django.utils.translation import gettext
import json
from datetime import timedelta
from uuid import uuid4
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.events.contributions import commands
from apps.events.contributions.errors import ProgrammeError, check_version, require_state
from apps.events.contributions.ports import ports
from .models_rounds import MentorRound, MentorRoundLock, MentorRoundCheckin, MentorConflict
from . import policy

LEASE_TTL = timedelta(minutes=10)


def require_lease(lease, *, mentor_id, lease_uuid, generation, at):
    if (lease.mentor_id != mentor_id or str(lease.lease_uuid) != str(lease_uuid)
            or lease.generation != generation or lease.expires_at <= at):
        raise ProgrammeError("lease_lost", gettext("This visit lease expired or moved to another mentor."))


def transition(*, actor, event_id, round_id, payload, action):
    def mutate(event, locks):
        row = get_object_or_404(MentorRound.objects.select_for_update(), pk=round_id, event=event)
        check_version(row, payload["expected_version"])
        if action == "open":
            require_state(row, "draft")
            if not row.opens_at <= timezone.now() < row.closes_at:
                raise ProgrammeError("round_closed", gettext("The round is outside its scheduled window."))
            if MentorRound.objects.filter(event=event, state="live",
                practice_run_id=row.practice_run_id).exclude(pk=row.pk).exists():
                raise ProgrammeError("round_already_live", gettext("Close the current round first."))
            return commands.changed(row, state="live")
        require_state(row, "draft", "live")
        if action not in ("close", "skip"):
            raise ProgrammeError("invalid_transition", gettext("Unknown round command."), status=400)
        for lease in MentorRoundLock.objects.select_for_update().filter(round=row).order_by("pk"):
            commands.changed(lease, expires_at=timezone.now())
        return commands.changed(row, state="closed" if action == "close" else "skipped")

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action=f"round.{action}", feature="events.mentor_rounds", permission="manage_team", mutate=mutate)


def visit(*, actor, event_id, round_id, team_id, payload, action):
    initial = get_object_or_404(MentorRound, pk=round_id, event_id=event_id)
    prepared = None
    if action == "submit":
        prepared = ports().forms.validate_round(schema=initial.form_schema, answers=payload["answers"])

    def authorize(event):
        policy.mentor_for(actor, event)
        ports().teams.require_eligible(event_id=event.pk, team_id=team_id, at=timezone.now())
        ports().teams.require_practice(event_id=event.pk, team_id=team_id,
            practice_run_id=str(initial.practice_run_id) if initial.practice_run_id else None)

    def mutate(event, locks):
        mentor, profile = policy.mentor_for(actor, event)
        row = MentorRound.objects.select_for_update().get(pk=round_id, event=event)
        now = timezone.now()
        require_state(row, "live")
        if now >= row.closes_at:
            raise ProgrammeError("round_closed", gettext("This round has closed."))
        if MentorRoundCheckin.objects.filter(round=row, team_id=team_id).exists():
            raise ProgrammeError("already_submitted", gettext("This team has already been checked in."))
        lease = MentorRoundLock.objects.select_for_update().filter(round=row, team_id=team_id).first()
        if action == "claim":
            check_version(row, payload["expected_version"])
            if lease and lease.expires_at > now:
                raise ProgrammeError("team_busy", gettext("Another visit is in progress."))
            reason = payload.get("override_reason", "").strip()
            seen = MentorRoundCheckin.objects.filter(event=event, team_id=team_id,
                mentor=mentor, round__practice_run_id=row.practice_run_id).exists()
            conflict = MentorConflict.objects.filter(mentor=mentor, team_id=team_id, active=True,
                kind__in=["declared", "affiliation"]).exists()
            if mentor.member_id in ports().teams.member_ids(event_id=event.pk, team_id=team_id):
                raise ProgrammeError("mentor_conflict", gettext("You cannot visit your own team."), status=403)
            if conflict and not (row.allow_conflict_override and reason):
                raise ProgrammeError("mentor_conflict", gettext("This visit needs a permitted conflict exception."))
            if seen and not (row.allow_fresh_eyes_override and reason):
                raise ProgrammeError("fresh_eyes_required", gettext("Choose a team you have not visited."))
            values = dict(mentor=mentor, lease_uuid=uuid4(), generation=lease.generation + 1 if lease else 1,
                expires_at=min(now + LEASE_TTL, row.closes_at), heartbeat_at=now, started_at=now, overrides=reason)
            if lease:
                return commands.changed(lease, **values)
            return commands.new_row(MentorRoundLock, event, round=row, team_id=team_id, **values)
        if lease is None:
            raise ProgrammeError("lease_lost", gettext("Claim this team before continuing."))
        check_version(lease, payload["expected_version"])
        if mentor.member_id in ports().teams.member_ids(event_id=event.pk, team_id=team_id):
            raise ProgrammeError("mentor_conflict", gettext("You cannot visit your own team."), status=403)
        conflicted_now = MentorConflict.objects.filter(mentor=mentor, team_id=team_id,
            active=True, kind__in=["declared", "affiliation"]).exists()
        if conflicted_now and not (row.allow_conflict_override and lease.overrides.strip()):
            raise ProgrammeError("mentor_conflict", gettext("This visit is no longer eligible."))
        require_lease(lease, mentor_id=mentor.pk, lease_uuid=payload["lease_uuid"],
                      generation=payload["generation"], at=now)
        if action == "heartbeat":
            return commands.changed(lease, expires_at=min(now + LEASE_TTL, row.closes_at), heartbeat_at=now)
        if action == "release":
            return commands.changed(lease, expires_at=now)
        if action != "submit":
            raise ProgrammeError("invalid_transition", gettext("Unknown visit command."), status=400)
        if payload.get("nominate") and payload.get("away"):
            raise ProgrammeError("visit_required", gettext("An away visit cannot nominate a team."), status=400)
        if initial.version != row.version or initial.form_schema_version != row.form_schema_version:
            raise ProgrammeError("form_revision_changed", gettext("The round form changed; review it again."))
        result = commands.new_row(MentorRoundCheckin, event, team_id=team_id, round=row, mentor=mentor,
            form_snapshot=row.form_schema, answers=json.dumps(prepared, separators=(",", ":")),
            overrides=lease.overrides, started_at=lease.started_at,
            submitted_at=now, away=payload.get("away", False))
        if payload.get("nominate"):
            from .models_rounds import MentorNomination
            commands.new_row(MentorNomination, event, mentor=mentor, team_id=team_id, round=row)
        from .round_triggers import fire_locked
        fire_locked(actor=actor, event=event, round=row, team_id=team_id, answers=prepared, locks=locks)
        commands.changed(lease, expires_at=now)
        return result

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action=f"round.visit.{action}", feature="events.mentor_rounds", permission="mentor_queue",
        authorize=authorize, mutate=mutate, status=201 if action == "submit" else 200)
