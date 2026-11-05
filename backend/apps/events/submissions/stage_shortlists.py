"""Shortlist gates after a submission stage (#179), on L21b's finalists engine.

Preview, then apply under the event lock with the preview's fingerprint, then publish once. The
selection is top N from a finalized judging round on that stage (ties at the cutoff all advance),
or hand-picked from the stage's eligible submissions. Applying closes the stage to submissions;
publishing opens the next stage to the chosen teams only. The rest are "not shortlisted": they keep
every earlier snapshot. Both results are told by email when the event's shortlist switch is on.
A shortlist refuses while any of the stage's submissions is untriaged (S5).
"""
from django.utils import timezone

from apps.audit.services import record
from apps.events.judging.ports import runtime
from .errors import SubmissionError
from .models_projects import HackathonSubmission
from .models_stages import StageShortlist, StageShortlistAnnouncement, StageShortlistEntry, SubmissionStage, SubmissionStageEntry
from .ports import boundary
from .stage_judging import round_stage_id
from .stage_triage import pending_count
from .workflow import canonical_digest

LIVE = ("submitted", "locked", "under_review", "judged")


def _stage(event, stage_id, *, lock=False):
    rows = SubmissionStage.objects.select_for_update() if lock else SubmissionStage.objects
    stage = rows.filter(event=event, pk=stage_id).first()
    if stage is None:
        raise SubmissionError("not_found", 404)
    if not stage.shortlist_after:
        raise SubmissionError("shortlist_not_enabled", 409)
    return stage


def candidates(stage):
    """{snapshot_id: submission} for the stage's current, eligible, live submissions."""
    rows = SubmissionStageEntry.objects.select_related("submission").filter(
        stage=stage, current_snapshot__isnull=False, triage="eligible", submission__state__in=LIVE)
    return {row.current_snapshot_id: row.submission for row in rows}


def plan(event, stage, values):
    from apps.events.judging.finalists import ranked_rows, select_ranked
    from apps.events.judging.models_definitions import JudgingRound
    if pending_count(stage):
        raise SubmissionError("triage_pending", 409, limit=str(pending_count(stage)))
    pool = candidates(stage)
    source = None
    if values.get("source_round_id"):
        source = JudgingRound.objects.filter(event=event, pk=values["source_round_id"]).first()
        if source is None:
            raise SubmissionError("not_found", 404)
        if source.state != "finalized" or round_stage_id(source) != stage.pk:
            raise SubmissionError("invalid_source_round", 409)
        rows = [r for r in ranked_rows(source) if r["snapshot_id"] in pool]
    else:
        rows = [{"snapshot_id": pk, "rank": None} for pk in sorted(pool)]
    if values["selection"] == "top_n":
        if source is None:
            raise SubmissionError("invalid_source_round", 400)
        chosen, tied = select_ranked(rows, selection="top_n", top_n=values["top_n"])
    else:
        by_submission = {submission.pk: pk for pk, submission in pool.items()}
        if any(pk not in by_submission for pk in values.get("submission_ids", [])):
            raise SubmissionError("invalid_selection", 400)
        wanted = {by_submission[pk] for pk in values.get("submission_ids", [])}
        chosen, tied = [r for r in rows if r["snapshot_id"] in wanted], False
        if source is not None and len(chosen) != len(wanted):
            raise SubmissionError("invalid_selection", 400)  # Hand-picks from a round must be reviewed in it.
        if source is None:
            chosen = [{"snapshot_id": pk, "rank": None} for pk in sorted(wanted)]
    entries = [{"submission_id": pool[r["snapshot_id"]].pk, "team_id": pool[r["snapshot_id"]].team_id,
                "snapshot_id": r["snapshot_id"], "title": runtime().snapshot(r["snapshot_id"]).title,
                "source_rank": r["rank"]} for r in chosen]
    from apps.events.judging.options import option
    fingerprint = canonical_digest({"stage": [stage.pk, stage.version], "round": [source.pk, source.version] if source else None,
                                    "selection": values["selection"], "top_n": values.get("top_n"),
                                    "entries": [[e["submission_id"], e["snapshot_id"]] for e in entries]})
    return {"stage_id": stage.pk, "source_round_id": source.pk if source else None, "selection": values["selection"],
            "top_n": values.get("top_n"), "tied_at_cutoff": tied, "fingerprint": fingerprint, "entries": entries,
            "candidates": len(pool), "not_shortlisted": len(pool) - len(entries),
            "email_enabled": bool(option(event, "shortlist_email"))}


def preview(*, actor, event_id, stage_id, values):
    with boundary().locked(actor=actor, event_id=event_id, team_id=None, action="stage_shortlist") as ctx:
        return plan(ctx.event, _stage(ctx.event, stage_id), values)


def apply(*, actor, event_id, stage_id, values):
    port = boundary()
    digest = canonical_digest({"apply": stage_id, **{k: str(v) for k, v in values.items()}})
    with port.locked(actor=actor, event_id=event_id, team_id=None, action="stage_shortlist") as ctx:
        replay = port.receipt(event_id=event_id, actor_id=actor.pk, operation_id=str(values["operation_id"]), digest=digest)
        if replay is not None:
            return replay
        stage = _stage(ctx.event, stage_id, lock=True)
        if StageShortlistAnnouncement.objects.filter(shortlist__stage=stage).exists():
            raise SubmissionError("shortlist_published", 409)
        result = plan(ctx.event, stage, values)
        if result["fingerprint"] != values["fingerprint"]:
            raise SubmissionError("plan_changed", 409)
        if not result["entries"]:
            raise SubmissionError("shortlist_empty", 409)
        row = StageShortlist.objects.create(event=ctx.event, stage=stage, source_round_id=result["source_round_id"],
                                            selection=values["selection"], top_n=values.get("top_n"),
                                            fingerprint=result["fingerprint"], created_by=actor)
        for entry in result["entries"]:
            StageShortlistEntry.objects.create(shortlist=row, submission_id=entry["submission_id"],
                                               snapshot_id=entry["snapshot_id"], source_rank=entry["source_rank"])
        record(actor, "event.submission_stage.shortlist_applied", makerspace=ctx.event.makerspace, target=row,
               meta={"event_id": ctx.event.pk, "stage_id": stage.pk, "count": len(result["entries"]),
                     "selection": values["selection"]})
        result = projection(ctx.event, stage)
        port.store_receipt(event_id=event_id, actor_id=actor.pk, operation_id=str(values["operation_id"]), digest=digest,
                           result=result)
        return result


def publish(*, actor, event_id, stage_id, values):
    from apps.events import event_authority
    port = boundary()
    digest = canonical_digest({"publish": stage_id, "shortlist": values["shortlist_id"]})
    with port.locked(actor=actor, event_id=event_id, team_id=None, action="stage_shortlist") as ctx:
        event_authority.require(actor, ctx.event, None)  # Publishing is the full event manager's, like finalists.
        replay = port.receipt(event_id=event_id, actor_id=actor.pk, operation_id=str(values["operation_id"]), digest=digest)
        if replay is not None:
            return replay
        stage = _stage(ctx.event, stage_id, lock=True)
        current = stage.shortlists.order_by("-pk").first()
        if current is None or current.pk != values["shortlist_id"]:
            raise SubmissionError("invalid_transition", 409)
        if StageShortlistAnnouncement.objects.filter(shortlist__stage=stage).exists():
            raise SubmissionError("shortlist_published", 409)
        row = StageShortlistAnnouncement.objects.create(event=ctx.event, shortlist=current, published_at=timezone.now(),
                                                        published_by=actor)
        record(actor, "event.submission_stage.shortlist_published", makerspace=ctx.event.makerspace, target=row,
               meta={"event_id": ctx.event.pk, "stage_id": stage.pk, "shortlist_id": current.pk})
        from apps.events.judging.options import option
        if option(ctx.event, "shortlist_email"):
            from apps.events.judging.boundary import notice
            notice(ctx.event, "stage_shortlisted", row.pk, 1)
            notice(ctx.event, "stage_not_shortlisted", row.pk, 1)
        result = projection(ctx.event, stage)
        port.store_receipt(event_id=event_id, actor_id=actor.pk, operation_id=str(values["operation_id"]), digest=digest,
                           result=result)
        return result


def read(*, actor, event_id, stage_id):
    with boundary().locked(actor=actor, event_id=event_id, team_id=None, action="admin_read") as ctx:
        return projection(ctx.event, _stage(ctx.event, stage_id))


def projection(event, stage):
    from apps.events.judging.options import option
    current = stage.shortlists.order_by("-pk").first()
    announcement = StageShortlistAnnouncement.objects.filter(shortlist=current).first() if current else None
    entries = [{"submission_id": e.submission_id, "team_id": HackathonSubmission.objects.get(pk=e.submission_id).team_id,
                "snapshot_id": e.snapshot_id, "title": runtime().snapshot(e.snapshot_id).title, "source_rank": e.source_rank}
               for e in (current.entries.order_by("source_rank", "submission_id") if current else [])]
    pool = candidates(stage)
    published = announcement is not None
    return {"stage_id": stage.pk, "label": stage.shortlist_label, "pending_triage": pending_count(stage),
            "candidates": len(pool), "email_enabled": bool(option(event, "shortlist_email")),
            "current": {"id": current.pk, "selection": current.selection, "top_n": current.top_n,
                        "source_round_id": current.source_round_id, "created_at": current.created_at,
                        "published_at": announcement.published_at if announcement else None,
                        "entries": entries} if current else None,
            "allowed_actions": [] if published else (["apply", "publish"] if current else ["apply"])}


def recipients(kind, announcement_id):
    """Members told about a published shortlist: the chosen teams, or the stage's other live teams."""
    announcement = StageShortlistAnnouncement.objects.select_related("shortlist__stage").filter(pk=announcement_id).first()
    if announcement is None:
        return ()
    shortlist = announcement.shortlist
    chosen = set(shortlist.entries.values_list("submission_id", flat=True))
    rows = SubmissionStageEntry.objects.filter(stage=shortlist.stage, current_snapshot__isnull=False,
                                               submission__state__in=LIVE)
    picked = [r for r in rows if (r.submission_id in chosen) == (kind == "stage_shortlisted")]
    return tuple(sorted({pk for r in picked for pk in runtime().snapshot(r.current_snapshot_id).member_ids}))
