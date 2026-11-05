"""The only help state writer. Team and mentor origins are explicit."""
from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.events.contributions import commands
from apps.events.contributions.errors import ProgrammeError, check_version, require_state
from apps.events.contributions.ports import ports
from . import policy
from .models_queue import EventHelpRequest, EventHelpType, EventHelpAction, EventHelpComment
from .models_rounds import MentorNotificationIntent
from . import help_expiry


def notice_locked(request, event, kind):
    if request.practice_run_id is None:
        notice, created = MentorNotificationIntent.objects.get_or_create(request=request, kind=kind,
            generation=request.version, defaults={"event": event, "makerspace_id": event.makerspace_id,
                                                  "available_at": timezone.now()})
        if created:
            from apps.events.contributions.notifications import enqueue_on_commit
            enqueue_on_commit(kind="mentor_help", notice_id=notice.pk)


def _team(actor, event, team_id):
    commands.active_member(actor)
    ports().teams.require_member(actor_id=actor.pk, event_id=event.pk, team_id=team_id)
    ports().teams.require_eligible(event_id=event.pk, team_id=team_id, at=timezone.now())


def _attendee(actor, event):
    """A drop-in asker (#128 C-36, E2-f): a confirmed registrant of an event without teams."""
    from apps.events.models import EventRegistration
    commands.active_member(actor)
    if not policy.drop_in_allowed(event):
        raise ProgrammeError("team_required", "Ask for help from your team's page.", status=400)
    if not EventRegistration.objects.filter(event=event, member=actor, status__in=("registered", "attended")).exists():
        raise ProgrammeError("registration_required", "Only confirmed attendees can ask a mentor.", status=403)


def _asker(actor, event, row):
    """Member-surface access to one request: its team, or the drop-in who raised it."""
    if row.team_id is None:
        _attendee(actor, event)
        if row.raised_by_id != actor.pk:
            raise ProgrammeError("not_found", "Not found.", status=404)
    else:
        _team(actor, event, row.team_id)


def create(*, actor, event_id, payload, mentor_origin=False):
    team_id = payload.get("team_id")
    drop_in = team_id is None and not mentor_origin

    def authorize(event):
        if team_id is None and mentor_origin:
            raise ProgrammeError("team_required", "Choose the team you are raising help for.", status=400)
        if drop_in:
            _attendee(actor, event)
        elif mentor_origin:
            assignment, profile = policy.mentor_for(actor, event)
            if not policy.visit_eligible(assignment=assignment, profile=profile, team_id=team_id):
                raise ProgrammeError("mentor_not_eligible", "You cannot visit this team.", status=403)
        else:
            _team(actor, event, team_id)

    def mutate(event, locks):
        help_type = EventHelpType.objects.filter(event=event, key=payload["type_key"]).first()
        if not help_type:
            raise ProgrammeError("invalid_help_type", "Choose an available help category.", status=400)
        if payload["expected_version"] != 0:
            raise ProgrammeError("stale_version", "Use version zero for a new request.")
        practice = payload.get("practice_run_id")
        if drop_in:
            if practice:
                raise ProgrammeError("practice_scope_mismatch", "Practice runs use teams.", status=404)
            rows = EventHelpRequest.objects.filter(event=event, team__isnull=True, raised_by=actor, type=help_type,
                                                   state__in=["open", "claimed"])
        else:
            ports().teams.require_practice(event_id=event.pk, team_id=team_id,
                                           practice_run_id=str(practice) if practice else None)
            rows = EventHelpRequest.objects.filter(event=event, team_id=team_id, type=help_type,
                practice_run_id=practice, state__in=["open", "claimed"])
        if rows.count() >= help_type.open_limit:
            raise ProgrammeError("help_limit_reached", "There is already an open request in this category.")
        assignment = policy.mentor_for(actor, event)[0] if mentor_origin else None
        if mentor_origin:
            _, profile = policy.mentor_for(actor, event)
            if not policy.visit_eligible(assignment=assignment, profile=profile, team_id=team_id,
                                         skill_tags=help_type.skill_tags):
                raise ProgrammeError("mentor_not_eligible", "This category needs another mentor.", status=403)
        row = commands.new_row(EventHelpRequest, event, team_id=team_id, type=help_type,
            raised_by=actor, raised_by_role_assignment=assignment,
            origin="mentor" if mentor_origin else "attendee" if drop_in else "team", structured_zone=payload.get("zone", {}),
            summary=payload["summary"], priority=help_type.priority,
            exclusive_until=timezone.now() + timedelta(minutes=5), practice_run_id=practice,
            expires_at=min(event.ends_at, timezone.now() + timedelta(minutes=help_type.expiry_minutes)))
        notice_locked(row, event, "created")
        return row

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action=("help.raise_mentor" if mentor_origin else "help.raise_drop_in" if drop_in else "help.raise_team"),
        feature="events.mentoring",
        permission="mentor_queue" if mentor_origin else False, authorize=authorize, mutate=mutate, status=201)


def _detail_access(actor, event, row, *, member_surface=False):
    if member_surface:
        _asker(actor, event, row)
    elif not policy.queue_manager(actor, event):
        assignment, _ = policy.mentor_for(actor, event)
        if row.claimed_by_id != assignment.pk:
            raise ProgrammeError("not_found", "Not found.", status=404)
        if not help_expiry.live_claim(row):
            raise ProgrammeError("lease_lost", "This help claim expired. Refresh the queue.")


def command(*, actor, event_id, help_id, payload, action, member_surface=False):
    initial = get_object_or_404(EventHelpRequest, pk=help_id, event_id=event_id)
    from apps.events.contributions.models_roles import EventRoleAssignment
    target = get_object_or_404(EventRoleAssignment, pk=payload["mentor_assignment_id"],
        event_id=event_id, role="mentor") if action == "assign" else None

    def authorize(event):
        current = get_object_or_404(EventHelpRequest, pk=help_id, event=event)
        if member_surface:
            _asker(actor, event, current)
        elif action in ("reopen", "assign"):
            policy.require_queue_manager(actor, event)
        elif action != "claim":
            # Authorization for retry is the live queue role. The current claim
            # is checked below only when the receipt does not already exist.
            if not policy.queue_manager(actor, event):
                policy.mentor_for(actor, event)

    def mutate(event, locks):
        row = EventHelpRequest.objects.select_for_update().get(pk=help_id, event=event)
        if not member_surface and action in ("release", "resolve"):
            _detail_access(actor, event, row)
        check_version(row, payload["expected_version"])
        help_expiry.require_live(row, event)
        now = timezone.now()
        old_assignee = row.claimed_by_id
        note = payload.get("resolution_note", payload.get("reason", ""))
        if action in ("claim", "assign"):
            require_state(row, "open" if action == "claim" else "open", "claimed" if action == "assign" else "open")
            if action == "assign":
                from apps.events.contributions.models_roles import EventRoleAssignment
                target = get_object_or_404(EventRoleAssignment, pk=payload["mentor_assignment_id"], event=event)
                assignment, profile = policy.mentor_for(target.member, event, assignment_id=target.pk)
            else:
                assignment, profile = policy.mentor_for(actor, event)
            if not policy.request_eligible(assignment=assignment, profile=profile, row=row,
                    skill_tags=row.type.skill_tags, priority_until=row.exclusive_until):
                raise ProgrammeError("mentor_not_eligible", "This request needs another mentor.", status=403)
            if EventHelpRequest.objects.filter(state="claimed", claimed_by=assignment,
                    claim_expires_at__gt=now).exclude(pk=row.pk).exists():
                raise ProgrammeError("mentor_busy", "Finish or release the current request first.")
            # Clean expired claims under the same parent lock before the DB's
            # one-claimed-ticket constraint is consulted.
            for stale in EventHelpRequest.objects.select_for_update().filter(state="claimed",
                    event=event, claimed_by=assignment).exclude(pk=row.pk):
                help_expiry.release_locked(row=stale, event=event, kind="lease_expired")
            commands.changed(row, state="claimed", claimed_by=assignment,
                first_claimed_at=row.first_claimed_at or now, last_claimed_at=now,
                **help_expiry.claim_values(row, event, now))
        elif action == "renew":
            require_state(row, "claimed")
            assignment, profile = policy.mentor_for(actor, event)
            if row.claimed_by_id != assignment.pk or str(row.claim_uuid) != str(payload["claim_uuid"]) or row.claim_generation != payload["claim_generation"]:
                raise ProgrammeError("lease_lost", "This claim belongs to another visit.")
            if not policy.request_eligible(assignment=assignment, profile=profile, row=row,
                    skill_tags=row.type.skill_tags):
                raise ProgrammeError("mentor_not_eligible", "This claim is no longer eligible.", status=403)
            commands.changed(row, claim_expires_at=min(help_expiry.deadline(row, event),
                now + timedelta(minutes=row.type.claim_minutes)))
        elif action == "release":
            require_state(row, "claimed")
            commands.changed(row, state="open", claimed_by=None, last_opened_at=now,
                             claim_uuid=None, claim_expires_at=None, open_generation=row.open_generation + 1)
        elif action == "resolve":
            require_state(row, "claimed")
            commands.changed(row, state="resolved", claimed_by=None, resolved_at=now,
                             claim_uuid=None, claim_expires_at=None)
        elif action == "reopen":
            require_state(row, "resolved")
            if not note.strip():
                raise ProgrammeError("reason_required", "Explain why the request is reopening.", status=400)
            commands.changed(row, state="open", resolved_at=None, exclusive_until=now + timedelta(minutes=5),
                             last_opened_at=now, open_generation=row.open_generation + 1)
        elif action == "cancel" and member_surface:
            require_state(row, "open", "claimed")
            commands.changed(row, state="cancelled", claimed_by=None, cancelled_at=now,
                             claim_uuid=None, claim_expires_at=None)
        else:
            raise ProgrammeError("invalid_transition", "Unknown help command.", status=400)
        commands.new_row(EventHelpAction, event, request=row, actor=actor, kind=action, note=note)
        notice_locked(row, event, "claim_released" if old_assignee and not row.claimed_by_id else action)
        return row

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action=f"help.{action}", feature="events.mentoring", permission=False if member_surface else "mentor_queue",
        authorize=authorize, mutate=mutate, account_ids=(target.member_id,) if target else (),
        authority_ids=(target.member_id,) if target else ())


def comment(*, actor, event_id, help_id, payload, member_surface=False):
    initial = get_object_or_404(EventHelpRequest, pk=help_id, event_id=event_id)

    def authorize(event):
        current = get_object_or_404(EventHelpRequest, pk=help_id, event=event)
        _detail_access(actor, event, current, member_surface=member_surface)

    def mutate(event, locks):
        row = EventHelpRequest.objects.select_for_update().get(pk=help_id, event=event)
        check_version(row, payload["expected_version"])
        if row.state not in ("open", "claimed"):
            raise ProgrammeError("request_closed", "This request is closed.")
        help_expiry.require_live(row, event)
        if not payload["body"].strip() or len(payload["body"]) > 2000:
            raise ProgrammeError("comment_too_long", "Use 1–2000 characters.", status=400)
        commands.changed(row)
        return commands.new_row(EventHelpComment, event, request=row, author=actor,
            origin="team" if member_surface else "mentor", body=payload["body"])

    return commands.run(actor=actor, event_id=event_id, operation_id=payload["operation_id"], payload=payload,
        action="help.comment", feature="events.mentoring", permission=False if member_surface else "mentor_queue",
        authorize=authorize, mutate=mutate, status=201)
