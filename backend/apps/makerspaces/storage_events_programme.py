"""Event asset pool/provider accounting without the ordinary base entitlement.

The event usage row is locked by the workflow before this receipt. The owning
makerspace lock is acquired by the common boundary before either child row.
"""
from django.db import connection
from django.db.models import F

from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.models_assets import (
    EventAssetObligation, SubmissionAsset, HackathonParticipantAsset,
)
from apps.makerspaces import limits
from apps.makerspaces.models import Makerspace


def settle(obligation, operation, size):
    """Return the provider delta. Replays either agree or refuse the transaction."""
    if type(size) is not int or size < 0:
        raise SubmissionError("asset_accounting_conflict", 409)
    if operation == "reserve":
        if obligation.initial_bytes:
            if obligation.initial_bytes != size:
                raise SubmissionError("asset_accounting_conflict", 409)
            return 0
        obligation.initial_bytes = obligation.reserved_bytes = size
        return size
    if operation == "reserve_canonical":
        if obligation.canonical_extra_bytes:
            if obligation.canonical_extra_bytes != size:
                raise SubmissionError("asset_accounting_conflict", 409)
            return 0
        if obligation.fully_released or obligation.charged_bytes:
            raise SubmissionError("asset_accounting_conflict", 409)
        obligation.canonical_extra_bytes = size
        obligation.reserved_bytes += size
        return size
    if operation == "charge":
        if obligation.charged_bytes == size and not obligation.fully_released:
            return 0
        if obligation.charged_bytes or obligation.fully_released or not 0 < size <= obligation.reserved_bytes:
            raise SubmissionError("asset_accounting_conflict", 409)
        obligation.reserved_bytes -= size
        obligation.charged_bytes = size
        return 0
    if operation not in {"release_temporary", "release_all"}:
        raise SubmissionError("asset_accounting_conflict", 409)
    if obligation.fully_released or operation == "release_temporary" and obligation.temporary_released:
        return 0
    expected = obligation.reserved_bytes + (obligation.charged_bytes if operation == "release_all" else 0)
    if size != expected:
        raise SubmissionError("asset_accounting_conflict", 409)
    obligation.reserved_bytes, obligation.temporary_released = 0, True
    if operation == "release_all":
        obligation.charged_bytes, obligation.fully_released = 0, True
    return -size


def provider_delta(obligation, delta):
    if not obligation.managed or not delta:
        return
    # No ordinary base quota check; B has already serialized the event's pool.
    rows = Makerspace.objects.filter(pk=obligation.makerspace_id_snapshot)
    if delta < 0:
        # A missing tenant is expected after purge; a surviving tenant must agree.
        eligible = rows.filter(storage_bytes_used__gte=-delta)
        if rows.exists() and not eligible.update(storage_bytes_used=F("storage_bytes_used") + delta):
            raise SubmissionError("asset_accounting_conflict", 409)
    else:
        rows.update(storage_bytes_used=F("storage_bytes_used") + delta)


class EventAssetStoragePool:
    def apply_locked(self, *, event, asset_uuid, operation, bytes):
        if not connection.in_atomic_block:
            raise RuntimeError("Asset accounting requires ordered event locks.")
        asset = None
        for model in (SubmissionAsset, HackathonParticipantAsset):
            asset = model.objects.filter(event_id=event.pk, public_id=asset_uuid).first()
            if asset is not None:
                break
        if asset is None:
            raise SubmissionError("asset_accounting_conflict", 409)
        if operation != "reserve" and not EventAssetObligation.objects.filter(asset_uuid=asset_uuid).exists():
            raise SubmissionError("asset_accounting_conflict", 409)
        receipt, _ = EventAssetObligation.objects.get_or_create(asset_uuid=asset_uuid, defaults={
            "asset_label": asset._meta.label, "asset_id_snapshot": asset.pk,
            "event_id_snapshot": event.pk, "makerspace_id_snapshot": event.makerspace_id,
            "object_key": asset.object_key, "staging_key": asset.staging_key,
            "verification_key": asset.verification_key, "managed": not limits.is_self_host(),
            "write_not_after": asset.upload_not_after,
        })
        receipt = EventAssetObligation.objects.select_for_update().get(pk=receipt.pk)
        delta = settle(receipt, operation, bytes)
        provider_delta(receipt, delta)
        receipt.save()


def accounted_bytes(makerspace):
    """Authoritative reconciler contribution, including purged-but-not-deleted bytes."""
    from django.db.models import Sum
    totals = EventAssetObligation.objects.filter(makerspace_id_snapshot=makerspace.pk).aggregate(
        reserved=Sum("reserved_bytes"), charged=Sum("charged_bytes"))
    return (totals["reserved"] or 0) + (totals["charged"] or 0)


def refresh_obligation_locked(asset):
    """Keep the last issued staging-write deadline across module/tenant purge."""
    if not connection.in_atomic_block:
        raise RuntimeError("Refresh upload custody inside the event transaction.")
    row = EventAssetObligation.objects.select_for_update().filter(asset_uuid=asset.public_id).first()
    if row is None:
        raise SubmissionError("asset_accounting_conflict", 409)
    row.write_not_after = max(value for value in (row.write_not_after, asset.upload_not_after) if value is not None)
    row.multipart_upload_id = asset.multipart_upload_id
    row.save(update_fields=["write_not_after", "multipart_upload_id"])


def accounted_print_bytes(makerspace):
    """Reservations remain charged until confirmed cleanup, including after purge."""
    from apps.events.certificates.print_models import BadgePrintJob, BadgePrintResource, BadgePrintCleanupReceipt
    from django.db.models import Sum
    jobs = BadgePrintJob.objects.filter(event__makerspace=makerspace, cleaned_at__isnull=True)
    resources = BadgePrintResource.objects.filter(job__event__makerspace=makerspace, cleaned_at__isnull=True)
    # Custody can coexist briefly with a retained graph in its purge transaction.
    # Keys represented by that graph are counted exactly once.
    receipts = BadgePrintCleanupReceipt.objects.filter(makerspace_id_snapshot=makerspace.pk, released=False).exclude(
        object_key__in=jobs.values("object_key")).exclude(object_key__in=resources.values("object_key"))
    return sum(rows.aggregate(total=Sum("size_bytes"))["total"] or 0 for rows in (jobs, resources, receipts))
