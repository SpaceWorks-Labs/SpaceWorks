"""Durable deletion retries/holds and terminal metadata without domain lookups."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4
import pytest
from django.db import transaction
from django.utils import timezone
from apps.payments.event_payouts import attachment_workflow, cleanup, eligibility_workflow
from apps.payments.event_payouts.cleanup_models import FinanceObjectCleanup
from apps.payments.event_payouts.retention import expire_asset
from apps.payments.event_payouts.worker_boundary import locked_asset
from .conftest import request_for
from .test_cancel_unpaid import detach, cancel_data
from apps.payments.event_payouts.obligation_workflow import cancel_unpaid

pytestmark = pytest.mark.django_db(transaction=True)


def close(bundle):
    detach(bundle)
    data = cancel_data(bundle.obligation)
    cancel_unpaid(request=request_for(bundle.actor, data), obligation_id=bundle.obligation.pk, data=data)
    bundle.asset.refresh_from_db()


def test_retention_hold_defers_expiry_and_release_makes_it_due(finance_bundle):
    b = finance_bundle
    close(b)
    with locked_asset(b.asset.pk) as (row, obligation):
        attachment_workflow.hold_locked(row, actor=b.actor, reason_code="legal_review",
            hold_until=timezone.now() + timedelta(days=3000))
    assert not expire_asset(b.asset.pk, now=b.asset.expires_at + timedelta(days=1))
    with locked_asset(b.asset.pk) as (row, obligation):
        attachment_workflow.hold_locked(row, actor=b.actor, reason_code="review_complete", hold_until=None, release=True)
    assert expire_asset(b.asset.pk, now=b.asset.expires_at + timedelta(days=1))
    b.asset.refresh_from_db()
    assert b.asset.state == "expired" and b.asset.sha256 == "a" * 64


def test_storage_failure_retains_locators_and_success_reschedules_all_version_reconciliation(finance_bundle):
    b = finance_bundle
    close(b)
    expire_asset(b.asset.pk, now=b.asset.expires_at + timedelta(days=1))
    locator = FinanceObjectCleanup.objects.get(asset_id=b.asset.pk)
    # expire_asset's test clock is deliberately future; admit this retry now.
    FinanceObjectCleanup.objects.filter(pk=locator.pk).update(next_attempt_at=timezone.now())
    def fail(key):
        raise OSError("private storage failure")
    assert not cleanup.delete_one(locator.pk, storage=SimpleNamespace(delete=fail))
    locator.refresh_from_db()
    assert locator.last_error_code == "storage_delete_unavailable" and locator.next_attempt_at > timezone.now()
    FinanceObjectCleanup.objects.filter(pk=locator.pk).update(next_attempt_at=timezone.now())
    keys = []
    assert cleanup.delete_one(locator.pk, storage=SimpleNamespace(delete=keys.append))
    locator.refresh_from_db(); b.asset.refresh_from_db()
    assert keys == [b.asset.staging_key, b.asset.object_key] and b.asset.state == "deleted"
    assert locator.deleted_at and locator.next_attempt_at > timezone.now()


def test_cleanup_does_not_need_live_tenant_or_source_and_locators_cannot_be_deleted(finance_bundle):
    b = finance_bundle
    locator = FinanceObjectCleanup.objects.get(asset_id=b.asset.pk)
    # A standalone FK-free locator represents G's before-purge collection hook.
    other = FinanceObjectCleanup.objects.create(source_makerspace_id=2147483000, asset_id=2147483000,
        bucket="private-test", staging_key="finance/gone/staging", object_key="finance/gone/final", next_attempt_at=timezone.now())
    keys = []
    assert cleanup.delete_one(other.pk, storage=SimpleNamespace(delete=keys.append))
    assert len(keys) == 2
    with pytest.raises(RuntimeError):
        other.delete()
    with pytest.raises(RuntimeError):
        FinanceObjectCleanup.objects.filter(pk=other.pk).delete()
