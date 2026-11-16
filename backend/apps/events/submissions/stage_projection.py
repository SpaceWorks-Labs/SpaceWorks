"""Read shapes for submission stages: the staff editor and the participant's per-stage checklist."""
from zoneinfo import ZoneInfo

from django.utils import timezone

from .links import KINDS
from .models_stages import StageExtension, SubmissionStageEntry
from .stage_presets import PRESETS
from .stage_rules import FAMILIES, FIELD_TYPES, FIELD_VISIBILITY, VIDEO_HOSTS, stage_cap
from . import stage_runtime as runtime
from .stage_feedback import released_feedback

RULE_FIELDS = ("content_mode", "required_link_kinds", "min_files", "max_files", "max_links", "accepted_families",
               "max_bytes_per_file", "video_hosts", "resubmission", "late_policy")


def definition(stage):
    return {"id": stage.pk, "position": stage.position, "version": stage.version,
            **{key: getattr(stage, key) for key in runtime.STAGE_FIELDS}}


def editor_options(event):
    from .stage_rules import ANSWER_LIMITS
    return {"timezone": event.timezone_name, "event_ends_at": event.ends_at, "presets": list(PRESETS),
            "families": list(FAMILIES), "link_kinds": sorted(KINDS), "video_hosts": list(VIDEO_HOSTS),
            "field_types": list(FIELD_TYPES), "field_visibility": list(FIELD_VISIBILITY), "max_stages": stage_cap(event.makerspace),
            "answer_limits": ANSWER_LIMITS, "admission_enabled": _admission_on(event)}


def _admission_on(event):
    from apps.events.hackathons.admission_feature import admission_enabled
    return bool(admission_enabled(event.makerspace))


def deadline_warning(event, stage):
    """S13: a deadline at exactly 00:00 or 12:00 event time is ambiguous to many readers."""
    if not stage.deadline:
        return None
    local = stage.deadline.astimezone(ZoneInfo(event.timezone_name))
    return "ambiguous_deadline_time" if local.minute == 0 and local.hour in (0, 12) else None


def staff_stage(event, stage):
    from .stage_triage import pending_count
    entries = SubmissionStageEntry.objects.filter(stage=stage, current_snapshot__isnull=False)
    published = runtime.published_shortlist(stage)
    applied = stage.shortlists.order_by("-pk").first()
    extensions = [{"id": row.pk, "team_id": row.team_id, "team_name": row.team.name, "until": row.until,
                   "reason": row.reason, "created_at": row.created_at}
                  for row in StageExtension.objects.filter(stage=stage).select_related("team")
                  .order_by("-created_at", "-pk")[:200]]
    warning = deadline_warning(event, stage)
    return {**definition(stage), "submissions": entries.count(), "pending_triage": pending_count(stage),
            "shortlist": {"applied_id": applied.pk if applied else None, "published": published is not None,
                          "count": applied.entries.count() if applied else 0},
            "extensions": extensions, "warnings": [warning] if warning else []}


def participant_stages(event, project, team_id, now=None):
    """The team's view of every stage: window, rules, its own progress and its shortlist status."""
    now = now or timezone.now()
    stages = runtime.stages_for(event.pk)
    if not stages:
        return [], None
    active = runtime.active_stage(stages, event, project, team_id, now)
    rows = []
    for stage in stages:
        entry = runtime.entry(project, stage)
        effective, extension = runtime.cutoff(stage, event, team_id)
        rows.append({
            "id": stage.pk, "position": stage.position, "name": stage.name, "description": stage.description,
            "opens_at": stage.opens_at, "deadline": stage.deadline or event.ends_at, "grace_minutes": stage.grace_minutes,
            "effective_deadline": effective, "extended": extension is not None,
            "status": runtime.window_status(stage, event, team_id, now),
            "rules": {key: getattr(stage, key) for key in RULE_FIELDS},
            "custom_fields": [{key: field.get(key) for key in ("key", "label", "type", "required", "choices", "help")}
                              for field in stage.custom_fields],
            "requires_previous": stage.requires_previous, "shortlist_after": stage.shortlist_after,
            "shortlist_label": stage.shortlist_label,
            "submitted": bool(entry and entry.current_snapshot_id),
            "snapshot_id": entry.current_snapshot_id if entry else None,
            "submitted_at": entry.submitted_at if entry else None,
            "blocked": runtime.gate(stage, stages, project),
            "shortlist_status": runtime.shortlist_status(stage, project),
            "feedback": released_feedback(stage, project),
        })
    return rows, active.pk if active else None
