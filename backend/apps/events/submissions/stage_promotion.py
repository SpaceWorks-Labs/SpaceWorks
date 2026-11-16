"""#180 S12: when a shortlisted team withdraws before the next stage opens, promote the next team.

Staff choose it; nothing happens on its own. The next team comes from the shortlist's ranked source
round (every team tied at that rank comes up together). The promotion is a new, already-published
shortlist that amends the current one (append-only), audited, and the promoted team is told when the
event's shortlist email is on.
"""
from django.utils import timezone

from apps.audit.services import record
from .errors import SubmissionError
from .models_projects import HackathonSubmission
from .models_stages import StageShortlist, StageShortlistAnnouncement, StageShortlistEntry, SubmissionStage
from .ports import boundary
from .stage_runtime import published_shortlist, stages_for
from .workflow import canonical_digest


def _next_ranked(current, keep):
    """Rows of the source round's next rank among live candidates not already kept."""
    from apps.events.judging.finalists import ranked_rows
    from .stage_shortlists import candidates
    pool = candidates(current.stage)
    taken = {e.submission_id for e in keep}
    rows = [r for r in ranked_rows(current.source_round) if r["snapshot_id"] in pool
            and pool[r["snapshot_id"]].pk not in taken]
    if not rows:
        return [], pool
    rank = rows[0]["rank"]
    return [r for r in rows if r["rank"] == rank], pool


def promote_next(*, actor, event_id, stage_id, values):
    port = boundary()
    digest = canonical_digest({"promote": stage_id, "withdrawn": values["withdrawn_submission_id"]})
    with port.locked(actor=actor, event_id=event_id, team_id=None, action="stage_shortlist") as ctx:
        replay = port.receipt(event_id=event_id, actor_id=actor.pk, operation_id=str(values["operation_id"]), digest=digest)
        if replay is not None:
            return replay
        stage = SubmissionStage.objects.select_for_update().filter(event=ctx.event, pk=stage_id, shortlist_after=True).first()
        current = published_shortlist(stage) if stage else None
        if current is None:
            raise SubmissionError("invalid_transition", 409)
        following = next((s for s in stages_for(ctx.event.pk) if s.position > stage.position), None)
        if following is not None and following.opens_at and timezone.now() >= following.opens_at:
            raise SubmissionError("next_stage_open", 409)
        withdrawn = HackathonSubmission.objects.filter(event=ctx.event, pk=values["withdrawn_submission_id"],
                                                       state="withdrawn").first()
        entries = list(current.entries.all())
        if withdrawn is None or withdrawn.pk not in {e.submission_id for e in entries}:
            raise SubmissionError("not_a_withdrawn_shortlisted_team", 409)
        if current.source_round_id is None:
            raise SubmissionError("no_ranked_source", 409)
        keep = [e for e in entries if e.submission_id != withdrawn.pk]
        promoted, pool = _next_ranked(current, keep)
        if not promoted:
            raise SubmissionError("no_next_team", 409)
        row = StageShortlist.objects.create(event=ctx.event, stage=stage, source_round=current.source_round,
                                            selection="promoted", amends=current, created_by=actor,
                                            fingerprint=canonical_digest({"amends": current.pk, "out": withdrawn.pk,
                                                                          "in": [r["snapshot_id"] for r in promoted]}))
        for entry in keep:
            StageShortlistEntry.objects.create(shortlist=row, submission_id=entry.submission_id,
                                               snapshot_id=entry.snapshot_id, source_rank=entry.source_rank)
        for item in promoted:
            StageShortlistEntry.objects.create(shortlist=row, submission=pool[item["snapshot_id"]],
                                               snapshot_id=item["snapshot_id"], source_rank=item["rank"])
        announcement = StageShortlistAnnouncement.objects.create(event=ctx.event, shortlist=row,
                                                                 published_at=timezone.now(), published_by=actor)
        record(actor, "event.submission_stage.shortlist_promoted", makerspace=ctx.event.makerspace, target=row,
               meta={"event_id": ctx.event.pk, "stage_id": stage.pk, "shortlist_id": row.pk,
                     "withdrawn_submission_id": withdrawn.pk, "count": len(promoted)})
        from apps.events.judging.options import option
        if option(ctx.event, "shortlist_email"):
            from apps.events.judging.boundary import notice
            notice(ctx.event, "stage_promoted", announcement.pk, 1)
        from .stage_shortlists import projection
        result = projection(ctx.event, stage)
        port.store_receipt(event_id=event_id, actor_id=actor.pk, operation_id=str(values["operation_id"]), digest=digest,
                           result=result)
        return result


def promoted_recipients(announcement_id):
    """Members of the teams a promotion added (not those already on the list)."""
    from apps.events.judging.ports import runtime
    announcement = StageShortlistAnnouncement.objects.select_related("shortlist").filter(pk=announcement_id).first()
    if announcement is None or announcement.shortlist.amends_id is None:
        return ()
    before = set(announcement.shortlist.amends.entries.values_list("submission_id", flat=True))
    added = announcement.shortlist.entries.exclude(submission_id__in=before)
    return tuple(sorted({pk for e in added for pk in runtime().snapshot(e.snapshot_id).member_ids}))
