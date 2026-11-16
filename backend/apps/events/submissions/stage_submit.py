"""The submit path's stage checks (#177-#180). Called by ``workflow`` under the event lock.

Drafts may be incomplete: a draft edit is refused only for content the active stage does not take at
all (files in a links-only stage, links in a files-only stage, a file family it does not accept).
Every other requirement is enforced when a stage is submitted, with a typed 400. A stage's rules are
frozen into its snapshot, so editing a stage later never changes what was submitted.
"""
from django.utils import timezone

from .errors import SubmissionError
from .models_stages import SnapshotStage, SubmissionStageEntry
from . import stage_runtime as runtime
from .stage_rules import field_answer


def _stages(context):
    from apps.events.hackathons.admission_models import HackathonConfig
    config = HackathonConfig.objects.filter(event=context.event).first()
    return runtime.ensure_stages(context.event, config, context=context)


def check_draft(project, context, patch, *, now=None):
    """Refuse adding content the team's active stage does not take. Returns that stage (or None)."""
    stages = _stages(context)
    stage = runtime.active_stage(stages, context.event, project, context.team_id, now or timezone.now())
    if stage is None:
        return None
    if patch.get("links") and stage.content_mode == "files_only":
        raise SubmissionError("submission_links_disabled", 400, stage=stage.name)
    if patch.get("asset_ids") and stage.content_mode == "links_only":
        raise SubmissionError("submission_files_disabled", 400, stage=stage.name)
    return stage


def check_upload(project, context, group, size):
    """A team upload into the active stage: refused when it takes no files, or not this family or size."""
    stages = _stages(context)
    stage = runtime.active_stage(stages, context.event, project, context.team_id, timezone.now())
    if stage is None:
        return
    if stage.content_mode == "links_only":
        raise SubmissionError("submission_files_disabled", 400, stage=stage.name)
    if stage.accepted_families and group not in stage.accepted_families:
        raise SubmissionError("submission_file_type_not_accepted", 400, families=list(stage.accepted_families))
    if stage.max_bytes_per_file and size > stage.max_bytes_per_file:
        raise SubmissionError("submission_file_too_large", 413, limit=str(stage.max_bytes_per_file))


def resolve(project, context, data, now, action):
    """The stage a submit or amendment freezes, with (late, extension). Amendments are staff
    corrections: they skip the window and the gates, as amendments always have."""
    stages = _stages(context)
    by_id = {stage.pk: stage for stage in stages}
    requested = data.get("stage_id")
    if requested is not None and (type(requested) is not int or requested not in by_id):
        raise SubmissionError("not_found", 404)
    if action == "amend":
        stage = by_id.get(requested) if requested else _stage_of_current(project, stages)
        if runtime.entry(project, stage) is None:
            raise SubmissionError("invalid_transition", 409)
        return stage, False, None
    stage = by_id[requested] if requested else runtime.active_stage(stages, context.event, project, context.team_id, now)
    if stage is None:
        raise SubmissionError("submission_deadline", 409)
    if stage.position > 1 and stage.opens_at and now < stage.opens_at:
        raise SubmissionError("stage_not_open", 409, stage=stage.name)
    if runtime.shortlist_applied(stage):
        raise SubmissionError("stage_closed", 409, stage=stage.name)
    reason = runtime.gate(stage, stages, project)
    if reason:
        raise SubmissionError(reason, 403 if reason == "not_shortlisted" else 409, stage=stage.name)
    effective, extension = runtime.cutoff(stage, context.event, context.team_id)
    if now > effective and stage.late_policy != "accept_flagged":
        raise SubmissionError("submission_deadline", 409)
    current = runtime.entry(project, stage)
    if stage.resubmission == "once" and current is not None and current.current_snapshot_id:
        raise SubmissionError("stage_already_submitted", 409, stage=stage.name)
    late = now > runtime.base_cutoff(stage, context.event)
    return stage, late, extension if late else None


def _stage_of_current(project, stages):
    ref = SnapshotStage.objects.filter(snapshot_id=project.current_snapshot_id).first()
    return next((s for s in stages if ref and s.pk == ref.stage_id), stages[-1])


def check_content(stage, project, assets, links):
    """Enforce one stage's requirements on what is about to be frozen."""
    mode = stage.content_mode
    if mode == "files_only" and links:
        raise SubmissionError("submission_links_disabled", 400, stage=stage.name)
    if mode == "links_only" and assets:
        raise SubmissionError("submission_files_disabled", 400, stage=stage.name)
    if mode != "presentation" and not assets and not links:
        raise SubmissionError("submission_content_required")
    if stage.accepted_families and any(a.kind not in stage.accepted_families for a in assets):
        raise SubmissionError("submission_file_type_not_accepted", 400, families=list(stage.accepted_families))
    if stage.max_bytes_per_file and any((a.actual_bytes or 0) > stage.max_bytes_per_file for a in assets):
        raise SubmissionError("submission_file_too_large", 413, limit=str(stage.max_bytes_per_file))
    if len(assets) < stage.min_files:
        raise SubmissionError("submission_files_required", 400, limit=str(stage.min_files))
    if stage.max_files is not None and len(assets) > stage.max_files:
        raise SubmissionError("submission_too_many_files", 400, limit=str(stage.max_files))
    if stage.max_links is not None and len(links) > stage.max_links:
        raise SubmissionError("submission_too_many_links", 400, limit=str(stage.max_links))
    missing = sorted(set(stage.required_link_kinds) - {link.kind for link in links})
    if missing:
        raise SubmissionError("submission_link_required", 400, kinds=missing)
    if stage.video_hosts and any(link.kind == "video" and link.provider not in stage.video_hosts for link in links):
        raise SubmissionError("submission_video_host_not_allowed", 400, hosts=list(stage.video_hosts))
    return _answers(stage, project)


def _answers(stage, project):
    supplied = (project.form_answers or {}).get(f"stage:{stage.pk}", {})
    if not isinstance(supplied, dict):
        raise SubmissionError("invalid_answers")
    answers, missing = {}, []
    for field in stage.custom_fields:
        value = field_answer(field, supplied.get(field["key"]))
        if value is None and field.get("required"):
            missing.append(field["key"])
        elif value is not None:
            answers[field["key"]] = value
    if missing:
        raise SubmissionError("submission_field_required", 400, fields=missing)
    return answers


def frozen_stage(stage, answers):
    """The stage definition and answers frozen into a snapshot document."""
    return {"id": stage.pk, "position": stage.position, "name": stage.name, "version": stage.version,
            "rules": {key: getattr(stage, key) for key in ("content_mode", "required_link_kinds", "min_files",
                      "max_files", "max_links", "accepted_families", "max_bytes_per_file", "video_hosts", "resubmission")},
            "custom_fields": stage.custom_fields, "answers": answers}


def record(project, stage, snapshot, extension):
    """Point the stage entry at the new snapshot and return the snapshot it replaces (or None)."""
    SnapshotStage.objects.create(snapshot=snapshot, stage=stage, extension=extension)
    row, created = SubmissionStageEntry.objects.select_for_update().get_or_create(submission=project, stage=stage)
    previous = row.current_snapshot_id
    row.current_snapshot, row.submitted_at, row.triage = snapshot, snapshot.submitted_at, "pending"
    row.version = row.version if created else row.version + 1
    row.save()
    furthest = runtime.furthest_entry(project)
    project.current_snapshot_id = furthest.current_snapshot_id
    return previous, furthest.stage_id == stage.pk

