"""Quota-debt release and abandoned row removal cannot credit storage twice."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.evidence.models import EvidencePhoto, EvidenceRetentionPolicy
from apps.evidence.abandoned_upload_cleanup import sweep_abandoned_evidence_uploads
from apps.makerspaces.models import Makerspace
from apps.makerspaces.storage_reservations import reserved_bytes
from tests.evidence.test_storage_reservations_cx7_p5 import world, upload

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending, pytest.mark.area_inventory]


@pytest.mark.parametrize("enabled", [False, True])
def test_abandoned_cleanup_keeps_default_off_and_releases_only_the_reservation(enabled, settings, monkeypatch):
    from apps.evidence import storage
    settings.EVIDENCE_ABANDONED_UPLOAD_CLEANUP_ENABLED = enabled
    settings.EVIDENCE_ABANDONED_UPLOAD_RETENTION_DAYS = 7
    space, actor, _ = world(settings, monkeypatch)
    # Independent accounted files must never be credited for this uncharged upload.
    Makerspace.objects.filter(pk=space.pk).update(storage_bytes_used=0)
    photo = upload(space, actor)
    Makerspace.objects.filter(pk=space.pk).update(storage_bytes_used=7)
    EvidenceRetentionPolicy.objects.create(makerspace=space, abandoned_upload_cleanup_enabled=enabled)
    monkeypatch.setattr(storage, "object_size", lambda key: 10)
    monkeypatch.setattr(storage, "delete_object_strict", lambda key, **kwargs: "deleted")
    monkeypatch.setattr("apps.evidence.abandoned_upload_state._storage_identity", lambda: "p5-storage")
    summary = sweep_abandoned_evidence_uploads(now=timezone.now() + timedelta(days=30))
    assert summary["photos_deleted"] == int(enabled)
    assert EvidencePhoto.objects.filter(pk=photo.pk).exists() is (not enabled)
    assert reserved_bytes(space) == (0 if enabled else 10)
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 7
