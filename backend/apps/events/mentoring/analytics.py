"""Private diagnostics and F's read-only readiness summary; practice is excluded."""
import hashlib
import json
import math
from statistics import mean, median
from django.utils import timezone
from apps.events import event_authority
from apps.events.contributions.errors import ProgrammeError
from .models_queue import EventHelpRequest
from .models_rounds import MentorRound, MentorRoundCheckin, MentorRoundLock


def distribution(values):
    values = sorted(values)
    if not values:
        return {"n": 0, "average_seconds": None, "median_seconds": None, "p90_seconds": None}
    return {"n": len(values), "average_seconds": round(mean(values), 2),
        "median_seconds": round(median(values), 2), "p90_seconds": values[max(0, math.ceil(len(values) * .9) - 1)]}


def stable_due_order(team_ids, *, event_id, round_id, mentor_id):
    # Original SHA-256 ordering, inspired by Mentor Desk's spread-order idea.
    # Mentor Desk: MIT, copyright 2026 Jasim (jasimcm) and contributors.
    return sorted(team_ids, key=lambda pk: hashlib.sha256(
        f"spaceworks:mentor-spread:v1:{event_id}:{round_id}:{mentor_id}:{pk}".encode()).digest())[:8]


def summary(*, actor, event, own_mentor_id=None):
    manager = event_authority.can(actor, event, None)
    if not manager:
        from .policy import mentor_for
        assignment, _ = mentor_for(actor, event, on_shift=False)
        if own_mentor_id not in (None, assignment.pk):
            raise ProgrammeError("not_found", "Not found.", status=404)
        own_mentor_id = assignment.pk
    checks = MentorRoundCheckin.objects.filter(event=event, round__practice_run_id__isnull=True)
    help_rows = EventHelpRequest.objects.filter(event=event, practice_run_id__isnull=True)
    leases = MentorRoundLock.objects.filter(event=event, round__practice_run_id__isnull=True)
    if own_mentor_id:
        from apps.events.contributions.models_roles import EventRoleAssignment
        owner_id = EventRoleAssignment.objects.get(pk=own_mentor_id, event=event).member_id
        checks = checks.filter(mentor_id=own_mentor_id)
        # Historical assignee is read from immutable action authors, not a cleared claimed_by.
        help_rows = help_rows.filter(actions__actor_id=owner_id).distinct()
        leases = leases.filter(mentor_id=own_mentor_id)
    responses, durations = [], []
    for row in help_rows:
        if row.first_claimed_at:
            responses.append(max(0, int((row.first_claimed_at - row.created_at).total_seconds())))
        if row.resolved_at and row.first_claimed_at:
            started, elapsed = None, 0
            for action in row.actions.order_by("created_at", "pk"):
                if action.kind in ("claim", "assign"):
                    if started is not None:
                        elapsed += max(0, int((action.created_at - started).total_seconds()))
                    started = action.created_at
                elif action.kind in ("release", "resolve", "cancel") and started is not None:
                    elapsed += max(0, int((action.created_at - started).total_seconds()))
                    started = None
            durations.append(elapsed)
    visits = [max(0, int((row.submitted_at - row.started_at).total_seconds())) for row in checks]
    from .diagnostics import project
    return {**project(event=event, mentor_id=own_mentor_id),
        "completed_checkins": checks.count(), "open_help": help_rows.filter(state="open").count(),
        "first_response": distribution(responses), "help_duration": distribution(durations),
        "visit_duration": distribution(visits),
        "expired_leases": leases.filter(expires_at__lte=timezone.now()).exclude(
            team_id__in=checks.values("team_id")).count(),
        "scope": "event" if manager and own_mentor_id is None else "own"}


def prior_notes(*, event_id, team_id, practice_run_id=None):
    rows = MentorRoundCheckin.objects.filter(event_id=event_id, team_id=team_id,
        round__practice_run_id=practice_run_id).select_related("round").order_by("submitted_at")
    # Ratings are never copied into the next mentor's view.
    return [{"round_id": row.round_id, "notes": {key: value for key, value in json.loads(row.answers).items()
        if key in row.round.note_keys and key not in row.round.rating_keys}, "away": row.away} for row in rows]
