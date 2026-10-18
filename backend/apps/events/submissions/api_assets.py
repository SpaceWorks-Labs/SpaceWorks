"""Upload orchestration: scoped DB reads are finished before storage calls."""
from math import ceil
from uuid import UUID, uuid4

from django.utils import timezone
from apps.audit.services import record

from .asset_workflow import initialize_asset, model_for, asset_command
from .asset_jobs import AssetJob
from .api_runtime import runtime
from .errors import SubmissionError
from .ports import boundary
from .workflow import canonical_digest
from .upload_deadlines import upload_deadline


def operation_key(request):
    value = request.headers.get("Idempotency-Key")
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise SubmissionError("idempotency_key_required") from exc


def owned_asset(*, actor, event_id, team_id, asset_id, participant, action="upload_read"):
    with boundary().locked(actor=actor, event_id=event_id, team_id=team_id, action=action):
        owner = {"member_id": actor.pk} if participant else {"team_id": team_id}
        asset = model_for(participant).objects.filter(pk=asset_id, event_id=event_id, **owner).first()
        if asset is None:
            raise SubmissionError("not_found", 404)
        return asset


def project_asset(asset):
    return {"asset_id": asset.pk, "event_id": asset.event_id, "version": asset.version,
        "generation": asset.generation, "state": asset.state, "bytes": asset.actual_bytes,
        "mime": asset.canonical_mime, "sha256": asset.sha256, "expires_at": asset.expires_at,
        "filename": asset.original_filename, "extension": asset.extension, "kind": asset.kind,
        "media_metadata": asset.media_metadata,
        "allowed_actions": (["download", "grant_consent", "delete"] if hasattr(asset, "member_id")
                            else ["download"]) if asset.state == "ready" else []}


def create_upload(*, actor, event_id, team_id, operation_id, data, participant):
    if participant:
        data = {**data, "group": "resume", "subtype": "pdf"}
    result = initialize_asset(actor=actor, event_id=event_id, team_id=team_id,
                              operation_id=operation_id, data=data, participant=participant)
    asset = owned_asset(actor=actor, event_id=event_id, team_id=team_id, asset_id=result["asset_id"], participant=participant)
    if asset.state == "reserved":
        descriptor = AssetJob(actor=actor, event_id=event_id, team_id=team_id, asset_id=asset.pk,
            participant=participant, storage=runtime().storage).run(scan_options=runtime().scan_options)
    elif asset.state == "uploading":
        descriptor = resume_upload(actor=actor, event_id=event_id, team_id=team_id,
            asset_id=asset.pk, participant=participant, expected_version=asset.version, generation=asset.generation,
            operation_id=str(uuid4()))
    else:
        return project_asset(asset)
    asset = owned_asset(actor=actor, event_id=event_id, team_id=team_id, asset_id=asset.pk, participant=participant)
    return {**project_asset(asset), "upload": descriptor}


def resume_upload(*, actor, event_id, team_id, asset_id, participant, expected_version, generation, operation_id, part_numbers=None):
    port = boundary()
    digest = canonical_digest({"refresh": asset_id, "participant": participant,
        "version": expected_version, "generation": generation, "part_numbers": part_numbers})
    with port.locked(actor=actor, event_id=event_id, team_id=team_id, action="upload") as ctx:
        owner = {"member_id": actor.pk} if participant else {"team_id": team_id}
        asset = model_for(participant).objects.select_for_update().filter(pk=asset_id, event_id=event_id, **owner).first()
        if asset is None:
            raise SubmissionError("not_found", 404)
        if asset.generation != generation or asset.version != expected_version:
            raise SubmissionError("upload_generation_changed", 409)
        if asset.state != "uploading":
            raise SubmissionError("invalid_transition", 409)
        replay = port.receipt(event_id=event_id, actor_id=actor.pk, operation_id=operation_id, digest=digest)
        asset.last_activity_at = timezone.now()
        asset.upload_not_after = upload_deadline(ctx, now=asset.last_activity_at, expires_at=asset.expires_at)
        asset.save(update_fields=["last_activity_at", "upload_not_after"])
        record(actor, "event.asset_upload_refreshed", makerspace=ctx.event.makerspace, target=asset)
        if replay is None:
            port.store_receipt(event_id=event_id, actor_id=actor.pk, operation_id=operation_id, digest=digest,
                result={"asset_id": asset.pk, "generation": asset.generation, "state": "uploading"})
    storage = runtime().storage
    if asset.multipart_upload_id:
        if part_numbers is not None:
            descriptor = {"parts": storage.sign_parts(asset, part_numbers)}
        else:
            descriptor = {"method": "MULTIPART", "part_size": asset.part_size,
                          "part_count": ceil(asset.declared_bytes / asset.part_size)}
    else:
        descriptor, _, _ = storage.initialize(asset, now=timezone.now())
    # Refuse stale authority after signer I/O too. Already issued staging-only
    # write grants have their documented fifteen-minute remaining lifetime.
    owned_asset(actor=actor, event_id=event_id, team_id=team_id, asset_id=asset.pk, participant=participant, action="upload")
    return descriptor
