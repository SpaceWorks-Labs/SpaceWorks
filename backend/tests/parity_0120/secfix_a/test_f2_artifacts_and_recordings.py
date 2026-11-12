"""SECFIX-A F2: artifact job links (L-A2), signed downloads (#21), confirmed purges (lead 6 / M3 / L-A5), recording
content types and size cap, and the devices module purge collecting every object key."""
import uuid
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.devices.models import AdapterArtifact, AdapterWatch
from apps.devices.services_adapter_recording import _presign as REAL_PRESIGN
from apps.evidence.storage import StorageUnavailable
from tests.parity_0120.adapter_api.adapter_case import adapter_case
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db(transaction=True)
ARTIFACT = ("status", "events", "artifact.upload", "detection.report")
STREAM = ("status", "events", "media.stream", "media.snapshot")


@pytest.fixture(autouse=True)
def _storage(monkeypatch):
    from django.core.cache import cache
    cache.clear()
    signed = []
    monkeypatch.setattr("apps.machines.service_storage.presigned_upload",
                        lambda key, ct, max_bytes: {"url": "https://s.test/u", "method": "PUT"})
    monkeypatch.setattr("apps.machines.service_storage.finalize_upload", lambda key, max_bytes: 2048)
    monkeypatch.setattr("apps.machines.service_storage.presigned_download_url",
                        lambda key, ct: signed.append((key, ct)) or "https://s.test/get")
    monkeypatch.setattr("apps.devices.services_adapter_recording._presign",
                        lambda key, ct: {"url": "https://s.test/rec", "fields": {}})
    return signed


def _artifact(case, **links):
    return case["sim"].post("artifacts", {"operation_id": str(uuid.uuid4()), "binding_id": case["binding_id"],
                                          "kind": "thumbnail", "content_type": "image/png", "size_bytes": 64, **links})


def _job(case, machine=None):
    from tests.test_machine_service_workflow import in_progress
    return in_progress(case["space"], actor=case["manager"], target=machine or case["machine"])


# --- L-A2 -------------------------------------------------------------------------------------------------------
def test_an_adapter_cannot_attach_an_artifact_to_another_machines_job():
    from tests.test_machine_service_workflow import machine
    case = adapter_case("f2-art-link", caps=ARTIFACT)
    other_job = _job(case, machine(case["space"], name="Other machine"))
    refused = _artifact(case, service_request_id=other_job.pk)
    assert refused.status_code == 404 and refused.data["code"] == "invalid_link"
    assert not AdapterArtifact.objects.filter(service_request_id=other_job.pk).exists()
    own = _job(case)
    assert _artifact(case, service_request_id=own.pk).status_code == 201


def test_a_pre_existing_cross_machine_link_is_not_served_to_the_owner(_storage):
    from tests.test_machine_service_workflow import machine
    case = adapter_case("f2-art-legacy", caps=ARTIFACT)
    own = _job(case)
    made = _artifact(case, service_request_id=own.pk)
    case["sim"].post(f"artifacts/{made.data['artifact_id']}/complete")
    owner = authenticated_client(own.member or own.requester)
    url = owner.get(f"/api/v1/member/adapter-artifacts/{made.data['artifact_id']}/url")
    assert url.status_code == 200 and _storage == [(AdapterArtifact.objects.get().object_key, "image/png")]
    # A link written before the fix: the artifact names a job that runs on another machine.
    other_job = _job(case, machine(case["space"], name="Elsewhere"))
    AdapterArtifact.objects.update(service_request_id=other_job.pk)
    victim = authenticated_client(other_job.member or other_job.requester)
    assert victim.get(f"/api/v1/member/adapter-artifacts/requests/{other_job.pk}").data["count"] == 0
    assert victim.get(f"/api/v1/member/adapter-artifacts/{made.data['artifact_id']}/url").status_code == 404


def test_staff_artifact_links_are_signed_downloads_with_the_stored_type(_storage):
    case = adapter_case("f2-art-staff", caps=ARTIFACT)
    made = _artifact(case)
    case["sim"].post(f"artifacts/{made.data['artifact_id']}/complete")
    url = case["client"].get(reverse("devices:admin-adapter-artifact-url", args=[made.data["artifact_id"]]))
    assert url.status_code == 200 and _storage[-1][1] == "image/png"


# --- L-A5: an artifact is marked purged only after storage confirmed the delete ----------------------------------
def test_an_artifact_is_not_marked_purged_when_its_delete_fails(monkeypatch):
    from apps.devices.services_adapter_artifacts import purge_expired
    case = adapter_case("f2-art-purge", caps=ARTIFACT)
    made = _artifact(case)
    case["sim"].post(f"artifacts/{made.data['artifact_id']}/complete")
    AdapterArtifact.objects.update(expires_at=timezone.now() - timedelta(minutes=1))

    def broken(key):
        raise StorageUnavailable()
    monkeypatch.setattr("apps.machines.service_storage.purge_upload", broken)
    assert purge_expired() == 0
    assert AdapterArtifact.objects.get().status == "ready"  # the attack: it used to read "purged" over live bytes
    assert not AuditLog.objects.filter(action="devices.adapter_artifact_purged").exists()
    deleted = []
    monkeypatch.setattr("apps.machines.service_storage.purge_upload", deleted.append)
    assert purge_expired() == 1 and AdapterArtifact.objects.get().status == "purged"
    assert deleted == [AdapterArtifact.objects.get().object_key]


# --- lead 6 / M3: recordings ------------------------------------------------------------------------------------
def _recording_watch(slug):
    case = adapter_case(slug, caps=STREAM)
    opened = case["client"].post(reverse("devices:admin-adapter-watch-create", args=[case["binding_id"]]),
                                 {"reason": "check", "record": True}, format="json")
    assert opened.status_code == 201, opened.data
    return case, opened.data["id"]


def test_only_webm_and_mp4_recordings_are_accepted():
    case, watch = _recording_watch("f2-rec-types")
    for bad in ("text/html", "video/quicktime", "video/x-msvideo"):
        refused = case["sim"].post(f"media/{watch}/recording", {"content_type": bad})
        assert refused.status_code == 400 and refused.data["code"] == "content_type_not_allowed", bad
    ok = case["sim"].post(f"media/{watch}/recording", {"content_type": "video/mp4", "size_bytes": 1024})
    assert ok.status_code == 201 and ok.data["object_key"].startswith("adapter-recordings/")


def test_the_recording_presign_signs_the_staging_key_with_the_recording_cap(monkeypatch):
    from apps.devices import services_adapter_recording as recording
    seen = {}
    monkeypatch.setattr("apps.evidence.storage._public_client", lambda: object())
    monkeypatch.setattr("apps.evidence.storage._client", lambda: object())
    monkeypatch.setattr("apps.storage_capabilities.presigning.presign_upload",
                        lambda signing, **kwargs: seen.update(kwargs) or {"url": "https://s.test/rec"})
    REAL_PRESIGN("adapter-recordings/1/w", "video/webm")  # the autouse fixture stubs the module attribute
    assert seen["key"] == "staging/adapter-recordings/1/w" and seen["max_bytes"] == recording.RECORDING_MAX_BYTES
    assert seen["content_type"] == "video/webm"


def test_a_recording_is_marked_purged_only_after_both_keys_are_confirmed_gone(monkeypatch):
    from apps.devices.services_adapter_media import purge_recordings
    case, watch = _recording_watch("f2-rec-purge")
    assert case["sim"].post(f"media/{watch}/recording", {"content_type": "video/webm"}).status_code == 201

    def broken(key):
        raise StorageUnavailable()
    monkeypatch.setattr("apps.machines.service_storage.purge_object", broken)
    later = timezone.now() + timedelta(days=8)
    assert purge_recordings(now=later) == 0
    assert AdapterWatch.objects.get(pk=watch).recording_purged_at is None  # left due for the next sweep
    assert not AuditLog.objects.filter(action="devices.adapter_watch_recording_purged").exists()
    deleted = []
    monkeypatch.setattr("apps.machines.service_storage.purge_object", deleted.append)
    assert purge_recordings(now=later) == 1
    row = AdapterWatch.objects.get(pk=watch)
    assert row.recording_purged_at is not None
    assert set(deleted) == {row.recording_key, f"staging/{row.recording_key}"}


# --- M3: module purge collects every artifact and recording object ----------------------------------------------
def test_the_devices_module_purge_collects_both_keys_of_every_artifact_and_recording():
    from apps.makerspaces.module_purge_collectors_devices import devices_private_keys
    from apps.makerspaces.module_purge_plans import PLANS
    case, watch = _recording_watch("f2-purge-keys")
    case["sim"].post(f"media/{watch}/recording", {"content_type": "video/webm"})
    other = adapter_case("f2-purge-keys-other", caps=STREAM)
    other_watch = other["client"].post(reverse("devices:admin-adapter-watch-create", args=[other["binding_id"]]),
                                       {"reason": "x", "record": True}, format="json").data["id"]
    other["sim"].post(f"media/{other_watch}/recording", {"content_type": "video/webm"})
    keys = []
    devices_private_keys(case["space"], keys.append)
    recording_key = AdapterWatch.objects.get(pk=watch).recording_key
    assert recording_key in keys and f"staging/{recording_key}" in keys
    assert AdapterWatch.objects.get(pk=other_watch).recording_key not in keys  # never another space's objects
    plan = next(plan for plan in PLANS if plan.key == "devices")
    assert plan.private_keys is devices_private_keys
