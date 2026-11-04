"""Pairwise judge commands. The judge's cursor version is the compare-and-set token.

A judge sees one project at a time. The first is only viewed (`next` moves on); from the second
on they answer "which was better, the one before or this one" (`compare`), or skip / recuse the
current one. Every project shown is a lazily created `JudgeAssignment` (batch `pairwise`), so the
existing conflicts, recusal, coverage and sponsor scoping apply unchanged.
"""

from datetime import timedelta

from django.db.models import Max
from django.http import Http404
from django.utils import timezone

from .boundary import audit, command, mutation, notice, owned
from .conflicts import eligible, require_assignment
from .errors import ProgrammeError, invalid, require_version
from .models_definitions import JudgingRound
from .models_pairwise import JudgePairwiseComparison, JudgePairwiseCursor
from .models_scoring import JudgeAssignment
from .pairwise_assignment import choose
from .pairwise_projection import BATCH, live_snapshots, require_pairwise, selection_state
from .ports import runtime
from .scoring_workflow import _open as require_open, withdraw_locked
from .serializers import CommandInput, ReasonInput, validated
from .serializers_pairwise import CompareInput, SkipInput


def actor_judge(actor, event_id):
    roles = sorted((j for j in runtime().judges(event_id) if j.member_id == actor.pk and j.active
                    and j.event_id == event_id), key=lambda j: j.role_assignment_id)
    if not roles:
        raise Http404
    return roles[0]


def _round(event, round_id):
    round = owned(JudgingRound, event.pk, round_id)
    round.event = event
    if round.mode != "pairwise":
        raise Http404
    require_open(round)
    return round


def _cursor(event, round, judge, expected):
    cursor = JudgePairwiseCursor.objects.select_for_update().filter(round=round, judge_id=judge.role_assignment_id).first()
    if cursor is None:
        if expected != 0:
            raise ProgrammeError("stale_version", "This item changed.", current_version=0)
        return JudgePairwiseCursor(event=event, round=round, judge_id=judge.role_assignment_id, version=0)
    require_version(cursor, expected)
    return cursor


def live(assignment, actor, round, state):
    if assignment is None or assignment.state != state:
        return None
    try:
        require_assignment(actor, assignment, round)
    except Http404:
        return None
    return assignment


def _scope(judge, snapshot):
    return not (judge.room and snapshot.room and judge.room != snapshot.room)


def candidates(round, judge, snapshots):
    """Projects this judge may still be shown: unseen, in their track/room scope and nonconflicted."""
    seen = set(round.assignments.filter(judge_role_assignment_id=judge.role_assignment_id)
               .values_list("submission_snapshot_id", flat=True))
    return [pk for pk, s in snapshots.items() if pk not in seen and _scope(judge, s) and eligible(judge, s, round)]


def select(event, round, judge, cursor):
    """Create the next assignment for this judge, or return None when nothing is left."""
    snapshots = live_snapshots(round)
    since = timezone.now() - timedelta(minutes=round.minutes_per_view)
    in_view = set(round.assignments.filter(state="assigned", assigned_at__gte=since)
                  .exclude(judge_role_assignment_id=judge.role_assignment_id).values_list("submission_snapshot_id", flat=True))
    state, counts = selection_state(round, snapshots)
    previous = cursor.previous.submission_snapshot_id if cursor.previous_id else None
    chosen, counter = choose(candidates(round, judge, snapshots), state=state, judge_id=judge.role_assignment_id, previous=previous,
                             counts=counts, min_reviews=round.min_reviews, in_view=in_view,
                             round_id=round.pk, counter=cursor.draw_count)
    cursor.draw_count = counter
    if chosen is None:
        return None
    project = snapshots[chosen]
    tracks = set(project.track_ids) & set(judge.track_ids) if judge.track_ids else set(project.track_ids)
    return JudgeAssignment.objects.create(event=event, round=round, judge_role_assignment_id=judge.role_assignment_id,
        submission_snapshot_id=chosen, track_id=min(tracks) if tracks else None, room=project.room, batch=BATCH)


def seed_locked(event, round):
    """At open: one cursor per active judge, each with a first project and the existing notice."""
    for judge in sorted(runtime().judges(event.pk), key=lambda j: j.role_assignment_id):
        if not judge.active or judge.event_id != event.pk:
            continue
        cursor = JudgePairwiseCursor(event=event, round=round, judge_id=judge.role_assignment_id)
        cursor.current = select(event, round, judge, cursor)
        cursor.save()
        if cursor.current is not None:
            notice(event, "judge_assigned", cursor.current.pk, cursor.current.version)


def _advance(event, actor, cursor, action=None, **safe):
    cursor.version += 1
    cursor.save()
    if action:
        audit(event, actor, action, cursor, version=cursor.version, round_id=cursor.round_id, **safe)
    return {"id": cursor.pk, "event_id": event.pk, "version": cursor.version, "round_id": cursor.round_id,
            "allowed_actions": []}


def _mark(assignment, state):
    assignment.state = state
    assignment.version += 1
    assignment.save(update_fields=("state", "version"))


def _record(event, round, cursor, previous, current, outcome, notes):
    sequence = (JudgePairwiseComparison.objects.filter(round=round).aggregate(top=Max("sequence"))["top"] or 0) + 1
    return JudgePairwiseComparison.objects.create(event=event, makerspace_id=event.makerspace_id, round=round,
        judge_id=cursor.judge_id, previous=previous, current=current, outcome=outcome, notes=notes,
        submitted_at=timezone.now(), sequence=sequence)


def _run(event_id, round_id, actor, values, suffix, body):
    with mutation(event_id, actor, permission="judge", account_ids=(actor.pk,)) as (event, locks):
        def run():
            require_pairwise(event)
            round = _round(event, round_id)
            cursor = _cursor(event, round, actor_judge(actor, event_id), values["expected_version"])
            return body(event, round, cursor, locks)
        return command(event, actor, values, path=f"judging-rounds/{round_id}/pairwise/{suffix}", run=run)


def next_project(event_id, round_id, *, actor, data):
    values = validated(CommandInput, data)

    def body(event, round, cursor, locks):
        current = live(cursor.current, actor, round, "assigned")
        if current is not None and live(cursor.previous, actor, round, "scored") is not None:
            invalid("Compare or skip the current project first.")
        if current is not None:  # The first project was only viewed; it becomes the anchor.
            _mark(current, "scored")
            cursor.previous = current
        elif live(cursor.previous, actor, round, "scored") is None:
            cursor.previous = None
        cursor.current = select(event, round, actor_judge(actor, event.pk), cursor)
        return _advance(event, actor, cursor, "pairwise_project_shown",
                        assignment_id=cursor.current.pk if cursor.current else None)
    return _run(event_id, round_id, actor, values, "next", body)


def compare(event_id, round_id, *, actor, data):
    values = validated(CompareInput, data)

    def body(event, round, cursor, locks):
        previous, current = live(cursor.previous, actor, round, "scored"), live(cursor.current, actor, round, "assigned")
        if previous is None or current is None:
            invalid("There is no pair to compare. Load the next project.")
        row = _record(event, round, cursor, previous, current, values["outcome"], values["notes"])
        _mark(current, "scored")
        cursor.previous, cursor.current = current, None
        audit(event, actor, "pairwise_compared", row, round_id=round.pk, sequence=row.sequence)
        return _advance(event, actor, cursor)
    return _run(event_id, round_id, actor, values, "compare", body)


def skip_current(event_id, round_id, *, actor, data):
    values = validated(SkipInput, data)

    def body(event, round, cursor, locks):
        current = live(cursor.current, actor, round, "assigned")
        if current is None:
            invalid("There is no project to skip.")
        previous = live(cursor.previous, actor, round, "scored")
        row = _record(event, round, cursor, previous, current, "skip", values["notes"]) if previous else None
        _mark(current, "skipped")
        cursor.current = None
        audit(event, actor, "pairwise_skipped", current, round_id=round.pk, sequence=row.sequence if row else None)
        return _advance(event, actor, cursor)
    return _run(event_id, round_id, actor, values, "skip", body)


def recuse_current(event_id, round_id, *, actor, data):
    values = validated(ReasonInput, data)

    def body(event, round, cursor, locks):
        if live(cursor.current, actor, round, "assigned") is None:
            invalid("There is no project to recuse from.")
        assignment = owned(JudgeAssignment, event.pk, cursor.current_id)
        withdraw_locked(event, actor, round, assignment, action="recuse", text=values["reason"], locks=locks)
        cursor.current = None
        return _advance(event, actor, cursor)
    return _run(event_id, round_id, actor, values, "recuse", body)
