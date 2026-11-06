"""How judging, finalists and awards meet submission stages (#178, #180 S5/S17).

A round judges one stage (``JudgingRound.submission_stage``; empty means the event's last stage), so
for every existing "Single submission" event a round judges exactly what it judged before. An award
must point at a snapshot of the stage its round judges: a team that was not shortlisted at an
earlier gate has no later-stage snapshot, so it can never be placed in a later round or awarded.
"""
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from .stage_runtime import last_stage_id


def stage_snapshots(event_id, stage_id):
    """The port's current snapshots of one stage; an event without stages keeps the unstaged call."""
    from apps.events.judging.ports import runtime
    if stage_id is None:
        return runtime().snapshots(event_id)
    return runtime().snapshots(event_id, stage_id=stage_id)


def round_stage_id(round):
    return round.submission_stage_id or last_stage_id(round.event_id)


def require_triaged(round, stage_id):
    """S5 on a multi-stage event: a round refuses to open while any entry of its stage is pending.
    A single-stage event keeps today's rule (pending projects are simply not judged)."""
    from .models_stages import SubmissionStage
    from .stage_triage import pending_count
    from apps.events.judging.errors import invalid
    if stage_id is None or SubmissionStage.objects.filter(event_id=round.event_id).count() < 2:
        return
    if pending_count(SubmissionStage.objects.get(pk=stage_id)):
        invalid("Triage every submission of this stage before judging it.")


def narrow_to_finalists(snapshots, finalist_ids, stage_id):
    """Finalists advanced from a round on ANOTHER stage carry over by team; on the same stage, by snapshot."""
    from apps.events.judging.ports import runtime
    teams = {s.team_id for s in (runtime().snapshot(pk) for pk in finalist_ids) if s.stage_id != stage_id}
    return [s for s in snapshots if s.id in finalist_ids or s.team_id in teams]


def require_award_stage(rounds, snapshot):
    """S17 invariant: the snapshot belongs to the stage one of the result's rounds judges."""
    if snapshot.stage_id is None:
        return
    if snapshot.stage_id not in {round_stage_id(round) for round in rounds}:
        raise ValidationError({"awards": gettext("An award must go to the work of the stage its judging round judges.")})
