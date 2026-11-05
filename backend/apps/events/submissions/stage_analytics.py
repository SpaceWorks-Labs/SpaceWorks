"""#180 S16: submission stages in the event funnel: per stage, submitted, eligible, shortlisted, advanced.

Counts only (no names), for staff analytics. "Advanced" counts projects of this stage that also
submitted the next one. Merge note: lane r2-gap-crew's AN-c1 funnel can append these rows after its
application-stage rows.
"""
from .models_stages import StageShortlistEntry, SubmissionStageEntry
from .stage_runtime import published_shortlist, stages_for


def stage_funnel(event):
    stages = stages_for(event.pk)
    rows = []
    for index, stage in enumerate(stages):
        entries = SubmissionStageEntry.objects.filter(stage=stage, current_snapshot__isnull=False)
        projects = set(entries.values_list("submission_id", flat=True))
        published = published_shortlist(stage) if stage.shortlist_after else None
        following = stages[index + 1] if index + 1 < len(stages) else None
        advanced = (SubmissionStageEntry.objects.filter(stage=following, current_snapshot__isnull=False,
                                                        submission_id__in=projects).count() if following else None)
        rows.append({"position": stage.position, "name": stage.name, "submitted": len(projects),
                     "eligible": entries.filter(triage="eligible").count(),
                     "shortlisted": (StageShortlistEntry.objects.filter(shortlist=published).count()
                                     if published else None),
                     "advanced": advanced})
    return rows
