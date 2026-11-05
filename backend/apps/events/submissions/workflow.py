"""Single writer for project draft/snapshot transitions. No network under locks."""
import hashlib
import json
from uuid import UUID

from django.utils import timezone

from apps.audit.services import record
from .errors import SubmissionError
from .models_projects import (HackathonSubmission, SubmissionSnapshot, SnapshotAsset,
                              SnapshotLink, SnapshotTrack, SnapshotPrize)
from .ports import boundary
from .stage_runtime import last_stage_id
from .project_validation import PROJECT_FIELDS, validate_project_patch
from .pii import prepare_documents


def canonical_digest(data):
    try:
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    except (ValueError, TypeError, RecursionError) as exc:
        raise SubmissionError("invalid_command") from exc
    if len(encoded) > 256 * 1024:
        raise SubmissionError("command_too_large", 413)
    return hashlib.sha256(encoded).hexdigest()


def command(*, actor, event_id, team_id, operation_id, expected_version, action, data=None, now=None):
    if action not in {"save", "submit", "amend", "withdraw", "lock"}:
        raise SubmissionError("invalid_transition", 409)
    try:
        UUID(str(operation_id))
    except (ValueError, TypeError) as exc:
        raise SubmissionError("invalid_operation_id") from exc
    if type(expected_version) is not int or expected_version < 0:
        raise SubmissionError("invalid_version")
    data, now, port = data or {}, now or timezone.now(), boundary()
    digest = canonical_digest({"team": team_id, "action": action, "version": expected_version, "data": data})
    with prepare_documents(event_id), port.locked(actor=actor, event_id=event_id, team_id=team_id, action=action) as context:
        replay = port.receipt(event_id=event_id, actor_id=actor.pk, operation_id=str(operation_id), digest=digest)
        if replay is not None:
            return replay
        project, created = HackathonSubmission.objects.get_or_create(event_id=event_id, team_id=team_id)
        project = HackathonSubmission.objects.select_for_update().get(pk=project.pk, event_id=event_id, team_id=team_id)
        if project.version != expected_version and not (expected_version == 0 and created):
            raise SubmissionError("stale_version", 409)
        from .stage_runtime import team_cutoff
        cutoff = team_cutoff(context)  # The last stage's cutoff, or this team's later extension (S2).
        if action == "save":
            if project.state not in {"draft", "submitted"} or now > cutoff:
                raise SubmissionError("submission_locked", 409)
            patch = dict(data)
            from .stage_submit import check_draft
            check_draft(project, context, patch, now=now)
            if "links" in patch:
                from .link_workflow import replace_links_locked
                replace_links_locked(project, patch.pop("links"))
            for key, value in validate_project_patch(patch).items():
                setattr(project, key, value)
            _canonical_project(project, context, port, final=False)
        elif action in {"submit", "amend"}:
            if action == "amend" and (not project.current_snapshot_id or project.state in {"withdrawn", "disqualified"}):
                raise SubmissionError("invalid_transition", 409)
            if action == "submit" and actor.pk != context.leader_id:
                raise SubmissionError("leader_required", 403)
            if action == "submit" and project.state not in {"draft", "submitted"}:
                raise SubmissionError("invalid_transition", 409)
            from .stage_submit import resolve
            stage, late, extension = resolve(project, context, data, now, action)  # #178: the stage it freezes.
            if action == "submit":  # L21b: a draft until the entry fee and a paid team's charge are settled.
                from .entry_fees import require_submit_paid
                require_submit_paid(project, context.event, project.team, stage=stage)
            reason = data.get("reason", "")
            if action == "amend" and (not isinstance(reason, str) or not reason.strip() or len(reason) > 1000):
                raise SubmissionError("amendment_reason_required")
            if action == "amend":
                amendment = dict(data.get("patch", {}))
                from .stage_submit import check_draft
                check_draft(project, context, amendment, now=now)
                if "links" in amendment:
                    from .link_workflow import replace_links_locked
                    replace_links_locked(project, amendment.pop("links"))
                for key, value in validate_project_patch(amendment).items():
                    setattr(project, key, value)
            furthest, stage_snapshot = _snapshot(actor, project, context, port, now, late, reason, stage=stage, extension=extension)
            if action == "submit":
                project.state = "submitted"
            elif furthest and stage.pk == last_stage_id(context.event.pk):
                project.state = "locked"  # Amending the final stage locks the project, as before.
            if furthest:  # The project's triage mirrors its furthest stage's (S5).
                project.triage, project.triage_reason = "pending", ""
            project.submitted_at = now
        elif action == "lock":
            if now <= cutoff or not project.current_snapshot_id or project.state != "submitted":
                raise SubmissionError("invalid_transition", 409)
            project.state, project.locked_at = "locked", now
        else:
            if project.state == "withdrawn":
                result = _projection(project)
                port.store_receipt(event_id=event_id, actor_id=actor.pk, operation_id=str(operation_id), digest=digest, result=result)
                return result
            from .stage_runtime import current_snapshot_ids
            for snapshot_id in current_snapshot_ids(project):  # Every stage's current work leaves judging.
                port.invalidate_snapshot(context=context, snapshot_id=snapshot_id)
            from .entry_fees import on_withdrawn  # hack-money G2: void or (switch on) refund case
            on_withdrawn(event=context.event, project=project, actor=actor)
            project.state = "withdrawn"
        project.version += 1
        project.save()
        meta = {"version": project.version, "snapshot_id": project.current_snapshot_id}
        if action in {"submit", "amend"}:
            meta.update(stage_id=stage.pk, stage_snapshot_id=stage_snapshot, late=late)
        record(actor, f"event.submission_{action}", makerspace=context.event.makerspace, target=project, meta=meta)
        from .notifications import enqueue_locked
        enqueue_locked(project=project, action=action)
        result = _projection(project)
        port.store_receipt(event_id=event_id, actor_id=actor.pk, operation_id=str(operation_id), digest=digest, result=result)
        return result


def _snapshot(actor, project, context, port, now, late, reason, *, stage, extension):
    document = _canonical_project(project, context, port, final=True)
    validate_project_patch(document)
    if not set(project.public_asset_ids) <= set(project.asset_ids):
        raise SubmissionError("invalid_asset_consent")
    if not project.title.strip() or not project.ai_declaration or not project.reuse_declaration:
        raise SubmissionError("project_incomplete")
    assets = list(project.assets.select_for_update().filter(pk__in=project.asset_ids).order_by("pk"))
    if len(assets) != len(project.asset_ids) or any(a.state != "ready" or a.scan_status not in {"clean", "skipped"} or
           a.team_id != context.team_id or a.event_id != context.event.pk or
           a.expired_at or a.expires_at and now >= a.expires_at for a in assets):
        raise SubmissionError("asset_not_ready", 409)
    links = list(project.links.filter(version=project.links_version).order_by("pk"))
    from .stage_submit import check_content, frozen_stage, record
    answers = check_content(stage, project, assets, links)
    document["asset_ids"] = [a.pk for a in assets]
    document["assets"] = [{"id": a.pk, "sha256": a.sha256, "bytes": a.actual_bytes} for a in assets]
    document["links"] = [{"id": l.pk, "kind": l.kind, "url": l.url, "provider": l.provider,
                           "public_requested": l.public_requested} for l in links]
    document["stage"] = frozen_stage(stage, answers)
    # A locks roster in the same transaction; superseded D scores cannot survive.
    port.lock_roster(context=context)
    from django.db.models import Max
    sequence = (project.snapshots.aggregate(value=Max("sequence"))["value"] or 0) + 1
    snapshot = SubmissionSnapshot.objects.create(
        submission=project, sequence=sequence, submitted_by=actor,
        submitted_at=now, sealed_member_ids=sorted(context.member_ids), project=document,
        content_sha256=canonical_digest({"project": document, "members": sorted(context.member_ids)}),
        late=late, amendment_of=_stage_previous(project, stage) if reason else None, amendment_reason=reason,
    )
    for asset in assets:
        SnapshotAsset.objects.create(snapshot=snapshot, asset=asset, public_requested=asset.pk in project.public_asset_ids)
    for link in links:
        SnapshotLink.objects.create(snapshot=snapshot, link=link, kind=link.kind, url=link.url,
                                    provider=link.provider, public_requested=link.public_requested)
    for track_id in project.track_ids:
        SnapshotTrack.objects.create(snapshot=snapshot, track_id=track_id)
    for prize_id in project.prize_ids:
        SnapshotPrize.objects.create(snapshot=snapshot, prize_id=prize_id)
    # Only this stage's previous snapshot is superseded; other stages keep their judging (#178).
    previous, furthest = record(project, stage, snapshot, extension)
    if previous:
        port.invalidate_snapshot(context=context, snapshot_id=previous)
    return furthest, snapshot.pk


def _stage_previous(project, stage):
    from .stage_runtime import entry
    row = entry(project, stage)
    return row.current_snapshot if row is not None else None


def _canonical_project(project, context, port, *, final):
    current = {key: getattr(project, key) for key in sorted(PROJECT_FIELDS)}
    normalized = port.validate_project(context=context, project=current, final=final)
    if not isinstance(normalized, dict) or set(normalized) != PROJECT_FIELDS:
        raise SubmissionError("project_form_adapter_unavailable", 503)
    validate_project_patch({key: value for key, value in normalized.items()
                            if final or key not in {"ai_declaration", "reuse_declaration"} or value})
    for key, value in normalized.items():
        setattr(project, key, value)
    return normalized


def _projection(project):
    return {"id": project.pk, "event_id": project.event_id, "version": project.version,
            "state": project.state, "snapshot_id": project.current_snapshot_id, "allowed_actions": []}


def transition_review_locked(*, actor, context, submission_id, snapshot_id, expected_version, state, reason=""):
    """D calls after its own live round/assignment authority checks, under G's
    existing ordered locks. This remains the only writer of submission status.
    No HTTP request can deserialize context or call this transition directly.
    """
    from django.db import transaction
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Submission transitions require the event transaction")
    project = HackathonSubmission.objects.select_for_update().filter(
        pk=submission_id, event_id=context.event.pk, current_snapshot_id=snapshot_id).first()
    if project is None:
        raise SubmissionError("not_found", 404)
    if project.version != expected_version:
        raise SubmissionError("stale_version", 409)
    allowed = {"locked": {"under_review", "disqualified"},
               "under_review": {"judged", "disqualified"}, "judged": {"disqualified"}}
    if state not in allowed.get(project.state, set()):
        raise SubmissionError("invalid_transition", 409)
    if state == "disqualified":
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 1000:
            raise SubmissionError("disqualification_reason_required")
        boundary().invalidate_snapshot(context=context, snapshot_id=snapshot_id)
        project.triage, project.triage_reason = "ineligible", reason
        from .entry_fees import on_disqualified
        on_disqualified(event=context.event, project=project, actor=actor)
    project.state, project.version = state, project.version + 1
    project.save(update_fields=["state", "version", "triage", "triage_reason"])
    record(actor, "event.submission_review_transition", makerspace=context.event.makerspace, target=project,
           meta={"state": state, "snapshot_id": snapshot_id, "version": project.version})
    return _projection(project)
