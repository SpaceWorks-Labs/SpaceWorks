"""Confirmed document deletion, retained quota debt and exact-once retry release."""
from io import StringIO

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from django.core.management import call_command
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.machines import services, storage
from apps.machines.models import MachineDocument
from apps.makerspaces import limits
from apps.makerspaces.models import Makerspace
from tests.machines.route_support_cx11b_g2 import toggle
from tests.machines.test_cross_audit_document_lifecycle_cx9_wp2 import scenario
from tests.modules.switch_matrix_object_helpers import response_pair
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines]


class VersionedProvider:
    """Exercise the real all-version deletion and absence proof, with SDK failures."""

    def __init__(self, objects):
        self.versions = {key: {"current": size, "previous": size}
                         for key, size in objects.items()}
        self.mode = None
        self.batches = []
        self.before_delete = lambda: None

    def list_object_versions(self, *, Bucket, Prefix, MaxKeys):
        if self.mode == "transport":
            raise EndpointConnectionError(endpoint_url="https://unavailable.example.test")
        return {"IsTruncated": False, "Versions": [
            {"Key": key, "VersionId": version, "Size": size}
            for key, versions in self.versions.items() if key.startswith(Prefix)
            for version, size in versions.items()
        ]}

    def delete_objects(self, *, Bucket, Delete):
        self.before_delete()
        self.batches.append(Delete["Objects"])
        if self.mode == "denied":
            raise ClientError({"Error": {"Code": "AccessDenied"}}, "DeleteObjects")
        for obj in Delete["Objects"]:
            if self.mode == "partial" and obj["VersionId"] == "previous":
                continue
            self.versions[obj["Key"]].pop(obj["VersionId"])
        if self.mode == "partial":
            return {"Errors": [{"Code": "AccessDenied"}]}
        return {}

    def head_object(self, *, Bucket, Key):
        size = self.versions.get(Key, {}).get("current")
        if size is None:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject")
        return {"ContentLength": size}


def used(space):
    return Makerspace.objects.get(pk=space.pk).storage_bytes_used


def removals(space):
    return AuditLog.objects.filter(makerspace=space, action="machine.document_removed")


def setup(native, monkeypatch, settings):
    settings.STORAGE_CAPABILITIES_FILE = ""
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    w, url, body, _ = scenario(native, "machine", monkeypatch, settings)
    response = w.client.post(url, body, format="json")
    assert response_pair(response) == (201, None)
    document = MachineDocument.objects.get(pk=response.data["id"])
    kept_key = storage.machine_object_key(w.space.pk, "pdf")
    MachineDocument.objects.create(machine=w.machine, object_key=kept_key,
                                   doc_type="sop", original_filename="retained.pdf",
                                   content_type="application/pdf", size_bytes=23)
    limits.add_storage(w.space, 23)
    Makerspace.objects.filter(pk=w.other.pk).update(storage_bytes_used=41)
    provider = VersionedProvider({body["object_key"]: 10, kept_key: 23})
    monkeypatch.setattr(storage, "_client", lambda: provider)

    def before_delete():
        assert used(w.space) == 33
        assert MachineDocument.objects.filter(pk=document.pk).exists()
        assert removals(w.space).count() == 0

    provider.before_delete = before_delete
    return w, document, provider, reverse("admin-machine-document-detail", args=[document.pk])


def recompute(space, expected):
    output = StringIO()
    call_command("recompute_storage", str(space.pk), stdout=output)
    assert used(space) == expected
    assert f"{space.slug}: total={expected} bytes" in output.getvalue()


@pytest.mark.parametrize("native", [False, True], ids=["web", "native"])
def test_confirmed_deletion_releases_recorded_size_once_and_recompute_converges(native, monkeypatch, settings):
    w, document, provider, url = setup(native, monkeypatch, settings)
    stale = MachineDocument.objects.get(pk=document.pk)
    # Never trust the caller's possibly stale size or a provider's version total.
    document.size_bytes = 999
    services.remove_document(w.machine, w.actor, document)
    assert used(w.space) == 23
    assert used(w.other) == 41
    assert not MachineDocument.objects.filter(pk=document.pk).exists()
    assert provider.batches == [[{"Key": document.object_key, "VersionId": "current"},
                                 {"Key": document.object_key, "VersionId": "previous"}]]
    assert list(removals(w.space).values_list("meta", flat=True)) == [
        {"document_id": document.pk, "object_key": document.object_key}]
    services.remove_document(w.machine, w.actor, stale)
    assert (used(w.space), removals(w.space).count(), len(provider.batches)) == (23, 1, 1)
    with no_domain_writes():
        replay = w.client.delete(url)
    # Decisions 494/545 preserve native refusal when the deleted target no
    # longer resolves a tenant; browser lookup still returns not_found.
    assert response_pair(replay) == ((403, "permission_denied") if native else (404, "not_found"))
    recompute(w.space, 23)
    recompute(w.space, 23)
    assert used(w.other) == 41


@pytest.mark.parametrize("native", [False, True], ids=["web", "native"])
@pytest.mark.parametrize("failure", ["transport", "denied", "partial"])
def test_provider_failure_keeps_debt_and_retry_releases_exactly_once(native, failure, monkeypatch, settings):
    w, document, provider, url = setup(native, monkeypatch, settings)
    before = MachineDocument.objects.filter(pk=document.pk).values().get()
    provider.mode = failure
    refused = w.client.delete(url)
    assert response_pair(refused) == (503, "storage_unavailable")
    assert MachineDocument.objects.filter(pk=document.pk).values().get() == before
    assert (used(w.space), used(w.other), removals(w.space).count()) == (33, 41, 0)
    if failure == "partial":
        assert provider.versions[document.object_key] == {"previous": 10}
        assert storage.object_size(document.object_key) is None
    provider.mode = None
    recompute(w.space, 33)
    removed = w.client.delete(url)
    assert response_pair(removed) == (204, None)
    assert not MachineDocument.objects.filter(pk=document.pk).exists()
    assert provider.versions[document.object_key] == {}
    assert (used(w.space), used(w.other), removals(w.space).count()) == (23, 41, 1)
    batches = list(provider.batches)
    services.remove_document(w.machine, w.actor, document)
    with no_domain_writes():
        replay = w.client.delete(url)
    assert response_pair(replay) == ((403, "permission_denied") if native else (404, "not_found"))
    assert (used(w.space), removals(w.space).count(), provider.batches) == (23, 1, batches)
    recompute(w.space, 23)


@pytest.mark.parametrize("failure", [None, "transport", "denied", "partial"])
def test_storage_delete_has_explicit_outcome_without_raising_for_existing_callers(failure, monkeypatch, settings):
    settings.STORAGE_CAPABILITIES_FILE = ""
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    provider = VersionedProvider({"machines/1/manual.pdf": 10})
    provider.mode = failure
    monkeypatch.setattr(storage, "_client", lambda: provider)
    result = storage.delete_object("machines/1/manual.pdf")
    if failure is None:
        assert result is None
        assert provider.versions["machines/1/manual.pdf"] == {}
    else:
        assert result is False


@pytest.mark.parametrize("native", [False, True], ids=["web", "native"])
def test_disabled_machine_module_keeps_document_debt_and_restores_deletion(native, monkeypatch, settings):
    w, document, provider, url = setup(native, monkeypatch, settings)
    previous = toggle(w.space, "machines")
    with no_domain_writes():
        refused = w.client.delete(url)
    assert response_pair(refused) == (404, "module_disabled")
    assert MachineDocument.objects.filter(pk=document.pk).exists()
    assert (used(w.space), removals(w.space).count(), provider.batches) == (33, 0, [])
    toggle(w.space, "machines", previous)
    restored = w.client.delete(url)
    assert response_pair(restored) == (204, None)
    assert (used(w.space), removals(w.space).count()) == (23, 1)


@pytest.mark.parametrize("failure", [None, "transport"])
def test_finalize_cleanup_still_ignores_deletion_outcome(failure, monkeypatch, settings):
    settings.STORAGE_CAPABILITIES_FILE = ""
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    key = "machines/1/manual.pdf"
    provider = VersionedProvider({key: 10, storage.staging_key(key): 10})
    provider.mode = failure
    monkeypatch.setattr(storage, "_client", lambda: provider)
    assert storage.finalize_upload(key, 10) == 10
    assert provider.versions[storage.staging_key(key)] == (
        {} if failure is None else {"current": 10, "previous": 10})


@pytest.mark.parametrize("failure", [None, "transport"])
def test_type_document_failure_retains_charge_until_confirmed_retry(failure, monkeypatch, settings):
    from apps.machines import type_documents
    from apps.machines.models import MachineTypeDocument

    w, _document, provider, _url = setup(False, monkeypatch, settings)
    key = storage.machine_object_key(w.space.pk, "pdf")
    row = MachineTypeDocument.objects.create(makerspace=w.space, machine_type=w.machine_type,
                                            object_key=key, title="Type manual",
                                            original_filename="type.pdf", content_type="application/pdf",
                                            size_bytes=7)
    limits.add_storage(w.space, 7)
    provider.versions[key] = {"current": 7}
    provider.mode = failure
    def before_delete():
        assert used(w.space) == 40
        assert MachineTypeDocument.objects.filter(pk=row.pk).exists()
    provider.before_delete = before_delete
    url = reverse("machine-type-document-detail", args=[w.space.pk, w.machine_type.pk, row.pk])
    if failure:
        before = MachineTypeDocument.objects.filter(pk=row.pk).values().get()
        assert response_pair(w.client.delete(url)) == (503, "storage_unavailable")
        assert MachineTypeDocument.objects.filter(pk=row.pk).values().get() == before
        assert (used(w.space), used(w.other), provider.versions[key]) == (40, 41, {"current": 7})
        assert AuditLog.objects.filter(makerspace=w.space, action="machine_type_document.removed").count() == 0
        provider.mode = None
    assert response_pair(w.client.delete(url)) == (204, None)
    assert used(w.space) == 33
    assert not MachineTypeDocument.objects.filter(object_key=key).exists()
    assert AuditLog.objects.filter(makerspace=w.space, action="machine_type_document.removed").count() == 1
    assert provider.versions[key] == {}
    batches = list(provider.batches)
    type_documents.remove(w.actor, row)
    assert response_pair(w.client.delete(url)) == (404, "not_found")
    assert (used(w.space), used(w.other), provider.batches) == (33, 41, batches)
    assert AuditLog.objects.filter(makerspace=w.space, action="machine_type_document.removed").count() == 1


def test_audit_rollback_keeps_charge_and_absent_object_retry_releases_once(monkeypatch, settings):
    w, document, provider, url = setup(False, monkeypatch, settings)
    original_audit = services._audit

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit write unavailable")

    monkeypatch.setattr(services, "_audit", fail_audit)
    with pytest.raises(RuntimeError, match="audit write unavailable"):
        services.remove_document(w.machine, w.actor, document)
    assert (used(w.space), removals(w.space).count()) == (33, 0)
    assert MachineDocument.objects.filter(pk=document.pk).exists()
    assert provider.versions[document.object_key] == {}
    recompute(w.space, 33)
    monkeypatch.setattr(services, "_audit", original_audit)
    retry = w.client.delete(url)
    assert response_pair(retry) == (204, None)
    assert (used(w.space), removals(w.space).count(), len(provider.batches)) == (23, 1, 1)
    recompute(w.space, 23)


@pytest.mark.django_db(transaction=True)
def test_two_stale_document_deletions_release_one_charge(monkeypatch, settings):
    from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
    from threading import Barrier
    from django.db import close_old_connections, connection, connections

    w, document, provider, _url = setup(False, monkeypatch, settings)
    gate = Barrier(2)

    def worker():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '5s'")
                cursor.execute("SELECT pg_backend_pid()")
                backend_id = cursor.fetchone()[0]
            stale = MachineDocument.objects.get(pk=document.pk)
            gate.wait(timeout=10)
            services.remove_document(w.machine, w.actor, stale)
            return backend_id
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        backends = [future.result(timeout=40) for future in futures]
    assert len(set(backends)) == 2
    assert (used(w.space), used(w.other), removals(w.space).count(), len(provider.batches)) == (23, 41, 1, 1)
    assert not MachineDocument.objects.filter(pk=document.pk).exists()
    recompute(w.space, 23)
