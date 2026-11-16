"""Stage-aware participation evidence for money that depends on submitting (#180 G11, S17 seam).

``submission_evidence`` answers "which frozen snapshot shows this member met the rule?" for travel
reimbursement (and any later stage-based eligibility). Modes: ``any_stage`` (the old yes), ``stage``
(a position), ``final_stage``, ``shortlisted_at`` (a position whose shortlist is published) and
``finalist`` (published L21b finalists). Only live, eligible, current work counts.
"""
from .models_stages import StageShortlistEntry, SubmissionStage, SubmissionStageEntry
from .stage_runtime import last_stage_id, published_shortlist

LIVE = ("submitted", "locked", "under_review", "judged")


def _entries(event, owner_id):
    return (SubmissionStageEntry.objects.filter(submission__event=event, submission__state__in=LIVE, triage="eligible",
                                                current_snapshot__isnull=False,
                                                current_snapshot__sealed_member_ids__contains=[owner_id])
            .order_by("-current_snapshot__submitted_at", "-current_snapshot_id"))


def submission_evidence(*, event, owner_id, mode, position=None):
    if mode == "any_stage":
        row = _entries(event, owner_id).first()
        return row.current_snapshot_id if row else _legacy(event, owner_id)
    if mode == "final_stage":
        row = _entries(event, owner_id).filter(stage_id=last_stage_id(event.pk)).first()
        return row.current_snapshot_id if row else None
    if mode == "stage":
        row = _entries(event, owner_id).filter(stage__position=position).first()
        return row.current_snapshot_id if row else None
    if mode == "shortlisted_at":
        stage = SubmissionStage.objects.filter(event=event, position=position).first()
        shortlist = published_shortlist(stage) if stage else None
        row = (StageShortlistEntry.objects.filter(shortlist=shortlist, submission__state__in=LIVE,
                                                  snapshot__sealed_member_ids__contains=[owner_id]).first()
               if shortlist else None)
        return row.snapshot_id if row else None
    if mode == "finalist":
        from apps.events.judging.finalists import published_finalists
        _, snapshots = published_finalists(event)
        return next((s.id for s in snapshots if owner_id in s.member_ids), None)
    return None  # "none": nothing is required, so nothing is evidence.


def _legacy(event, owner_id):
    """A snapshot with no stage record (none after migration 0070) keeps the pre-stage rule."""
    from django.db.models import F
    from .models_projects import SubmissionSnapshot
    row = SubmissionSnapshot.objects.filter(submission__event=event, submission__state__in=LIVE,
        submission__triage="eligible", submission__current_snapshot_id=F("pk"), stage_ref__isnull=True,
        sealed_member_ids__contains=[owner_id]).order_by("-submitted_at", "-pk").first()
    return row.pk if row else None
