"""Asset command writer. Reservations and durable work precede all storage I/O."""
from uuid import uuid4

from django.utils import timezone

from apps.audit.services import record
from apps.maker_formats.upload_policy import upload_spec
from apps.maker_formats.errors import FormatError
from .errors import SubmissionError
from .models_assets import SubmissionAsset, HackathonParticipantAsset, SubmissionAssetWork
from .models_projects import HackathonSubmission
from .ports import boundary
from .quota import reserve, usage_locked
from .workflow import canonical_digest
from .upload_deadlines import upload_deadline


def model_for(participant):
    return HackathonParticipantAsset if participant else SubmissionAsset


def _receipt(port, context, actor, operation_id, digest):
    return port.receipt(event_id=context.event.pk, actor_id=actor.pk, operation_id=operation_id, digest=digest)


def initialize_asset(*, actor, event_id, team_id, operation_id, data, participant=False, saved_source=None, request_digest=None):
    required = {"filename", "mime", "bytes", "group", "subtype"}
    if not isinstance(data, dict) or set(data) != required or type(data["bytes"]) is not int or data["bytes"] < 1:
        raise SubmissionError("invalid_upload")
    if participant and (team_id is not None or data["group"] != "resume" or data["subtype"] != "pdf"):
        raise SubmissionError("invalid_resume")
    try:
        spec, cap, canonical_group = upload_spec(data["filename"], group="fab-2d" if participant else data["group"],
                                                  subtype=data["subtype"], declared_mime=data["mime"])
        if participant:
            cap = min(cap, 10 * 1024 ** 2)
        elif canonical_group != data["group"]:
            data = {**data, "group": canonical_group}
    except FormatError as exc:
        raise SubmissionError(exc.code, exc.status) from exc
    if participant and spec.extension != "pdf":
        raise SubmissionError("unsupported_format")
    if data["bytes"] > cap:
        raise SubmissionError("file_too_large", 413)
    port = boundary()
    digest = request_digest or canonical_digest({"create": data, "team": team_id, "participant": participant, "saved_source": saved_source})
    with port.locked(actor=actor, event_id=event_id, team_id=team_id, action="upload") as ctx:
        replay = _receipt(port, ctx, actor, operation_id, digest)
        if replay is not None:
            return replay
        event_cap = ctx.file_caps.get(spec.extension, cap)
        if type(event_cap) is not int or event_cap < 1:
            raise SubmissionError("invalid_cap")
        cap = min(cap, event_cap)
        if data["bytes"] > cap:
            raise SubmissionError("file_too_large", 413)
        usage = usage_locked(ctx)
        cls = model_for(participant)
        if participant:
            rows = cls.objects.filter(event_id=event_id, member_id=actor.pk)
            owner = {"member_id": actor.pk}
            owner_key = f"member-{actor.pk}"
        else:
            project, _ = HackathonSubmission.objects.get_or_create(event_id=event_id, team_id=team_id)
            if project.state not in {"draft", "submitted"}:
                raise SubmissionError("submission_locked", 409)
            rows = cls.objects.filter(event_id=event_id, team_id=team_id)
            owner = {"team_id": team_id, "submission": project}
            owner_key = f"team-{team_id}"
        reserve(usage, rows, size=data["bytes"], group=data["group"],
                group_cap_bytes=ctx.group_caps.get(data["group"]))
        public_id = uuid4()
        root = f"hackathon/{ctx.event.makerspace_id}/{event_id}/{owner_key}/{public_id}.{spec.extension}"
        asset = cls.objects.create(event_id=event_id, public_id=public_id, **owner,
            kind=data["group"], purpose="resume" if participant else "project", original_filename=data["filename"],
            extension=spec.extension, subtype=data["subtype"], effective_cap=cap, declared_mime=data["mime"],
            declared_bytes=data["bytes"], reserved_bytes=data["bytes"], uploaded_by=actor,
            staging_key="staging/" + root, verification_key="verification/" + root,
            object_key=root, expires_at=usage.expires_at,
            upload_not_after=upload_deadline(ctx, now=timezone.now(), expires_at=usage.expires_at))
        work_fields = {"participant_asset" if participant else "asset": asset}
        if saved_source is not None:
            if not participant:
                raise SubmissionError("invalid_resume")
            asset.state = "copying"
            asset.save(update_fields=["state"])
            work_fields.update(saved_source)
        SubmissionAssetWork.objects.create(**work_fields)
        port.storage_pool_locked(context=ctx, asset=asset, operation="reserve", bytes=asset.declared_bytes)
        record(actor, "event.asset_reserved", makerspace=ctx.event.makerspace, target=asset,
               meta={"bytes": asset.declared_bytes, "generation": asset.generation})
        result = {"asset_id": asset.pk, "event_id": event_id, "version": asset.version,
                  "generation": asset.generation, "state": asset.state}
        port.store_receipt(event_id=event_id, actor_id=actor.pk, operation_id=operation_id, digest=digest, result=result)
        return result


def asset_command(*, actor, event_id, team_id, asset_id, participant, operation_id,
                  expected_version, generation, action):
    if action not in {"complete", "abort", "delete"}:
        raise SubmissionError("invalid_transition", 409)
    port, cls = boundary(), model_for(participant)
    digest = canonical_digest({"asset": asset_id, "participant": participant, "version": expected_version,
                               "generation": generation, "action": action})
    with port.locked(actor=actor, event_id=event_id, team_id=team_id, action="upload") as ctx:
        replay = _receipt(port, ctx, actor, operation_id, digest)
        if replay is not None:
            return replay
        owner = {"member_id": actor.pk} if participant else {"team_id": team_id}
        asset = cls.objects.select_for_update().filter(pk=asset_id, event_id=event_id, **owner).first()
        if asset is None:
            raise SubmissionError("not_found", 404)
        if asset.version != expected_version:
            raise SubmissionError("stale_version", 409)
        if asset.generation != generation:
            raise SubmissionError("upload_generation_changed", 409)
        if action == "complete":
            if asset.state not in {"uploading", "uploaded", "validating", "promoting", "ready"}:
                raise SubmissionError("invalid_transition", 409)
            if asset.state == "uploading":
                asset.state = "uploaded"
                record(actor, "event.asset_uploaded", makerspace=ctx.event.makerspace, target=asset)
                asset.state = "validating"
        else:
            if action == "abort" and asset.state == "ready":
                raise SubmissionError("invalid_transition", 409)
            if not participant and asset.snapshot_refs.exists():
                raise SubmissionError("asset_referenced", 409)
            # D read policy checks this live state, so old sponsor URLs cease now.
            asset.state = "deleting" if action == "delete" else "aborted"
            asset.expired_at = asset.expired_at or timezone.now()
            if participant:
                port.invalidate_participant_asset_locked(context=ctx, member_id=actor.pk,
                                                         asset_id=asset.pk, replacing=False)
        asset.version += 1
        asset.last_activity_at = timezone.now()
        asset.save()
        SubmissionAssetWork.objects.filter(pk=asset.work.pk).update(
            state="pending", next_attempt_at=timezone.now(), lease_token=None, lease_until=None)
        record(actor, f"event.asset_{action}", makerspace=ctx.event.makerspace, target=asset,
               meta={"version": asset.version, "generation": asset.generation})
        result = {"asset_id": asset.pk, "state": asset.state, "version": asset.version}
        if participant and action == "delete":
            result["sponsor_consents_revoked"] = True  # Effective read revoked by terminal asset state.
        port.store_receipt(event_id=event_id, actor_id=actor.pk, operation_id=operation_id, digest=digest, result=result)
        return result
