from types import SimpleNamespace
from uuid import uuid4
from datetime import timedelta

import pytest
from django.db import transaction, connection, DatabaseError
from django.test import override_settings
from django.utils import timezone

from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.models_assets import HackathonParticipantAsset, EventAssetObligation
from apps.makerspaces.storage_events_programme import EventAssetStoragePool, settle, accounted_bytes
from tests.events.ticketing_helpers import account, event_space, open_event

pytestmark = pytest.mark.django_db(transaction=True)


def asset_fixture(slug="asset-pool"):
    user = account(slug)
    event = open_event(event_space(slug))
    ident = uuid4()
    asset = HackathonParticipantAsset.objects.create(event=event, member=user, uploaded_by=user,
        public_id=ident, kind="resume", extension="pdf", subtype="pdf", original_filename="resume.pdf",
        declared_mime="application/pdf", declared_bytes=80, effective_cap=100, reserved_bytes=80,
        object_key=f"final/{ident}", staging_key=f"staging/{ident}", verification_key=f"verification/{ident}",
        upload_not_after=timezone.now()-timedelta(minutes=2))
    return event, asset


def test_provider_counter_ignores_base_entitlement_and_replays_are_exact():
    with override_settings(PLATFORM_DOMAIN_SUFFIX="managed.example"):
        event, asset = asset_fixture()
        pool = EventAssetStoragePool()
        with transaction.atomic():
            pool.apply_locked(event=event, asset_uuid=asset.public_id, operation="reserve", bytes=80)
            pool.apply_locked(event=event, asset_uuid=asset.public_id, operation="reserve", bytes=80)
            pool.apply_locked(event=event, asset_uuid=asset.public_id, operation="charge", bytes=60)
            pool.apply_locked(event=event, asset_uuid=asset.public_id, operation="charge", bytes=60)
            pool.apply_locked(event=event, asset_uuid=asset.public_id, operation="release_temporary", bytes=20)
            pool.apply_locked(event=event, asset_uuid=asset.public_id, operation="release_temporary", bytes=20)
        event.makerspace.refresh_from_db()
        assert event.makerspace.storage_bytes_used == accounted_bytes(event.makerspace) == 60
        with transaction.atomic():
            pool.apply_locked(event=event, asset_uuid=asset.public_id, operation="release_all", bytes=60)
            pool.apply_locked(event=event, asset_uuid=asset.public_id, operation="release_all", bytes=60)
        event.makerspace.refresh_from_db()
        assert event.makerspace.storage_bytes_used == accounted_bytes(event.makerspace) == 0


def test_event_pool_does_not_consume_the_ordinary_base_storage_allowance(monkeypatch):
    from apps.makerspaces import limits
    with override_settings(PLATFORM_DOMAIN_SUFFIX="managed.example"):
        event, asset = asset_fixture("separate-entitlements")
        monkeypatch.setattr(limits, "resource_limit", lambda space, key: 10)
        with transaction.atomic():
            EventAssetStoragePool().apply_locked(event=event, asset_uuid=asset.public_id, operation="reserve", bytes=80)
        limits.add_storage(event.makerspace, 10)
        event.makerspace.refresh_from_db()
        assert event.makerspace.storage_bytes_used == 90
        assert limits._storage(event.makerspace) == 10
        with pytest.raises(Exception):
            limits.add_storage(event.makerspace, 1)


def test_receipt_cannot_be_deleted_even_by_purge_and_keys_cannot_be_reused():
    event, asset = asset_fixture("permanent-custody")
    with transaction.atomic():
        EventAssetStoragePool().apply_locked(event=event, asset_uuid=asset.public_id, operation="reserve", bytes=80)
    receipt = EventAssetObligation.objects.get(asset_uuid=asset.public_id)
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.allow_immutable_delete='on'")
        cursor.execute("DELETE FROM events_eventassetobligation WHERE id=%s", [receipt.pk])
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("UPDATE events_hackathonparticipantasset SET object_key=%s WHERE id=%s",
                       [receipt.verification_key, asset.pk])


def test_accounting_rejects_mismatched_replay_and_cannot_revive_released_bytes():
    row = SimpleNamespace(initial_bytes=0, reserved_bytes=0, canonical_extra_bytes=0, charged_bytes=0,
                          fully_released=False, temporary_released=False)
    assert settle(row, "reserve", 80) == 80
    with pytest.raises(SubmissionError) as conflict:
        settle(row, "reserve", 81)
    assert conflict.value.code == "asset_accounting_conflict" and conflict.value.status == 409
    assert settle(row, "release_all", 80) == -80
    with pytest.raises(SubmissionError):
        settle(row, "charge", 1)
