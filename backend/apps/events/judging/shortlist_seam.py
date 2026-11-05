"""Hack-money seam: "was this project shortlisted?" answered from L21b's published finalists.

The money lane needs one question answered (G2: did a team fail to advance at a shortlist gate),
before the submission-stages lane ships its stage engine. These two functions are the ONLY place
that question is answered; at merge the coordinator rewires them to the stage engine's shortlist
results ("shortlisted at or after stage N"), and nothing else in the money code changes.

Today a "shortlist" is an L21b finalists announcement: a project advanced if one of its snapshots
is among the published finalists. `stage` is accepted now so callers already pass it; it is
ignored until the stage engine exists (L21b has one submission window).
"""


def _published_snapshot_ids(event, *, latest=False):
    from .models_finalists import FinalistAnnouncement, JudgingFinalist
    announcements = FinalistAnnouncement.objects.filter(event=event).order_by("-published_at", "-pk")
    advances = [row.advance_id for row in announcements[:1]] if latest else announcements.values("advance_id")
    return set(JudgingFinalist.objects.filter(advance_id__in=advances).values_list("snapshot_id", flat=True))


def was_shortlisted(event, project_id, *, stage=None):
    """True when the project advanced at a published shortlist (any, for now; `stage` later)."""
    from apps.events.models import SubmissionSnapshot
    finalists = _published_snapshot_ids(event)
    return SubmissionSnapshot.objects.filter(submission_id=project_id, pk__in=finalists).exists()


def not_shortlisted_project_ids(event, *, stage=None):
    """Submitted projects (with a current snapshot) that are not in the NEWEST published shortlist.

    A team dropped at a later gate is "not shortlisted" too; one dropped earlier was already closed
    when that gate published (closing is idempotent). Empty until the first shortlist publishes.
    Withdrawn and disqualified projects are left out: their own transitions closed their fees.
    """
    from apps.events.models import HackathonSubmission, SubmissionSnapshot
    finalists = _published_snapshot_ids(event, latest=True)
    if not finalists:
        return []
    advanced = set(SubmissionSnapshot.objects.filter(pk__in=finalists).values_list("submission_id", flat=True))
    rows = (HackathonSubmission.objects.filter(event_id=event.pk, current_snapshot__isnull=False)
            .exclude(state__in=("withdrawn", "disqualified")).exclude(pk__in=advanced).order_by("pk"))
    return list(rows.values_list("pk", flat=True))
