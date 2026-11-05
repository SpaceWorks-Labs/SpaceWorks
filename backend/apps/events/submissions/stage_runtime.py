"""Stage lookups shared by the submit path, the participant payload, judging and the gallery (#178-#180).

A stage window: stage 1 is open from the start (its ``opens_at`` is shown, never enforced, exactly as
the single window always was); a later stage opens at its ``opens_at``. Every stage closes at its
deadline plus grace, or at the team's extension when that is later (S2), unless its late policy
accepts flagged late work (S1). Once a shortlist has been applied to a stage, that stage takes no more
submissions: the selection is made from what was frozen.
"""
from datetime import timedelta

from .models_stages import (SubmissionStage, SubmissionStageEntry, StageExtension, StageShortlist,
                            StageShortlistEntry)

STAGE_FIELDS = ("name", "description", "opens_at", "deadline", "grace_minutes", "late_policy", "resubmission",
                "requires_previous", "content_mode", "required_link_kinds", "min_files", "max_files", "max_links",
                "accepted_families", "max_bytes_per_file", "video_hosts", "custom_fields", "shortlist_after",
                "shortlist_label")


def stages_for(event_id):
    return list(SubmissionStage.objects.filter(event_id=event_id).order_by("position"))


def ensure_stages(event, config):
    """Write paths only: an event without stages gets the "Single submission" stage from its window."""
    rows = stages_for(event.pk)
    if rows:
        return rows
    from .stage_presets import default_stage
    values = default_stage(config)
    return [SubmissionStage.objects.create(event=event, position=1, **{key: values[key] for key in STAGE_FIELDS})]


def last_stage_id(event_id):
    return (SubmissionStage.objects.filter(event_id=event_id).order_by("-position")
            .values_list("pk", flat=True).first())


def base_cutoff(stage, event):
    return (stage.deadline or event.ends_at) + timedelta(minutes=stage.grace_minutes)


def extension_for(stage, team_id):
    if team_id is None:
        return None
    return StageExtension.objects.filter(stage=stage, team_id=team_id).order_by("-until", "-pk").first()


def cutoff(stage, event, team_id):
    """(effective cutoff, the extension that set it or None)."""
    base, extension = base_cutoff(stage, event), extension_for(stage, team_id)
    if extension is not None and extension.until > base:
        return extension.until, extension
    return base, None


def shortlist_applied(stage):
    return StageShortlist.objects.filter(stage=stage).exists()


def window_open(stage, event, team_id, now):
    if stage.position > 1 and stage.opens_at and now < stage.opens_at:
        return False
    if shortlist_applied(stage):
        return False
    return now <= cutoff(stage, event, team_id)[0] or stage.late_policy == "accept_flagged"


def window_status(stage, event, team_id, now):
    if stage.opens_at and now < stage.opens_at:
        return "upcoming"
    if shortlist_applied(stage):
        return "closed"
    if now <= cutoff(stage, event, team_id)[0]:
        return "open"
    return "late" if stage.late_policy == "accept_flagged" else "closed"


def entry(project, stage):
    if project is None or project.pk is None:
        return None
    return SubmissionStageEntry.objects.filter(submission=project, stage=stage).first()


def published_shortlist(stage):
    return (StageShortlist.objects.filter(stage=stage, announcement__isnull=False)
            .order_by("-pk").first())


def shortlist_status(stage, project):
    """None (no gate), "pending", "shortlisted" or "not_shortlisted" for a project that entered the stage."""
    if not stage.shortlist_after:
        return None
    published = published_shortlist(stage)
    if published is None:
        return "pending"
    if project is not None and project.pk and StageShortlistEntry.objects.filter(shortlist=published, submission=project).exists():
        return "shortlisted"
    row = entry(project, stage)
    return "not_shortlisted" if row is not None and row.current_snapshot_id else None


def gate(stage, stages, project):
    """Why this project may not enter ``stage`` yet, or None. Admission (accepted teams) is checked by the roster."""
    previous = next((row for row in reversed(stages) if row.position < stage.position), None)
    if previous is None:
        return None
    if previous.shortlist_after:
        status = shortlist_status(previous, project)
        if status == "pending":
            return "shortlist_pending"
        return None if status == "shortlisted" else "not_shortlisted"
    if stage.requires_previous:
        row = entry(project, previous)
        if row is None or not row.current_snapshot_id:
            return "previous_stage_required"
    return None


def active_stage(stages, event, project, team_id, now):
    """The stage a team works on now: the latest open stage it may enter, else the latest open one
    (its submit gives the typed gate error), else the first upcoming one, else None (all closed)."""
    open_now = [stage for stage in stages if window_open(stage, event, team_id, now)]
    for stage in reversed(open_now):
        if gate(stage, stages, project) is None:
            return stage
    if open_now:
        return open_now[-1]
    return next((stage for stage in stages if stage.opens_at and now < stage.opens_at), None)


def current_snapshot_ids(project):
    """Every stage's current snapshot for a project (plus the project pointer for unstaged history)."""
    ids = set(SubmissionStageEntry.objects.filter(submission=project, current_snapshot__isnull=False)
              .values_list("current_snapshot_id", flat=True))
    if project.current_snapshot_id:
        ids.add(project.current_snapshot_id)
    return sorted(ids)


def furthest_entry(project):
    return (SubmissionStageEntry.objects.select_related("stage").filter(submission=project, current_snapshot__isnull=False)
            .order_by("-stage__position").first())


def stage_snapshot_ids(stage_id):
    """Per project, the current snapshot of one stage (what a round on that stage judges)."""
    return list(SubmissionStageEntry.objects.filter(stage_id=stage_id, current_snapshot__isnull=False)
                .order_by("submission_id").values_list("current_snapshot_id", flat=True))


def team_cutoff(context):
    """When a team's drafting ends: the last stage's cutoff, or the team's later extension of it."""
    stages = stages_for(context.event.pk)
    if not stages:
        return context.deadline + timedelta(seconds=context.grace_seconds)
    return max(cutoff(stage, context.event, context.team_id)[0] for stage in stages)
