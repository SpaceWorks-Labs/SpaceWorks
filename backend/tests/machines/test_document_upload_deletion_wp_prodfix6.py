"""R3: bounded POST admission differs from the document's durable charge."""
import base64
from io import BytesIO
import json

import boto3
from botocore.client import Config
import pytest
from django.db import connection, transaction
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.machines import services, storage, type_documents
from apps.machines.models import MachineDocument, MachineTypeDocument
from apps.makerspaces import limits, storage_reservations as reservations
from apps.makerspaces.models import Makerspace, StorageQuotaReservation
from tests.machines.route_support_cx11b_g2 import toggle, world
from tests.machines.test_document_deletion_wp_prodfix2 import VersionedProvider, recompute, used
from tests.modules.switch_matrix_object_helpers import response_pair
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_machines]
PDF = b"%PDF-1.7\nx"


class UploadProvider(VersionedProvider):
    """SDK-shaped bytes store; presigning uses boto3's actual POST policy signer."""

    def head_object(self, **kwargs):
        return {**super().head_object(**kwargs), "VersionId": "current"}

    def get_object(self, **kwargs):
        return {"Body": BytesIO(PDF), "ContentType": "application/pdf"}

    def put_object(self, *, Key, Body, ContentLength, IfNoneMatch, **kwargs):
        assert IfNoneMatch == "*"
        assert Body.read() == PDF
        assert ContentLength == len(PDF)
        assert Key not in self.versions
        self.versions[Key] = {"current": ContentLength}
        return {}


def attached(native, kind, declared, monkeypatch, settings):
    settings.STORAGE_CAPABILITIES_FILE = ""
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.STORAGE_PRESIGN_METHOD = "post"
    settings.MACHINE_DOC_MAX_BYTES = 100
    w = world(native)
    provider = UploadProvider({})
    signer = boto3.client("s3", endpoint_url="https://uploads.example.test",
                          aws_access_key_id="test", aws_secret_access_key="test",
                          region_name="us-east-1", config=Config(signature_version="s3v4"))
    monkeypatch.setattr(storage, "_client", lambda: provider)
    monkeypatch.setattr(storage, "_public_client", lambda: signer)
    kept_key = storage.machine_object_key(w.space.pk, "pdf")
    MachineDocument.objects.create(machine=w.machine, object_key=kept_key, doc_type="sop",
                                   original_filename="kept.pdf", content_type="application/pdf", size_bytes=23)
    provider.versions[kept_key] = {"current": 23}
    limits.add_storage(w.space, 23)
    Makerspace.objects.filter(pk=w.other.pk).update(storage_bytes_used=41)
    args = [w.machine.pk] if kind == "machine" else [w.space.pk, w.machine_type.pk]
    prefix = "admin-machine-document" if kind == "machine" else "machine-type-document"
    body = {"content_type": "application/pdf", "filename": "manual.pdf"}
    if declared is not None:
        body["size"] = declared
    response = w.client.post(reverse(prefix + "-presign", args=args), body, format="json")
    assert response_pair(response) == (201, None)
    key, upload = response.data["object_key"], response.data["upload"]
    debt = StorageQuotaReservation.objects.get(object_key=key)
    maximum = declared if declared is not None else 100
    assert (debt.size_bytes, debt.converted, debt.released, used(w.space), used(w.other)) == (
        maximum, False, False, 23, 41)
    policy = json.loads(base64.b64decode(upload["fields"]["policy"]))
    assert ["content-length-range", 1, maximum] in policy["conditions"]
    assert upload["fields"]["key"] == debt.staging_key == storage.staging_key(key)
    original = (debt.size_bytes, debt.expires_at, debt.bucket, debt.final_bucket,
                debt.storage_endpoint, debt.kind, debt.staging_key, debt.final_key)
    provider.versions[debt.staging_key] = {"current": len(PDF)}
    body = {"object_key": key, "original_filename": "manual.pdf"}
    body.update({"doc_type": "manual"} if kind == "machine" else {"title": "Manual"})
    list_name = "admin-machine-documents" if kind == "machine" else "machine-type-documents"
    response = w.client.post(reverse(list_name, args=args), body, format="json")
    assert response_pair(response) == (201, None)
    model = MachineDocument if kind == "machine" else MachineTypeDocument
    row = model.objects.get(pk=response.data["id"])
    assert (row.size_bytes, row.object_key, used(w.space), used(w.other)) == (10, key, 33, 41)
    assert provider.versions[debt.staging_key] == {}
    debt.refresh_from_db()
    assert (debt.converted, debt.released) == (True, False)
    action = "machine.document_removed" if kind == "machine" else "machine_type_document.removed"
    audits = AuditLog.objects.filter(makerspace=w.space, action=action)
    delete_args = [row.pk] if kind == "machine" else [w.space.pk, w.machine_type.pk, row.pk]
    url = reverse(prefix + "-detail", args=delete_args)
    return w, row, debt, provider, audits, url, original


@pytest.mark.parametrize("native", [False, True], ids=["web", "native"])
@pytest.mark.parametrize("kind", ["machine", "type"])
@pytest.mark.parametrize("declared", [None, 80], ids=["size-omitted", "declared-maximum"])
@pytest.mark.parametrize("failure", [None, "transport", "partial"])
def test_real_post_smaller_document_deletes_actual_charge_and_preserves_admission(
        native, kind, declared, failure, monkeypatch, settings):
    w, row, debt, provider, audits, url, original = attached(native, kind, declared, monkeypatch, settings)
    model, key = type(row), row.object_key
    before = model.objects.filter(pk=row.pk).values().get()
    provider.versions[key]["previous"] = 6
    batches = len(provider.batches)

    def deleting():
        assert connection.in_atomic_block is False
        assert model.objects.filter(pk=row.pk).values().get() == before
        assert (used(w.space), used(w.other), audits.count()) == (33, 41, 0)

    provider.before_delete = deleting
    provider.mode = failure
    if failure:
        assert response_pair(w.client.delete(url)) == (503, "storage_unavailable")
        assert model.objects.filter(pk=row.pk).values().get() == before
        assert (used(w.space), used(w.other), audits.count()) == (33, 41, 0)
        debt.refresh_from_db()
        assert (debt.cleaning, debt.released) == (True, False)
        if failure == "partial":
            assert provider.versions[key] == {"previous": 6}
            assert storage.object_size(key) is None
        provider.mode = None
        recompute(w.space, 33)
    assert response_pair(w.client.delete(url)) == (204, None)
    assert model.objects.filter(pk=row.pk).exists() is False
    assert (used(w.space), used(w.other), audits.count(), provider.versions[key]) == (23, 41, 1, {})
    expected_batches = 2 if failure == "partial" else 1
    assert len(provider.batches) - batches == expected_batches
    debt.refresh_from_db()
    assert (debt.converted, debt.released, debt.cleaning) == (True, True, False)
    assert (debt.size_bytes, debt.expires_at, debt.bucket, debt.final_bucket,
            debt.storage_endpoint, debt.kind, debt.staging_key, debt.final_key) == original
    batches = list(provider.batches)
    if kind == "machine":
        services.remove_document(w.machine, w.actor, row)
    else:
        type_documents.remove(w.actor, row)
    with no_domain_writes():
        replay = w.client.delete(url)
    expected = (403, "permission_denied") if native and kind == "machine" else (404, "not_found")
    assert response_pair(replay) == expected
    assert (used(w.space), used(w.other), audits.count(), provider.batches) == (23, 41, 1, batches)
    recompute(w.space, 23)
    recompute(w.space, 23)
    assert used(w.other) == 41


@pytest.mark.parametrize("kind", ["machine", "type"])
def test_document_delete_module_off_keeps_claim_and_restores(kind, monkeypatch, settings):
    w, row, debt, provider, audits, url, _ = attached(False, kind, None, monkeypatch, settings)
    previous = toggle(w.space, "machines")
    batches = list(provider.batches)
    with no_domain_writes():
        response = w.client.delete(url)
    assert response_pair(response) == (404, "module_disabled")
    debt.refresh_from_db()
    assert (debt.cleaning, debt.released, used(w.space), used(w.other), audits.count()) == (
        False, False, 33, 41, 0)
    assert type(row).objects.filter(pk=row.pk).exists() is True
    assert provider.batches == batches
    toggle(w.space, "machines", previous)
    assert response_pair(w.client.delete(url)) == (204, None)
    assert (used(w.space), used(w.other), audits.count()) == (23, 41, 1)


@pytest.mark.parametrize("field", ["makerspace_id", "final_key", "bucket", "final_bucket",
                                  "staging_key", "storage_endpoint", "kind", "size_bytes"])
def test_bounded_document_claim_still_validates_identity_and_upper_bound(field, monkeypatch, settings):
    w, row, debt, provider, audits, _, _ = attached(False, "machine", None, monkeypatch, settings)
    value = w.other.pk if field == "makerspace_id" else 9 if field == "size_bytes" else "mismatched"
    StorageQuotaReservation.objects.filter(pk=debt.pk).update(**{field: value})
    batches = list(provider.batches)
    error = "size" if field == "size_bytes" else "identity"
    with pytest.raises(ValueError, match="Storage claim " + error + " mismatch"):
        services.remove_document(w.machine, w.actor, row)
    assert (used(w.space), used(w.other), audits.count(), provider.batches) == (33, 41, 0, batches)
    assert MachineDocument.objects.filter(pk=row.pk).exists() is True


def test_default_claim_keeps_artifact_size_exact(monkeypatch, settings):
    w, _, _, _, _, _, _ = attached(False, "machine", None, monkeypatch, settings)
    key = "adapter-artifacts/" + str(w.space.pk) + "/exact.pdf"
    storage.presigned_upload(key, "application/pdf", exact_bytes=80)
    debt = StorageQuotaReservation.objects.get(object_key=key)
    with transaction.atomic():
        space = Makerspace.objects.select_for_update().get(pk=w.space.pk)
        for charged in (False, True):
            with pytest.raises(ValueError, match="Storage claim size mismatch"):
                reservations.deletion_claim(space, key, 10, charged=charged)
        with pytest.raises(ValueError, match="Storage claim size mismatch"):
            reservations.deletion_claim(space, key, 10, charged=False, bounded_upload=True)
    debt.refresh_from_db()
    assert (debt.size_bytes, debt.converted, debt.cleaning, debt.released) == (80, False, False, False)


@pytest.mark.parametrize("native", [False, True], ids=["web", "native"])
def test_type_document_fence_failure_has_shared_error_without_deletion(native, monkeypatch, settings):
    from tests.machines.test_object_fence_wp_prodfix5 import fail_fence_connection

    w, row, debt, provider, audits, url, _ = attached(native, "type", None, monkeypatch, settings)
    batches = list(provider.batches)
    connect = fail_fence_connection(monkeypatch)
    assert response_pair(w.client.delete(url)) == (503, "storage_unavailable")
    assert MachineTypeDocument.objects.filter(pk=row.pk).exists() is True
    assert (used(w.space), used(w.other), audits.count(), provider.batches) == (33, 41, 0, batches)
    debt.refresh_from_db()
    assert (debt.cleaning, debt.released) == (False, False)
    connect.assert_called_once()


def test_type_document_audit_rollback_keeps_debt_until_absent_object_retry(monkeypatch, settings):
    w, row, debt, provider, audits, url, _ = attached(False, "type", None, monkeypatch, settings)
    original_audit = type_documents.audit.record

    def fail(*args, **kwargs):
        raise RuntimeError("audit write unavailable")

    monkeypatch.setattr(type_documents.audit, "record", fail)
    with pytest.raises(RuntimeError, match="audit write unavailable"):
        type_documents.remove(w.actor, row)
    assert MachineTypeDocument.objects.filter(pk=row.pk).exists() is True
    assert (used(w.space), used(w.other), audits.count(), provider.versions[row.object_key]) == (33, 41, 0, {})
    debt.refresh_from_db()
    assert (debt.cleaning, debt.released) == (True, False)
    recompute(w.space, 33)
    batches = list(provider.batches)
    monkeypatch.setattr(type_documents.audit, "record", original_audit)
    assert response_pair(w.client.delete(url)) == (204, None)
    assert (used(w.space), used(w.other), audits.count(), provider.batches) == (23, 41, 1, batches)
    recompute(w.space, 23)


def test_two_stale_type_deletions_release_recorded_charge_once(monkeypatch, settings):
    from threading import Barrier
    from django.db import close_old_connections, connections
    from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor

    w, row, debt, provider, audits, _, _ = attached(False, "type", None, monkeypatch, settings)
    batches = len(provider.batches)
    gate = Barrier(2)

    def deleting():
        assert connection.in_atomic_block is False
        assert (used(w.space), used(w.other), audits.count()) == (33, 41, 0)

    provider.before_delete = deleting

    def worker():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
                cursor.execute("SELECT pg_backend_pid()")
                pid = cursor.fetchone()[0]
            stale = MachineTypeDocument.objects.get(pk=row.pk)
            stale.size_bytes = 999
            gate.wait(timeout=10)
            type_documents.remove(w.actor, stale)
            return pid
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        pids = [future.result(timeout=30) for future in futures]
    assert len(set(pids)) == 2
    assert MachineTypeDocument.objects.filter(pk=row.pk).exists() is False
    assert (used(w.space), used(w.other), audits.count(), len(provider.batches) - batches) == (23, 41, 1, 1)
    debt.refresh_from_db()
    assert (debt.size_bytes, debt.released, debt.cleaning) == (100, True, False)
    recompute(w.space, 23)
