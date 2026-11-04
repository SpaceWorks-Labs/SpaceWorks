"""Ready stage bytes are required; expired bytes are expected absent."""
from datetime import datetime, UTC


def disposition(asset, *, now=None):
    now = now or datetime.now(UTC)
    if asset.expired_at is not None and asset.state in ("expired", "deleting", "deleted"):
        return "expected_expired"
    if asset.expires_at is not None and asset.expires_at <= now:
        return "retention_finalization_required"
    return "required" if asset.state == "attached" else "omit_unattached"


def capture(*, asset, add_object, now=None):
    state = disposition(asset, now=now)
    if state == "retention_finalization_required":
        raise ValueError("Finalize stage retention before capture.")
    if state == "required":
        # add_object is G's authenticated encrypted capture journal. Missing
        # attached bytes fail its normal checksum/size verification.
        return add_object(model="events.StageFormAsset", pk=asset.pk, field="object_key",
            key=asset.object_key, version_id=asset.final_version_id or None,
            sha256=asset.sha256, size_bytes=asset.actual_bytes)
    return None


def collect_keys(makerspace, add):
    from .upload_models import StageFormAsset
    for keys in StageFormAsset.objects.filter(event__makerspace=makerspace).values_list(
            "staging_key", "object_key").iterator(chunk_size=500):
        for key in keys:
            add(key)
