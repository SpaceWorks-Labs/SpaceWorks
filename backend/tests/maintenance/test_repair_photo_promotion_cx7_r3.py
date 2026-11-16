"""A delayed legacy repair promotion cannot replace an attached photo's bytes."""
import hashlib
from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
from io import BytesIO
from threading import Event, Lock, get_ident
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError
from django.db import connections, connection
from PIL import Image

from apps.audit.models import AuditLog
from apps.maintenance.models import IssuePhoto, IssueReport
from apps.maintenance.repairs import photos, storage
from apps.makerspaces.models import Makerspace, StorageQuotaReservation
from tests.maintenance.l16_helpers import loan, world
from tests.return_helpers import authenticated_client

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_inventory,
              pytest.mark.area_machines, pytest.mark.area_bookings]


class Objects:
    """SDK boundary with pinned reads and atomic destination create-only writes."""
    meta = SimpleNamespace(endpoint_url="https://storage.test")

    def __init__(self):
        self.values, self.mutex = {}, Lock()
        self.loser = None
        self.paused, self.resume = Event(), Event()
        self.attempts = []
        self.generate_presigned_url = Mock(return_value="https://storage.test/put")

    def write(self, key, data):
        with self.mutex:
            self.values[key] = data

    def error(self, code, status):
        return ClientError({"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}}, "object")

    def head_object(self, *, Key, **kwargs):
        if get_ident() == self.loser and Key.startswith("staging/") and not self.paused.is_set():
            self.paused.set()
            assert self.resume.wait(15), "The winning repair attachment did not release the loser."
        with self.mutex:
            if Key not in self.values:
                raise self.error("NoSuchKey", 404)
            data = self.values[Key]
            return {"ContentLength": len(data), "ETag": hashlib.sha256(data).hexdigest()}

    def get_object(self, *, Key, IfMatch=None, **kwargs):
        with self.mutex:
            if Key not in self.values:
                raise self.error("NoSuchKey", 404)
            data = self.values[Key]
            if IfMatch is not None and hashlib.sha256(data).hexdigest() != IfMatch:
                raise self.error("PreconditionFailed", 412)
            return {"Body": BytesIO(data), "ContentType": "image/webp"}

    def put_object(self, *, Key, Body, ContentLength, IfNoneMatch=None, **kwargs):
        data = Body.read()
        assert len(data) == ContentLength
        with self.mutex:
            self.attempts.append((Key, IfNoneMatch, data))
            if IfNoneMatch == "*" and Key in self.values:
                raise self.error("PreconditionFailed", 412)
            self.values[Key] = data

    def copy_object(self, *, Key, CopySource, **kwargs):
        # Deliberately implement the unsafe SDK operation so reverting the fix
        # replaces the winning object and fails the byte/accounting assertions.
        with self.mutex:
            self.values[Key] = self.values[CopySource["Key"]]

    def delete(self, key):
        with self.mutex:
            self.values.pop(key, None)
        return True


def image(colour):
    output = BytesIO()
    Image.new("RGB", (1, 1), colour).save(output, format="WEBP", lossless=True)
    return output.getvalue()


@pytest.fixture
def repair_upload(settings, monkeypatch):
    settings.STORAGE_CAPABILITIES_FILE = ""
    settings.STORAGE_PRESIGN_METHOD = "put"
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    settings.MANAGED_PLANS_ENABLED = False
    settings.EVIDENCE_MAX_BYTES = 1024
    sdk = Objects()
    monkeypatch.setattr(storage, "_client", lambda: sdk)
    monkeypatch.setattr(storage, "_public_client", lambda: sdk)
    monkeypatch.setattr(storage.shared, "_client", lambda: sdk)
    monkeypatch.setattr(storage.shared, "delete_object", sdk.delete)
    monkeypatch.setattr("apps.storage_capabilities.presigning.capabilities_for", lambda *a, **kw: None)
    monkeypatch.setattr("apps.maintenance.repairs.notify.staff", lambda *a: None)
    w = world("cx7-repair-promotion")
    request, borrower = loan(w)
    winner, replacement = image("black"), image("white")
    length = max(len(winner), len(replacement))
    assert length <= 64  # Exercise the real domain signature sniff as well.
    winner, replacement = winner.ljust(length, b"\0"), replacement.ljust(length, b"\0")
    grant = photos.issue_upload(w.space, "image/webp", photos.owner_for_user(borrower), size=length)
    row = StorageQuotaReservation.objects.get(makerspace=w.space)
    sdk.write(row.staging_key, winner)
    body = {"makerspace_id": w.space.pk, "loan_id": request.pk, "title": "Loose tip",
            "description": "The tip wobbles.", "photos": [grant["photo_token"]]}
    return w, borrower, sdk, row, winner, replacement, body


def report(user, body):
    return authenticated_client(user).post("/api/v1/member/issues", body, format="json")


def test_losing_promotion_after_attachment_and_staging_rewrite_keeps_the_winning_final(repair_upload):
    w, borrower, sdk, row, winner, replacement, body = repair_upload

    def losing_request():
        connections.close_all()
        sdk.loser = get_ident()
        try:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
            return report(borrower, body)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(losing_request)
        try:
            assert sdk.paused.wait(15), "The loser did not observe the missing final."
            accepted = report(borrower, body)
            assert accepted.status_code == 201, accepted.data
            winning_photo = IssuePhoto.objects.get()
            before_photo = IssuePhoto.objects.values().get()
            before_audit = list(AuditLog.objects.order_by("pk").values())
            row.refresh_from_db()
            assert (row.converted, row.released, row.size_bytes) == (True, False, len(winner))
            assert Makerspace.objects.get(pk=w.space.pk).storage_bytes_used == len(winner)
            assert sdk.values[row.object_key] == winner
            # The original PUT authorization is still valid, with the same size.
            sdk.write(row.staging_key, replacement)
        finally:
            sdk.resume.set()
        refused = future.result(timeout=20)

    assert (refused.status_code, refused.data["code"]) == (400, "upload_limit")
    assert sdk.values[row.object_key] == winner
    assert row.staging_key not in sdk.values
    assert sdk.attempts == [(row.object_key, "*", winner), (row.object_key, "*", replacement)]
    assert IssuePhoto.objects.values().get() == before_photo
    assert (winning_photo.object_key, winning_photo.size_bytes, winning_photo.content_type) == (
        row.object_key, len(winner), "image/webp")
    assert IssueReport.objects.filter(makerspace=w.space).count() == 1
    assert Makerspace.objects.get(pk=w.space.pk).storage_bytes_used == len(winner)
    row.refresh_from_db()
    assert (row.converted, row.cleaning, row.released, row.size_bytes) == (True, False, False, len(winner))
    assert list(AuditLog.objects.order_by("pk").values()) == before_audit
    assert AuditLog.objects.filter(makerspace=w.space, action="issue.reported").count() == 1
    assert storage.finalize(row.object_key) == len(winner)
    assert sdk.values[row.object_key] == winner
    replayed = report(borrower, body)
    assert (replayed.status_code, replayed.data["photos"].code) == (400, "invalid")
    assert str(replayed.data["photos"]) == "A photo is already attached."
    assert IssuePhoto.objects.values().get() == before_photo
    assert list(AuditLog.objects.order_by("pk").values()) == before_audit


@pytest.mark.parametrize("identity", ["foreign_space", "different_owner"])
def test_repair_photo_grant_still_requires_the_original_tenant_and_uploader(repair_upload, identity):
    from rest_framework.exceptions import ValidationError
    w, borrower, sdk, row, _, _, body = repair_upload
    target = world("cx7-repair-foreign").space if identity == "foreign_space" else w.space
    owner = photos.owner_for_user(borrower) if identity == "foreign_space" else "user:999999"
    before = list(sdk.attempts)
    with pytest.raises(ValidationError) as failure:
        photos.validate(target, body["photos"], owner)
    assert failure.value.status_code == 400
    assert failure.value.get_codes() == {"photos": "invalid"}
    assert sdk.attempts == before
    assert row.object_key not in sdk.values
    assert not IssuePhoto.objects.exists()
    assert not IssueReport.objects.exists()
    row.refresh_from_db()
    assert (row.converted, row.released, row.size_bytes) == (False, False, len(sdk.values[row.staging_key]))
