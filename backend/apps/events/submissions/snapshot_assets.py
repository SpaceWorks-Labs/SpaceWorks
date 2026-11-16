"""B implementation of the G1 SnapshotAssets protocol for D/A consumers."""
from django.utils import timezone
from .models_assets import SubmissionAsset
from .errors import SubmissionError


def require_ready_for_snapshot(*, asset_ids, owner_team_id, event_id):
    if (not isinstance(asset_ids, tuple) or len(asset_ids) > 100 or len(set(asset_ids)) != len(asset_ids)
            or any(type(value) is not int or value < 1 for value in asset_ids)):
        raise SubmissionError("invalid_assets")
    rows = list(SubmissionAsset.objects.filter(pk__in=asset_ids, team_id=owner_team_id, event_id=event_id))
    now = timezone.now()
    if len(rows) != len(asset_ids) or any(row.state != "ready" or row.expired_at or
        row.scan_status not in {"clean", "skipped"} or row.expires_at and row.expires_at <= now for row in rows):
        raise SubmissionError("asset_not_ready", 409)
    return tuple(sorted(row.pk for row in rows))
