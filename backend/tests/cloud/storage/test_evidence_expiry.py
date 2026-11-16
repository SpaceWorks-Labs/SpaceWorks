from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.evidence import storage
from apps.evidence.models import EvidenceObjectRetentionState
from apps.evidence.services_retention import sweep_evidence_retention
from tests.evidence.test_object_retention import make_space, make_manager, make_photo

pytestmark = pytest.mark.django_db


def test_two_key_absence_releases_quota_once_without_deleting_evidence(settings, monkeypatch):
    settings.STORAGE_PRESIGN_METHOD = "post"
    settings.EVIDENCE_OBJECT_EXPIRY_ENABLED = True
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    space = make_space("cloud-retention-once")
    photo = make_photo(space, make_manager("cloud-retention-manager", space))
    monkeypatch.setattr(storage, "object_size", lambda key: 123)
    deleted = Mock(return_value="deleted")
    monkeypatch.setattr(storage, "delete_object_strict", deleted)
    monkeypatch.setattr(storage, "uses_put_uploads", lambda: False)
    freed = Mock()
    monkeypatch.setattr("apps.evidence.services_retention.limits.free_storage", freed)
    now = timezone.now() + timedelta(days=400)
    first = sweep_evidence_retention(now=now)
    second = sweep_evidence_retention(now=now)
    assert first["photos_expired"] == 1 and second["photos_expired"] == 0
    assert photo.__class__.objects.filter(pk=photo.pk).exists()
    assert EvidenceObjectRetentionState.objects.get(evidence=photo).status == "expired"
    assert deleted.call_count == 2 and freed.call_count == 1
    assert AuditLog.objects.filter(action="evidence.object_expired", target_id=str(photo.pk)).count() == 1


def test_failed_second_key_keeps_quota_and_retryable_metadata(settings, monkeypatch):
    settings.EVIDENCE_OBJECT_EXPIRY_ENABLED = True
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    space = make_space("cloud-retention-failure")
    photo = make_photo(space, make_manager("cloud-failure-manager", space))
    monkeypatch.setattr(storage, "object_size", lambda key: 123)
    monkeypatch.setattr(storage, "delete_object_strict", Mock(side_effect=["deleted", storage.StorageUnavailable()]))
    freed = Mock()
    monkeypatch.setattr("apps.evidence.services_retention.limits.free_storage", freed)
    result = sweep_evidence_retention(now=timezone.now() + timedelta(days=400))
    assert result["photos_failed"] == 1
    assert EvidenceObjectRetentionState.objects.get(evidence=photo).status == "expiring"
    freed.assert_not_called()
    assert not AuditLog.objects.filter(action="evidence.object_expired", target_id=str(photo.pk)).exists()
