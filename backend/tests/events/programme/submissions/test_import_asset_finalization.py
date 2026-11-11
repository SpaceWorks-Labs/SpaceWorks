from datetime import timedelta
from django.db import transaction
from django.utils import timezone
import pytest

from apps.events.submissions.portability import asset_import_values, finalize_imported_assets
from apps.events.submissions.models_assets import EventAssetObligation, EventAssetUsage
from tests.events.programme.uploads.test_pool_receipts import asset_fixture

pytestmark = pytest.mark.django_db(transaction=True)


def test_pending_upload_is_inert_and_all_source_bucket_versions_are_cleared():
    source = {"state": "promoting", "actual_bytes": 17, "final_version_id": "source-version",
              "reserved_bytes": 80, "multipart_upload_id": "source-upload", "expired_at": None}
    result = asset_import_values(source)
    assert result["state"] == "aborted" and result["expired_at"] and result["deleted_at"]
    assert result["final_version_id"] == result["multipart_upload_id"] == ""
    assert result["reserved_bytes"] == result["charged_bytes"] == 0
    assert source["state"] == "promoting"


def test_target_usage_and_custody_derive_from_accepted_canonical_bytes_only():
    event, asset = asset_fixture("imported-asset-budget")
    event.makerspace.lifecycle_state = "importing"
    event.makerspace.save(update_fields=["lifecycle_state"])
    asset.state, asset.ready_at, asset.actual_bytes = "ready", timezone.now(), 60
    asset.sha256, asset.scan_status, asset.canonical_mime = "a" * 64, "skipped", "application/pdf"
    asset.reserved_bytes, asset.charged_bytes = 0, 60
    asset.expires_at = timezone.now()+timedelta(days=12)
    asset.save()
    with transaction.atomic():
        with pytest.raises(ValueError), transaction.atomic():
            finalize_imported_assets(event=event, accepted_objects={})
        proof = {asset.object_key: (60, "a" * 64, "target-version")}
        assert finalize_imported_assets(event=event, accepted_objects=proof) == 60
        assert finalize_imported_assets(event=event, accepted_objects=proof) == 60
    usage = EventAssetUsage.objects.get(event=event)
    assert usage.used_bytes == 60 and usage.reserved_bytes == 0 and usage.budget_bytes is None
    receipt = EventAssetObligation.objects.get(asset_uuid=asset.public_id)
    assert receipt.charged_bytes == 60 and receipt.reserved_bytes == 0
    asset.refresh_from_db()
    assert asset.expires_at.date() == (timezone.now()+timedelta(days=12)).date()
