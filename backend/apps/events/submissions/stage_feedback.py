"""#180 S4: judges' team feedback, released per round (switch ``share_feedback``, off by default).

A round's feedback reaches the team only once the round is finalized AND either the shortlist of the
stage it judged or a result that includes it has been published. The team reads the text alone,
never the judge's name, notes or scores.
"""
from .stage_runtime import published_shortlist


def released(round):
    from apps.events.judging.models_results import EventResultRound, ResultAnnouncement
    from .stage_judging import round_stage_id
    from .models_stages import SubmissionStage
    if not round.share_feedback or round.state != "finalized":
        return False
    stage = SubmissionStage.objects.filter(pk=round_stage_id(round)).first()
    if stage is not None and published_shortlist(stage) is not None:
        return True
    results = EventResultRound.objects.filter(round=round).values_list("result_id", flat=True)
    return ResultAnnouncement.objects.filter(result_id__in=list(results)).exists()


def released_feedback(stage, project):
    """The released feedback texts on this project's work for one stage, oldest round first."""
    if project is None or project.pk is None:
        return []
    from apps.events.judging.models_definitions import JudgingRound
    from apps.events.judging.models_scoring import JudgeScore
    from .models_stages import SnapshotStage
    snapshots = list(SnapshotStage.objects.filter(stage=stage, snapshot__submission=project)
                     .values_list("snapshot_id", flat=True))
    if not snapshots:
        return []
    texts = []
    rounds = JudgingRound.objects.filter(event_id=stage.event_id, share_feedback=True, state="finalized").order_by("pk")
    for round in rounds:
        if not released(round):
            continue
        for score in (JudgeScore.objects.filter(assignment__round=round, assignment__submission_snapshot_id__in=snapshots,
                                                assignment__state="scored", submitted_at__isnull=False)
                      .order_by("pk")):
            if score.team_feedback.strip():
                texts.append(score.team_feedback.strip())
    return texts
