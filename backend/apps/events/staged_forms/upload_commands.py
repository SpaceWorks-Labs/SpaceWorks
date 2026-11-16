"""Reserve exact stage-file quota under the event mutex, before storage I/O."""
from datetime import timedelta
from uuid import uuid4
from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from apps.makerspaces.private_upload_transport import ObjectLocator, UploadRequest, bounded_not_after
from apps.payments.event_payouts.errors import require
from .transactions import command
from .definition_models import EventStageForm
from .response_models import StageFormAssignment, StageFormResponse
from .upload_models import StageFormAsset, StageFileCleanup
from .file_validation import MAX_BYTES, MIMES


def editable(row, *, actor, now=None):
    now = now or timezone.now()
    require(row.owner_member_id == actor.pk, "not_found", status=404)
    response = row.response
    require(not (row.registration_id and row.registration.status in ("cancelled", "rejected"))
        and not (row.application_id and row.application.state in ("rejected", "withdrawn", "expired", "declined")),
        "stage_response_closed")
    from .lifecycle import frozen_policy, reached_rank, ORDER
    from .trigger_service import resolve_participant
    policy = frozen_policy(row)
    rank = 3 if policy.stage == "accepted_rsvp" and policy.activation_point == "rsvp" else ORDER[policy.stage]
    reached = reached_rank(resolve_participant(event=row.event, owner_id=row.owner_member_id), now)
    require(not policy.lock_on_next_stage or reached <= max(rank, getattr(policy, "lock_suppressed_through_rank", -1)),
            "stage_response_closed")
    require(row.event.status != "cancelled" and row.state in ("scheduled", "open", "completed") and not row.imported_paused
        and row.opens_at <= now < row.effective_due_at and row.next_stage_locked_at is None
        and response.state in ("draft", "submitted"), "stage_response_closed")
    return response


def parents_locked(*, event, stage_form_id, actor):
    definition = EventStageForm.objects.select_for_update().get(pk=stage_form_id, event=event)
    row = StageFormAssignment.objects.select_for_update().get(stage_form=definition, owner_member=actor)
    StageFormResponse.objects.select_for_update().get(assignment=row)
    return row


def project(asset):
    return {"asset_id": asset.pk, "version": asset.version, "generation": asset.generation,
        "state": asset.state, "question_id": asset.question_id, "purpose": asset.purpose,
        "expected_bytes": asset.expected_bytes, "actual_bytes": asset.actual_bytes,
        "canonical_mime": asset.canonical_mime, "sha256": asset.sha256, "scan_status": asset.scan_status,
        "error_code": asset.error_code, "expires_at": asset.expires_at}


def create(*, event_id, stage_form_id, actor, data):
    from apps.events.models import Event
    from apps.tenant_migration.gate_runtime import boundary_tenant_write
    seed = Event.objects.get(pk=event_id)
    with boundary_tenant_write(seed.makerspace_id):
        return _create(event_id=event_id, stage_form_id=stage_form_id, actor=actor, data=data)


def _create(*, event_id, stage_form_id, actor, data):
    from .upload_jobs import scan_options
    with command(event_id=event_id, actor=actor, data=data, action=f"stage_file.create:{stage_form_id}",
                 owner=True, virtual=True) as ctx:
        if ctx.replay:
            reference = ctx.replay
        else:
            scanner_policy = scan_options()["backend"]
            row = parents_locked(event=ctx.event, stage_form_id=stage_form_id, actor=ctx.actor)
            ctx.cas(row)
            response = editable(row, actor=ctx.actor)
            require(data["expected_response_version"] == response.version, "stale_response_version")
            question = next((q for q in row.pinned_form_revision.schema["questions"] if q["id"] == data["question_id"]), None)
            require(question and question["type"] == "file" and question["file"]["purpose"] == "stage_form_file",
                    "stage_file_question_invalid", status=400)
            require(type(data["size_bytes"]) is int and 0 < data["size_bytes"] <= min(MAX_BYTES, question["file"]["max_bytes_each"])
                and data["mime"] in MIMES, "stage_file_invalid", status=400)
            reserved = StageFormAsset.objects.filter(event=ctx.event).exclude(state="deleted")
            require(reserved.filter(assignment=row, question_id=question["id"], form_revision=row.pinned_form_revision).count()
                < question["file"]["max_files"], "stage_file_limit")
            member_bytes = reserved.filter(owner_member=ctx.actor).aggregate(total=Sum("expected_bytes"))["total"] or 0
            event_bytes = reserved.aggregate(total=Sum("expected_bytes"))["total"] or 0
            require(member_bytes + data["size_bytes"] <= getattr(settings, "EVENT_STAGE_MEMBER_QUOTA_BYTES", 100 * 1024**2)
                and event_bytes + data["size_bytes"] <= getattr(settings, "EVENT_STAGE_EVENT_QUOTA_BYTES", 1024**3), "stage_file_quota")
            token = uuid4().hex
            prefix = f"event-stage/{ctx.event.makerspace_id}/{ctx.event.pk}/{token}"
            asset = StageFormAsset.objects.create(event=ctx.event, assignment=row, owner_member=ctx.actor,
                form_revision=row.pinned_form_revision, question_id=question["id"], expected_bytes=data["size_bytes"],
                declared_mime=data["mime"], original_filename=data["filename"], staging_key=prefix + "/staging",
                object_key=prefix + "/final", scanner_policy=scanner_policy,
                expires_at=timezone.now() + timedelta(hours=24),
                retention_days_snapshot=getattr(settings, "EVENT_STAGE_FILE_RETENTION_DAYS", 365))
            StageFileCleanup.objects.create(source_asset_id=asset.pk, tenant_id=ctx.event.makerspace_id,
                event_id_snapshot=ctx.event.pk, bucket=settings.AWS_STORAGE_BUCKET_NAME,
                staging_key=asset.staging_key, object_key=asset.object_key,
                not_before=asset.expires_at, next_attempt_at=asset.expires_at)
            ctx.audit("event.stage_file.initiated", asset, asset_id=asset.pk, new_state=asset.state)
            reference = ctx.finish(asset, asset_id=asset.pk)
    # A failed signer leaves a durable reservation; replay signs the same resource.
    from .storage import storage
    asset = StageFormAsset.objects.select_related("assignment__response").get(pk=reference["asset_id"])
    editable(asset.assignment, actor=actor)
    if asset.state != "initiated":
        return {**reference, **project(asset), "upload": None}
    until = bounded_not_after(now=timezone.now(), purpose_max_seconds=900,
        limits=(asset.assignment.effective_due_at, asset.created_at + timedelta(minutes=15)))
    descriptor = storage().initialize(UploadRequest(staging=ObjectLocator(bucket=settings.AWS_STORAGE_BUCKET_NAME,
        key=asset.staging_key), generation=asset.generation, mime=asset.declared_mime,
        size_bytes=asset.expected_bytes, not_after=until))
    return {**reference, **project(asset), "upload": {"method": descriptor.method, "url": descriptor.url,
        "fields": dict(descriptor.fields), "expires_at": descriptor.expires_at, "generation": descriptor.generation}}


def complete(*, event_id, stage_form_id, actor, asset_id, data):
    with command(event_id=event_id, actor=actor, data=data, action=f"stage_file.complete:{asset_id}",
                 owner=True, virtual=True) as ctx:
        if ctx.replay:
            return ctx.replay
        row = parents_locked(event=ctx.event, stage_form_id=stage_form_id, actor=ctx.actor)
        editable(row, actor=ctx.actor)
        asset = StageFormAsset.objects.select_for_update().get(pk=asset_id, assignment=row)
        ctx.cas(asset)
        require(asset.generation == data["generation"] and asset.state == "initiated", "invalid_stage_file_state")
        require(asset.expires_at is None or timezone.now() < asset.expires_at, "stage_file_expired", status=410)
        asset.state, asset.version = "uploaded", asset.version + 1
        asset.save(update_fields=["state", "version"])
        ctx.audit("event.stage_file.uploaded", asset, asset_id=asset.pk, old_state="initiated", new_state="uploaded")
        return ctx.finish(asset, asset_id=asset.pk)


def delete(*, event_id, stage_form_id, actor, asset_id, data):
    with command(event_id=event_id, actor=actor, data=data, action=f"stage_file.delete:{asset_id}",
                 owner=True, virtual=True) as ctx:
        if ctx.replay:
            return ctx.replay
        row = parents_locked(event=ctx.event, stage_form_id=stage_form_id, actor=ctx.actor)
        asset = StageFormAsset.objects.select_for_update().get(pk=asset_id, assignment=row)
        ctx.cas(asset)
        require(asset.response_id is None and asset.state not in ("attached", "deleted"), "stage_file_retained", status=423)
        from .upload_workflow import expire_locked
        expire_locked(asset, now=timezone.now(), actor=ctx.actor)
        return ctx.finish(asset, asset_id=asset.pk)
