"""Combine C's canonical declarations/mentoring/affiliations with D's recusals."""

from django.http import Http404

from .models_scoring import JudgeConflict
from .ports import runtime


def is_conflicted(*, member_id, team_id, round_id):
    return (JudgeConflict.objects.filter(round_id=round_id, member_id=member_id,
                                         team_id=team_id, active=True).exists()
            or runtime().is_conflicted(member_id=member_id, team_id=team_id, round_id=round_id))


def eligible(judge, snapshot, round):
    return bool(judge.active and judge.event_id == round.event_id == snapshot.event_id
                and snapshot.eligible and snapshot.current and judge.member_id not in snapshot.member_ids
                and (not judge.track_ids or set(judge.track_ids) & set(snapshot.track_ids))
                and not is_conflicted(member_id=judge.member_id, team_id=snapshot.team_id, round_id=round.pk))


def require_assignment(actor, assignment, round):
    from apps.events import event_authority
    # A full manager still cannot score someone else's assignment.
    judge = runtime().judge(assignment.judge_role_assignment_id)
    snapshot = runtime().snapshot(assignment.submission_snapshot_id)
    if (judge.member_id != actor.pk or not eligible(judge, snapshot, round)
            or not event_authority.can(actor, round.event, "judge")):
        raise Http404
    return judge, snapshot
