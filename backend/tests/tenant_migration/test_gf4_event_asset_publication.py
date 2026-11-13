"""Trusted import journals publish event asset budgets without a base-cap charge."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.events.submissions.models_assets import EventAssetUsage, EventAssetObligation
from apps.tenant_migration.models_import_job import TenantImportJob
from apps.tenant_migration.models_import_objects import TenantImportObject
from apps.tenant_migration.import_finalization import _commit_completion
from apps.tenant_migration.object_promotion import _mark_promoted_and_charge
from apps.tenant_migration.tenant_restore_objects import _charge_accepted_bytes
from tests.events.programme.uploads.test_pool_receipts import asset_fixture

pytestmark = pytest.mark.django_db(transaction=True)


def target(slug):
    event, asset = asset_fixture(slug)
    event.makerspace.lifecycle_state = "importing"
    event.makerspace.save(update_fields=["lifecycle_state"])
    asset.state, asset.scan_status = "ready", "clean"
    asset.actual_bytes, asset.charged_bytes, asset.reserved_bytes = 80, 80, 0
    asset.sha256, asset.ready_at = "a" * 64, timezone.now()
    asset.save(update_fields=["state", "scan_status", "actual_bytes", "charged_bytes", "reserved_bytes", "sha256", "ready_at"])
    job = TenantImportJob.objects.create(target_makerspace=event.makerspace, status="finalizing",
        source_archive_digest="b" * 64, expires_at=timezone.now() + timedelta(days=1),
        materialization_report={"imported": {}, "identities_linked": 0, "identities_created": 0})
    return event, asset, job


def journal(job, asset, *, state="verified"):
    return TenantImportObject.objects.create(job=job, source_key="source", target_key=asset.object_key,
        staging_key="import-staging", bucket_kind="private", size=80, sha256=asset.sha256,
        state=state, claimed_at=timezone.now())


def test_actual_completion_installs_receipt_and_budget_once():
    event, asset, job = target("gf4-import-final")
    journal(job, asset)
    completed, fresh = _commit_completion(job.pk, actor=None)
    assert completed.status == "completed" and fresh
    assert EventAssetUsage.objects.get(event=event).used_bytes == 80
    receipt = EventAssetObligation.objects.get(asset_uuid=asset.public_id)
    assert (receipt.event_id_snapshot, receipt.makerspace_id_snapshot, receipt.charged_bytes) == (event.pk, event.makerspace_id, 80)
    assert _commit_completion(job.pk, actor=None)[1] is False
    assert EventAssetObligation.objects.filter(asset_uuid=asset.public_id).count() == 1


def test_actual_completion_refuses_unverified_bytes_and_rolls_back_publication():
    event, asset, job = target("gf4-import-unverified")
    journal(job, asset, state="promoted")
    with pytest.raises(ValueError):
        _commit_completion(job.pk, actor=None)
    job.refresh_from_db()
    assert job.status == "finalizing"
    assert not EventAssetObligation.objects.filter(asset_uuid=asset.public_id).exists()


def test_portable_promotion_uses_event_pool_above_ordinary_allowance(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = "managed.example"
    settings.MANAGED_RESOURCE_LIMITS = {"storage": 10}
    event, asset, job = target("gf4-import-charge")
    row = journal(job, asset, state="staged")
    _mark_promoted_and_charge(row.pk, event.makerspace, claimed_at=row.claimed_at)
    event.makerspace.refresh_from_db()
    row.refresh_from_db()
    assert event.makerspace.storage_bytes_used == 80
    assert row.state == "promoted" and row.quota_charged_at


def test_raw_dump_watermark_classifies_trusted_canonical_asset(settings):
    settings.PLATFORM_DOMAIN_SUFFIX = "managed.example"
    settings.MANAGED_RESOURCE_LIMITS = {"storage": 10}
    event, asset, job = target("gf4-raw-charge")
    detail = {"key": asset.object_key, "bucket": settings.AWS_STORAGE_BUCKET_NAME,
              "digest": asset.sha256, "accepted_size": 80}
    ledger = SimpleNamespace(records=lambda: [{"state": "begun", "phase": "object-load-0", "detail": detail}])
    _charge_accepted_bytes(ledger, event.makerspace, "object-load-0")
    _charge_accepted_bytes(ledger, event.makerspace, "object-load-0")
    event.makerspace.refresh_from_db()
    assert event.makerspace.storage_bytes_used == 80


def test_import_key_allocator_reserves_receipt_final_and_staging_names_even_if_both_absent(monkeypatch):
    from apps.accounts.models import User
    from apps.evidence.models import EvidencePhoto, EvidenceAbandonedUploadReceipt
    from apps.makerspaces.models import Makerspace
    from apps.tenant_migration import object_storage
    tenant = Makerspace.objects.create(name="Receipt reservation", slug="gf4-receipt-reservation")
    user = User.objects.create_user(username="gf4-receipt-owner")
    photo = EvidencePhoto.objects.create(makerspace=tenant, uploaded_by=user,
        evidence_type="issue", object_key="evidence/receipt-reserved", consumption_state="unconsumed")
    EvidenceAbandonedUploadReceipt.objects.create(source_makerspace_id_snapshot=tenant.pk,
        evidence_id_snapshot=photo.pk, object_key=photo.object_key, next_reconcile_at=timezone.now())
    monkeypatch.setattr(object_storage, "object_exists", lambda *args: False)
    for key in (photo.object_key, "staging/"+photo.object_key):
        chosen, renamed = object_storage.choose_target_key("private", key, "gf4-receipt-import")
        assert renamed and chosen != key
