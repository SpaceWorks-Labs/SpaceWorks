"""Application stages as event-funnel steps (AN-c1, #128 C-33). Counts only, never people.

Every submitted application stands in the first live stage (its entry is implicit until
the stage acts on it); a later stage counts the applications with an entry at that stage
or beyond, so a stage's count never exceeds the one before it. Draft stages are left out.
"""
from apps.makerspaces.platform import feature_enabled

from .admission_models import HackathonApplication, HackathonConfig
from .admission_stage_models import AdmissionStageEntry
from .admission_stages import STAGES, stages_for


def stage_counts(event):
    """-> [{"position", "name", "count"}] for the event's open and closed stages, or []."""
    if not feature_enabled(event.makerspace, STAGES):
        return []
    if not HackathonConfig.objects.filter(event=event, enabled=True).exists():
        return []
    stages = list(stages_for(event.pk).exclude(state="draft"))
    if not stages:
        return []
    submitted = HackathonApplication.objects.filter(event=event).exclude(submitted_at=None)
    total = submitted.count()
    furthest = {}
    for application_id, position in AdmissionStageEntry.objects.filter(
            event=event, application__in=submitted).values_list("application_id", "stage__position"):
        furthest[application_id] = max(furthest.get(application_id, 0), position)
    rows = []
    for index, stage in enumerate(stages):
        count = total if index == 0 else sum(1 for reached in furthest.values() if reached >= stage.position)
        rows.append({"position": stage.position, "name": stage.name, "count": count})
    return rows
