"""Staff commands on one stage: per-team deadline extensions (#180 S2) and bulk triage (S5)."""
from apps.audit.services import record
from .errors import SubmissionError
from .models_projects import HackathonSubmission
from .models_stages import StageExtension, SubmissionStage, SubmissionStageEntry
from .ports import boundary
from .stage_triage import apply_locked
from .workflow import canonical_digest


def _stage(event, stage_id):
    stage = SubmissionStage.objects.select_for_update().filter(event=event, pk=stage_id).first()
    if stage is None:
        raise SubmissionError("not_found", 404)
    return stage


def extend(*, actor, event_id, stage_id, values):
    """Give one team a later deadline for one stage. Append-only; the latest ``until`` wins."""
    from apps.events.hackathons.team_models import HackathonTeam
    port = boundary()
    digest = canonical_digest({"extend": stage_id, "team": values["team_id"], "until": values["until"].isoformat(),
                               "reason": values["reason"]})
    with port.locked(actor=actor, event_id=event_id, team_id=None, action="stage_extension") as ctx:
        replay = port.receipt(event_id=event_id, actor_id=actor.pk, operation_id=str(values["operation_id"]), digest=digest)
        if replay is not None:
            return replay
        stage = _stage(ctx.event, stage_id)
        team = HackathonTeam.objects.filter(event=ctx.event, pk=values["team_id"]).first()
        if team is None:
            raise SubmissionError("not_found", 404)
        if values["until"] > ctx.event.ends_at:
            raise SubmissionError("invalid_extension", 400, reason="after_event")
        row = StageExtension.objects.create(stage=stage, team=team, until=values["until"], reason=values["reason"],
                                            created_by=actor)
        record(actor, "event.submission_stage.extension_granted", makerspace=ctx.event.makerspace, target=row,
               meta={"event_id": ctx.event.pk, "stage_id": stage.pk, "team_id": team.pk, "until": values["until"].isoformat()})
        result = {"id": row.pk, "stage_id": stage.pk, "team_id": team.pk, "team_name": team.name, "until": row.until,
                  "reason": row.reason, "created_at": row.created_at}
        port.store_receipt(event_id=event_id, actor_id=actor.pk, operation_id=str(values["operation_id"]), digest=digest,
                           result=result)
        return result


def bulk_triage(*, actor, event_id, stage_id, values):
    """Mark many of a stage's submissions at once (S5), e.g. every pending one as eligible."""
    port = boundary()
    digest = canonical_digest({"triage": stage_id, "ids": sorted(values["submission_ids"]), "to": values["triage"],
                               "reason": values["reason"]})
    with port.locked(actor=actor, event_id=event_id, team_id=None, action="triage") as ctx:
        replay = port.receipt(event_id=event_id, actor_id=actor.pk, operation_id=str(values["operation_id"]), digest=digest)
        if replay is not None:
            return replay
        stage = _stage(ctx.event, stage_id)
        projects = list(HackathonSubmission.objects.select_for_update().filter(
            event=ctx.event, pk__in=values["submission_ids"]).order_by("pk"))
        if len(projects) != len(set(values["submission_ids"])):
            raise SubmissionError("not_found", 404)
        for project in projects:
            entry = SubmissionStageEntry.objects.select_for_update().filter(submission=project, stage=stage).first()
            apply_locked(ctx=ctx, port=port, actor=actor, project=project, entry=entry, triage=values["triage"],
                         reason=values["reason"])
            project.save(update_fields=["triage", "triage_reason", "version"])
        result = {"stage_id": stage.pk, "updated": len(projects), "triage": values["triage"]}
        port.store_receipt(event_id=event_id, actor_id=actor.pk, operation_id=str(values["operation_id"]), digest=digest,
                           result=result)
        return result
