"""G11 storage tail: durable cleanup receipts and usage reconciliation."""
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.events.models_r2_l2 import SubmissionStorageCleanupReceipt
from apps.events.submissions.models_assets import EventAssetUsage
from apps.events.submissions.storage_cleanup import delete_keys, record_receipts
from apps.events.submissions.storage_reconcile import reconcile_event, reconcile_event_storage_task
from tests.events.ticketing_helpers import event_space, open_event

pytestmark = pytest.mark.django_db


class FakeClient:
    """A versioned bucket holding two versions, one marker and one upload of `key`."""

    def __init__(self, key):
        self.key, self.gone = key, False

    def get_paginator(self, name):
        client = self

        class Pager:
            def paginate(self, **kwargs):
                if name == "list_object_versions":
                    yield ({} if client.gone else {
                        "Versions": [{"Key": client.key, "VersionId": "1"}, {"Key": client.key, "VersionId": "2"}],
                        "DeleteMarkers": [{"Key": client.key, "VersionId": "m"}]})
                else:
                    yield {} if client.gone else {"Uploads": [{"Key": client.key, "UploadId": "u"}]}
        return Pager()

    def delete_objects(self, **kwargs):
        return {}

    def delete_object(self, **kwargs):
        pass

    def abort_multipart_upload(self, **kwargs):
        self.gone = True

    def head_object(self, **kwargs):
        error = Exception()
        error.response = {"Error": {"Code": "404"}}
        raise error


def test_cleanup_tallies_become_one_append_only_receipt_per_key():
    storage = type("S", (), {"client": FakeClient("events/1/a"), "bucket": "b"})()
    tallies = delete_keys(storage, ["events/1/a", ""])
    assert tallies == {"events/1/a": {"versions": 2, "markers": 1, "uploads": 1}}
    asset = uuid4()
    record_receipts(makerspace_id=1, event_id=2, asset_uuid=asset, tallies=tallies)
    record_receipts(makerspace_id=1, event_id=2, asset_uuid=asset, tallies=tallies)
    receipt = SubmissionStorageCleanupReceipt.objects.get(asset_uuid=asset)
    assert receipt.versions_deleted == 2 and "events/1/a" not in receipt.key_sha256
    with pytest.raises(ValidationError):
        receipt.delete()


def test_usage_drift_is_corrected_and_audited():
    event = open_event(event_space("reconcile"))
    usage = EventAssetUsage.objects.create(event=event, reserved_bytes=500, used_bytes=900)
    assert reconcile_event(event.pk) == {"changed": True, "adopted": 0}
    usage.refresh_from_db()
    assert (usage.reserved_bytes, usage.used_bytes) == (0, 0)
    assert AuditLog.objects.filter(action="event.asset_usage_reconciled").count() == 1
    assert reconcile_event(event.pk) == {"changed": False, "adopted": 0}
    assert reconcile_event_storage_task()["failed"] == 0
