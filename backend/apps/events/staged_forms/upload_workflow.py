"""Stage file attachment is pinned to a submitted response's exact revision."""
from datetime import timedelta
from django.utils import timezone
from apps.payments.event_payouts.errors import require


def attach_locked(asset, *, response):
    require(asset.assignment_id == response.assignment_id and asset.event_id == response.event_id
        and asset.owner_member_id == response.owner_member_id and asset.form_revision_id == response.form_revision_id
        and asset.purpose == "stage_form_file" and asset.state in ("ready", "attached")
        and asset.actual_bytes == asset.expected_bytes and asset.scan_status in ("clean", "skipped"), "stage_file_unavailable")
    if asset.state == "ready":
        asset.state, asset.attached_at, asset.response = "attached", timezone.now(), response
        asset.expires_at = response.event.ends_at + timedelta(days=asset.retention_days_snapshot)
        asset.version += 1
        asset.save()
