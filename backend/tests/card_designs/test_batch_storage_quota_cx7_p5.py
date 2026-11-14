"""Temporary photo batches must not create an uncharged private storage pool."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.card_designs import photo_batch
from apps.card_designs.models_cutout import CardPhotoBatch, CardPhotoBatchItem
from apps.makerspaces.storage_reservations import reserved_bytes
from apps.makerspaces.storage_reservation_cleanup import cleanup
from apps.makerspaces.models import StorageQuotaReservation
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_membership]


def setup(settings, monkeypatch, key):
    space = make_space("p5-photo-batch")
    settings.MANAGED_PLANS_ENABLED = False
    space.resource_limit_overrides = {key: 10}
    space.save(update_fields=["resource_limit_overrides"])
    batches = [CardPhotoBatch.objects.create(makerspace=space, kind="member_card", holders_consented=True,
        expires_at=timezone.now() + timedelta(days=7)) for _ in range(2)]
    monkeypatch.setattr(photo_batch.roster, "holders", lambda *args: [])
    monkeypatch.setattr(photo_batch, "normalise", lambda *args, **kwargs: (b"p" * 10, 1, 1, ""))
    writer = Mock()
    monkeypatch.setattr(photo_batch, "put_bytes", writer)
    return space, batches, writer


def add(space, batch):
    return photo_batch.add_files(batch, space, None,
        [SimpleUploadedFile("unmatched.png", b"p" * 10, content_type="image/png")])


@pytest.mark.parametrize("key,status,code", [("storage", 400, "limit_reached"),
    ("storage_public_images_bytes", 409, "storage_public_images_bytes_quota_reached")])
def test_batch_max_next_is_typed_before_remote_write_and_cleanup_releases_capacity(key, status, code, settings, monkeypatch):
    space, batches, writer = setup(settings, monkeypatch, key)
    assert add(space, batches[0]) == 0
    assert reserved_bytes(space) == 10
    with pytest.raises(APIException) as failure:
        add(space, batches[1])
    assert (failure.value.status_code, str(failure.value.detail["code"])) == (status, code)
    assert (writer.call_count, CardPhotoBatchItem.objects.count()) == (1, 1)
    row = StorageQuotaReservation.objects.get(makerspace=space)
    monkeypatch.setattr("apps.evidence.storage._client", lambda: object())
    monkeypatch.setattr("apps.object_storage.delete_all_versions", lambda *args, **kwargs: SimpleNamespace(absence_confirmed=True))
    assert cleanup(row.pk, now=row.expires_at + timedelta(seconds=1)) is True
    assert reserved_bytes(space) == 0
    assert add(space, batches[1]) == 0
    assert writer.call_count == 2


@pytest.mark.django_db(transaction=True)
def test_independent_batches_share_one_last_slot(settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, batches, writer = setup(settings, monkeypatch, "storage")
    assert race_creators(lambda index: add(space, batches[index])) == [(201, "created"), (400, "limit_reached")]
    assert (writer.call_count, CardPhotoBatchItem.objects.count(), reserved_bytes(space)) == (1, 1, 10)
