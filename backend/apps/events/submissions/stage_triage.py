"""Per-stage triage (#180 S5): triage belongs to a project's submission of one stage.

The project's own ``triage`` mirrors its furthest stage's entry, so every reader that predates stages
(reimbursement eligibility, the organiser list, the deadline lock) keeps meaning "the latest work".
A shortlist on a stage refuses while any of that stage's entries is still pending.
"""
from apps.audit.services import record
from .errors import SubmissionError
from .models_stages import SubmissionStageEntry
from .stage_runtime import furthest_entry

TRIAGE = ("pending", "eligible", "ineligible", "hidden")


def apply_locked(*, ctx, port, actor, project, entry, triage, reason):
    """Set one stage entry's triage under the event lock; the caller saves the project."""
    if entry is None or not entry.current_snapshot_id or project.state == "withdrawn":
        raise SubmissionError("invalid_transition", 409)
    if triage in {"ineligible", "hidden"}:
        port.invalidate_snapshot(context=ctx, snapshot_id=entry.current_snapshot_id)
    furthest = furthest_entry(project)
    mirrors = furthest is not None and furthest.pk == entry.pk
    if mirrors and triage == "ineligible" and project.triage != "ineligible":  # L21b: staff disqualification.
        from .entry_fees import on_disqualified
        on_disqualified(event=ctx.event, project=project, actor=actor)
    entry.triage, entry.version = triage, entry.version + 1
    entry.save(update_fields=["triage", "version"])
    if mirrors:
        project.triage, project.triage_reason = triage, reason
    project.version += 1
    record(actor, "event.submission_triaged", makerspace=ctx.event.makerspace, target=project,
           meta={"triage": triage, "version": project.version, "stage_id": entry.stage_id})


def entry_for(project, stage_id):
    rows = SubmissionStageEntry.objects.select_for_update().filter(submission=project)
    if stage_id is None:
        furthest = furthest_entry(project)
        return rows.filter(pk=furthest.pk).first() if furthest else None
    return rows.filter(stage_id=stage_id).first()


def pending_count(stage):
    return SubmissionStageEntry.objects.filter(stage=stage, current_snapshot__isnull=False, triage="pending",
                                               submission__state__in=("submitted", "locked", "under_review", "judged")).count()
