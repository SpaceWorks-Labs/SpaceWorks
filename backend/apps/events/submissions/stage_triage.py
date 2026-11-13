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


def reinstate_locked(*, ctx, actor, project, entry, reason):
    """E-B4 (D7): undo a disqualification under the event lock; the caller saves the project.

    Only an ``ineligible`` entry can be reinstated. Its entry-fee case is voided while still open, and the
    project's invalidated judging work comes back (see ``judging.reinstate``). Returns the counts."""
    if entry is None or entry.triage != "ineligible" or not entry.current_snapshot_id or project.state == "withdrawn":
        raise SubmissionError("not_disqualified", 409)
    furthest = furthest_entry(project)
    mirrors = furthest is not None and furthest.pk == entry.pk
    voided = False
    if mirrors:
        from .entry_fees import on_reinstated
        voided = on_reinstated(event=ctx.event, project=project, actor=actor)
    entry.triage, entry.version = "eligible", entry.version + 1
    entry.save(update_fields=["triage", "version"])
    if mirrors:
        project.triage, project.triage_reason = "eligible", reason
    project.version += 1
    from apps.events.judging.reinstate import reinstate_snapshot_locked
    from apps.events.programme_locks import current_locks
    counts = reinstate_snapshot_locked(event=ctx.event, snapshot_id=entry.current_snapshot_id,
                                       locks=current_locks(ctx.event.pk), actor=actor)
    record(actor, "event.submission_reinstated", makerspace=ctx.event.makerspace, target=project,
           meta={"event_id": ctx.event.pk, "stage_id": entry.stage_id, "version": project.version,
                 "fee_case_voided": voided, **counts})
    return counts


def entry_for(project, stage_id):
    rows = SubmissionStageEntry.objects.select_for_update().filter(submission=project)
    if stage_id is None:
        furthest = furthest_entry(project)
        return rows.filter(pk=furthest.pk).first() if furthest else None
    return rows.filter(stage_id=stage_id).first()


def pending_count(stage):
    return SubmissionStageEntry.objects.filter(stage=stage, current_snapshot__isnull=False, triage="pending",
                                               submission__state__in=("submitted", "locked", "under_review", "judged")).count()
