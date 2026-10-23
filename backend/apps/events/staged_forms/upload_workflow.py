"""Stage file attachment is pinned to a submitted response's exact revision."""
from datetime import timedelta
from django.utils import timezone
from apps.payments.event_payouts.errors import require
from apps.audit.services import record


def create(**kwargs):
    from .upload_commands import create as run
    return run(**kwargs)


def complete(**kwargs):
    from .upload_commands import complete as run
    return run(**kwargs)


def delete(**kwargs):
    from .upload_commands import delete as run
    return run(**kwargs)


def attach_locked(asset, *, response):
    require(asset.assignment_id == response.assignment_id and asset.event_id == response.event_id
        and asset.owner_member_id == response.owner_member_id and asset.form_revision_id == response.form_revision_id
        and asset.purpose == "stage_form_file" and asset.state in ("ready", "attached")
        and asset.actual_bytes == asset.expected_bytes and asset.scan_status in ("clean", "skipped"), "stage_file_unavailable")
    if asset.state == "ready":
        asset.state, asset.attached_at, asset.response = "attached", timezone.now(), response
        asset.expires_at = response.event.ends_at + timedelta(days=asset.retention_days_snapshot)
        asset.version += 1
        asset.save(update_fields=["state", "attached_at", "response", "expires_at", "version"])
        from .upload_models import StageFileCleanup
        StageFileCleanup.objects.filter(source_asset_id=asset.pk).update(not_before=asset.expires_at, next_attempt_at=asset.expires_at)
        record(response.owner_member, "event.stage_file.attached", makerspace=response.event.makerspace, target=asset,
               meta={"asset_id": asset.pk, "response_id": response.pk, "new_state": "attached"})


def expire_locked(asset, *, now, actor=None):
    if asset.state in ("expired", "deleting", "deleted"):
        return
    from .upload_models import StageFileCleanup
    asset.state, asset.expired_at, asset.version = "expired", now, asset.version + 1
    asset.lease_token, asset.lease_until = None, None
    asset.save(update_fields=["state", "expired_at", "version", "lease_token", "lease_until"])
    StageFileCleanup.objects.filter(source_asset_id=asset.pk).update(not_before=now, next_attempt_at=now)
    record(actor, "event.stage_file.expired", makerspace=asset.event.makerspace, target=asset,
           meta={"asset_id": asset.pk, "new_state": "expired"})


def claim_validation_locked(asset, *, now):
    from uuid import uuid4
    require(asset.state in ("uploaded", "validating") and (asset.lease_until is None or asset.lease_until <= now), "stage_file_busy")
    asset.state, asset.lease_token, asset.lease_until = "validating", uuid4(), now + timedelta(minutes=5)
    asset.attempts, asset.version = asset.attempts + 1, asset.version + 1
    asset.save(update_fields=["state", "lease_token", "lease_until", "attempts", "version"])
    record(None, "event.stage_file.validating", makerspace=asset.event.makerspace, target=asset,
           meta={"asset_id": asset.pk, "new_state": "validating"})
    return asset.lease_token


def finish_validation_locked(asset, *, token, result=None, error_code=None):
    require(asset.state == "validating" and asset.lease_token == token and asset.lease_until > timezone.now(), "stage_file_lease_lost")
    if result:
        for key, value in result.items():
            setattr(asset, key, value)
        asset.state = "ready"
    elif error_code in ("scanner_unavailable", "scanner_incomplete", "storage_unavailable", "stage_decoder_unavailable"):
        asset.error_code = error_code
        asset.lease_until = timezone.now() + timedelta(minutes=min(60, 2 ** min(asset.attempts, 6)))
    else:
        asset.state, asset.error_code = "failed", error_code or "stage_file_invalid"
    if asset.state != "validating":
        asset.lease_token, asset.lease_until = None, None
    asset.version += 1
    asset.save(update_fields=["state", "error_code", "lease_token", "lease_until", "version", *(result or {})])
    record(None, "event.stage_file.validation_result", makerspace=asset.event.makerspace, target=asset,
           meta={"asset_id": asset.pk, "new_state": asset.state, "code": asset.error_code})


def deleted_locked(asset, *, now):
    require(asset.state in ("expired", "deleting", "deleted"), "invalid_stage_file_state")
    if asset.state == "deleted":
        return
    asset.state, asset.version = "deleted", asset.version + 1
    asset.deletion_receipt = {"deleted_at": now.isoformat(), "all_versions": True}
    asset.save(update_fields=["state", "version", "deletion_receipt"])
    record(None, "event.stage_file.deleted", makerspace=asset.event.makerspace, target=asset,
           meta={"asset_id": asset.pk, "new_state": "deleted"})
