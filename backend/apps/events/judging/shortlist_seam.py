"""Hack-money seam: "was this project shortlisted?" (G2: did a team fail to advance at a gate).

These two functions are the ONLY place that question is answered. With `stage` (a submission stage
whose shortlist was published, #179) the answer comes from the stage engine: a project that entered
that stage advanced if it is in the stage's published shortlist. Without one, a "shortlist" is an
L21b finalists announcement: a project advanced if one of its snapshots is among the published
finalists.
"""


def _published_snapshot_ids(event, *, latest=False):
    from .models_finalists import FinalistAnnouncement, JudgingFinalist
    announcements = FinalistAnnouncement.objects.filter(event=event).order_by("-published_at", "-pk")
    advances = [row.advance_id for row in announcements[:1]] if latest else announcements.values("advance_id")
    return set(JudgingFinalist.objects.filter(advance_id__in=advances).values_list("snapshot_id", flat=True))


def was_shortlisted(event, project_id, *, stage=None):
    """True when the project advanced at the stage's published shortlist, else at any finalists list."""
    from apps.events.models import SubmissionSnapshot
    if stage is not None:
        from apps.events.submissions.models_stages import StageShortlistEntry
        from apps.events.submissions.stage_runtime import published_shortlist
        shortlist = published_shortlist(stage)
        return bool(shortlist) and StageShortlistEntry.objects.filter(shortlist=shortlist, submission_id=project_id).exists()
    finalists = _published_snapshot_ids(event)
    return SubmissionSnapshot.objects.filter(submission_id=project_id, pk__in=finalists).exists()


def not_shortlisted_project_ids(event, *, stage=None):
    """Submitted projects (with a current snapshot) that are not in the NEWEST published shortlist.

    A team dropped at a later gate is "not shortlisted" too; one dropped earlier was already closed
    when that gate published (closing is idempotent). Empty until the first shortlist publishes.
    Withdrawn and disqualified projects are left out: their own transitions closed their fees.
    """
    from apps.events.models import HackathonSubmission, SubmissionSnapshot
    if stage is not None:
        return _not_shortlisted_at(stage)
    finalists = _published_snapshot_ids(event, latest=True)
    if not finalists:
        return []
    advanced = set(SubmissionSnapshot.objects.filter(pk__in=finalists).values_list("submission_id", flat=True))
    rows = (HackathonSubmission.objects.filter(event_id=event.pk, current_snapshot__isnull=False)
            .exclude(state__in=("withdrawn", "disqualified")).exclude(pk__in=advanced).order_by("pk"))
    return list(rows.values_list("pk", flat=True))


def _not_shortlisted_at(stage):
    """Projects that entered the stage (a current snapshot there) and are not in its published shortlist."""
    from apps.events.submissions.models_stages import StageShortlistEntry, SubmissionStageEntry
    from apps.events.submissions.stage_runtime import published_shortlist
    shortlist = published_shortlist(stage)
    if shortlist is None:
        return []
    advanced = StageShortlistEntry.objects.filter(shortlist=shortlist).values("submission_id")
    rows = (SubmissionStageEntry.objects.filter(stage=stage, current_snapshot__isnull=False)
            .exclude(submission__state__in=("withdrawn", "disqualified")).exclude(submission_id__in=advanced)
            .order_by("submission_id"))
    return list(rows.values_list("submission_id", flat=True))
