"""Byte cleanup never needs an active uploader, feature or tenant workflow grant."""
from datetime import timedelta
from uuid import uuid4

from django.utils import timezone

from apps.audit.services import record
from apps.events.tasks_retention import _retention_event
from .asset_workflow import model_for
from .errors import SubmissionError
from .models_assets import SubmissionAssetWork, EventAssetObligation
from .ports import SubmissionContext
from .quota import usage_locked, release_after_cleanup
from .storage_cleanup import delete_keys

TERMINAL = {"aborted", "rejected", "quarantined", "expiring", "expired", "deleting"}


def cleanup_asset(*, asset_id, participant, storage):
    model = model_for(participant)
    original = model.objects.get(pk=asset_id)
    token = uuid4()
    with _retention_event(original.event_id) as event:
        asset = model.objects.select_for_update().get(pk=asset_id, event=event)
        work, _ = SubmissionAssetWork.objects.get_or_create(**{
            "participant_asset" if participant else "asset": asset})
        work = SubmissionAssetWork.objects.select_for_update().get(pk=work.pk)
        now = timezone.now()
        if work.lease_until and work.lease_until > now:
            return False
        if asset.state not in TERMINAL | {"ready"}:
            return False
        temporary = asset.state == "ready"
        not_after = asset.upload_not_after or asset.last_activity_at + timedelta(minutes=15)
        if now < not_after + timedelta(minutes=1):
            work.next_attempt_at = not_after + timedelta(minutes=1)
            work.save(update_fields=["next_attempt_at"])
            return False
        work.lease_token, work.lease_until, work.state = token, now + timedelta(minutes=5), "processing"
        work.attempts += 1
        work.save()
    code = ""
    try:
        keys = [asset.staging_key, asset.verification_key]
        if not temporary:
            keys.append(asset.object_key)
        delete_keys(storage, keys)
    except SubmissionError:
        code = "storage_cleanup_pending"
    with _retention_event(original.event_id) as event:
        # Owning event serializes all usage, asset and receipt changes.
        ctx = SubmissionContext(event=event, team_id=getattr(asset, "team_id", None),
            member_ids=(), leader_id=None, deadline=event.ends_at)
        usage = usage_locked(ctx)
        asset = model.objects.select_for_update().get(pk=asset_id, event=event)
        work = SubmissionAssetWork.objects.select_for_update().get(pk=work.pk)
        if work.lease_token != token or work.lease_until <= timezone.now():
            raise SubmissionError("lease_lost", 409)
        # Expiry may have won during temporary-only I/O; never claim its final
        # bytes removed on a pass that deleted temporary copies only.
        if not code:
            amount = asset.reserved_bytes + (0 if temporary else asset.charged_bytes)
            obligation = EventAssetObligation.objects.get(asset_uuid=asset.public_id)
            first = not obligation.temporary_released if temporary else asset.deleted_at is None
            release_after_cleanup(usage, asset, final_deleted=not temporary)
            from apps.makerspaces.storage_events_programme import EventAssetStoragePool
            EventAssetStoragePool().apply_locked(event=event, asset_uuid=asset.public_id,
                operation="release_temporary" if temporary else "release_all", bytes=amount)
            if not temporary:
                asset.deleted_at = asset.deleted_at or timezone.now()
                asset.expired_size_bytes = asset.actual_bytes
                if asset.state == "expiring":
                    asset.state = "expired"
            if first or amount or asset.failure_code:
                record(None, "event.asset_bytes_deleted", makerspace=event.makerspace, target=asset,
                       meta={"temporary_only": temporary})
        elif asset.failure_code != code:
            record(None, "event.asset_attempt_failed", makerspace=event.makerspace, target=asset,
                   meta={"code": code, "retryable": True})
        asset.failure_code = code
        asset.save()
        work.state, work.last_code = "pending" if code or temporary and asset.state != "ready" else "verify_absence", code
        work.next_attempt_at = timezone.now() + timedelta(minutes=5 if code or work.state == "pending" else 360)
        work.lease_token, work.lease_until = None, None
        work.save()
    return not code
