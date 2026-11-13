"""Decision 321 a-c: audio and talk, artifacts, detections. Written, not run (no Docker in this lane)."""
import time
import uuid
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.devices.models import AdapterArtifact, AdapterEvent, AdapterWatch
from tests.parity_0120.adapter_api.adapter_case import CHILDREN, adapter_case, plain_member
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db(transaction=True)
STREAM = ("status", "events", "media.stream", "media.audio", "media.talk")
ARTIFACT = ("status", "events", "artifact.upload", "detection.report")
ON = ("machines.integrations", *CHILDREN)


def _watch(case, **body):
    return case["client"].post(reverse("devices:admin-adapter-watch-create", args=[case["binding_id"]]),
                               {"reason": "check", **body}, format="json")


@pytest.fixture(autouse=True)
def _storage(monkeypatch):
    cache.clear()
    monkeypatch.setattr("apps.machines.service_storage.presigned_upload",
                        lambda key, ct, max_bytes: {"url": "https://s.test/u", "method": "PUT"})
    monkeypatch.setattr("apps.machines.service_storage.finalize_upload", lambda key, max_bytes: 2048)
    monkeypatch.setattr("apps.machines.service_storage.cleanup_upload", lambda key: None)
    monkeypatch.setattr("apps.machines.service_storage.purge_upload", lambda key: None)
    monkeypatch.setattr("apps.evidence.storage.presigned_get_url", lambda key: "https://s.test/get")
    monkeypatch.setattr("apps.machines.service_storage.presigned_download_url", lambda key, ct: "https://s.test/get")


# --- a) audio and talk ------------------------------------------------------------------------------------------
def test_audio_is_receive_only_by_default_and_needs_its_switch():
    off = adapter_case("audio-off", caps=STREAM, features=tuple(f for f in ON if not f.endswith(".audio")))
    assert _watch(off, audio=True).status_code == 404
    case = adapter_case("audio-on", caps=STREAM)
    plain = _watch(case)
    assert plain.status_code == 201 and plain.data["audio"] is False and plain.data["talk"] is False
    heard = _watch(case, audio=True)
    assert heard.status_code == 201 and heard.data["audio"] is True and heard.data["talk"] is False
    polled = case["sim"].get(f"media/{heard.data['id']}/signal?after=0")
    assert polled.data["audio"] is True and polled.data["announce_audio"] is True  # the notice at the device


def test_recording_audio_needs_the_notice_acknowledged_and_its_switch():
    case = adapter_case("audio-record", caps=STREAM)
    refused = _watch(case, audio=True, record=True)
    assert refused.status_code == 409 and refused.data["code"] == "audio_notice_required"
    ok = _watch(case, audio=True, record=True, notice_ack=True)
    assert ok.status_code == 201 and AdapterWatch.objects.get(pk=ok.data["id"]).audio_notice_ack is True
    off = adapter_case("audio-record-off", caps=STREAM,
                       features=tuple(f for f in ON if not f.endswith("audio_recording")))
    assert _watch(off, audio=True, record=True, notice_ack=True).status_code == 404


def test_talk_is_staff_only_push_to_talk_and_every_press_is_audited():
    case = adapter_case("talk", caps=STREAM)
    opened = _watch(case, talk=True)
    assert opened.status_code == 201 and opened.data["talk"] is True and opened.data["audio"] is True
    watch = opened.data["id"]
    talk = f"/api/v1/member/adapter-watch/{watch}/talk"
    assert case["client"].post(talk, {"active": True}, format="json").status_code == 201
    assert case["client"].post(talk, {"active": False}, format="json").status_code == 201
    kinds = [row["kind"] for row in case["sim"].get(f"media/{watch}/signal?after=0").data["signals"]]
    assert kinds == ["ptt_on", "ptt_off"]
    assert AuditLog.objects.filter(action="devices.adapter_talk_started").count() == 1
    assert AuditLog.objects.filter(action="devices.adapter_talk_stopped").count() == 1
    # PTT never rides the generic signal route, from either side.
    assert case["client"].post(f"/api/v1/member/adapter-watch/{watch}/signal", {"kind": "ptt_on"},
                               format="json").status_code == 400
    assert case["sim"].post(f"media/{watch}/signal", {"kind": "ptt_on"}).status_code == 400


def test_a_watch_without_talk_and_a_stranger_cannot_use_the_talk_route():
    case = adapter_case("talk-denied", caps=STREAM)
    listen = _watch(case, audio=True)
    talk = f"/api/v1/member/adapter-watch/{listen.data['id']}/talk"
    assert case["client"].post(talk, {"active": True}, format="json").status_code == 403
    opened = _watch(case, talk=True)
    stranger = authenticated_client(plain_member("talk-stranger", case["space"]))
    assert stranger.post(f"/api/v1/member/adapter-watch/{opened.data['id']}/talk", {"active": True},
                         format="json").status_code == 404
    off = adapter_case("talk-off", caps=STREAM, features=tuple(f for f in ON if not f.endswith(".talk")))
    assert _watch(off, talk=True).status_code == 404


# --- b) artifacts -----------------------------------------------------------------------------------------------
def _artifact(case, kind="thumbnail", content_type="image/jpeg", size=2048, **links):
    return case["sim"].post("artifacts", {"operation_id": str(uuid.uuid4()), "binding_id": case["binding_id"],
                                          "kind": kind, "content_type": content_type, "size_bytes": size, **links})


def test_artifact_routes_are_404_while_their_switch_is_off():
    case = adapter_case("art-off", caps=ARTIFACT, features=tuple(f for f in ON if not f.endswith("artifacts")))
    assert _artifact(case).status_code == 404
    assert case["client"].get(reverse("devices:admin-adapter-artifacts", args=[case["binding_id"]])).status_code == 404


def test_an_artifact_uploads_to_staging_completes_once_and_staff_can_read_it():
    case = adapter_case("art-flow", caps=ARTIFACT)
    made = _artifact(case)
    assert made.status_code == 201 and made.data["upload"]["url"].startswith("https://")
    assert "object_key" in made.data
    done = case["sim"].post(f"artifacts/{made.data['artifact_id']}/complete")
    assert done.status_code == 200 and done.data["status"] == "ready"
    assert case["sim"].post(f"artifacts/{made.data['artifact_id']}/complete").data["status"] == "ready"
    listed = case["client"].get(reverse("devices:admin-adapter-artifacts", args=[case["binding_id"]]))
    assert listed.status_code == 200 and listed.data["count"] == 1
    assert "object_key" not in listed.data["results"][0]
    url = case["client"].get(reverse("devices:admin-adapter-artifact-url", args=[made.data["artifact_id"]]))
    assert url.data["url"] == "https://s.test/get"


def test_artifact_kind_rules_size_content_type_and_idempotency():
    case = adapter_case("art-rules", caps=ARTIFACT)
    assert _artifact(case, size=6 * 2 ** 20).status_code == 413  # thumbnail cap is 5 MB
    assert _artifact(case, kind="timelapse", content_type="image/jpeg").status_code == 400
    body = {"operation_id": str(uuid.uuid4()), "binding_id": case["binding_id"], "kind": "thumbnail",
            "content_type": "image/png", "size_bytes": 10}
    first = case["sim"].post("artifacts", body)
    second = case["sim"].post("artifacts", body)
    assert first.status_code == 201 and second.data["duplicate"] is True
    assert AdapterArtifact.objects.count() == 1
    # Audio is only recorded during a watch that asked for it and acknowledged the notice.
    assert _artifact(case, kind="audio_recording", content_type="audio/ogg").status_code == 409


def test_the_artifact_quota_refuses_only_a_new_artifact():
    case = adapter_case("art-quota", caps=ARTIFACT)
    case["space"].resource_limit_overrides = {"adapter_artifacts": 1}
    case["space"].save(update_fields=["resource_limit_overrides"])
    assert _artifact(case).status_code == 201
    refused = _artifact(case)
    assert refused.status_code == 409 and refused.data["code"] == "adapter_artifacts_quota_reached"


def test_the_job_owner_sees_their_own_job_artifacts_and_nobody_else_does():
    from tests.test_machine_service_workflow import in_progress
    case = adapter_case("art-owner", caps=ARTIFACT)
    row = in_progress(case["space"], actor=case["manager"], target=case["machine"])
    made = _artifact(case, service_request_id=row.pk)
    case["sim"].post(f"artifacts/{made.data['artifact_id']}/complete")
    owner = authenticated_client(row.member or row.requester)
    mine = owner.get(f"/api/v1/member/adapter-artifacts/requests/{row.pk}")
    assert mine.status_code == 200 and mine.data["count"] == 1
    assert owner.get(f"/api/v1/member/adapter-artifacts/{made.data['artifact_id']}/url").status_code == 200
    stranger = authenticated_client(plain_member("art-stranger", case["space"]))
    assert stranger.get(f"/api/v1/member/adapter-artifacts/requests/{row.pk}").status_code == 404
    assert stranger.get(f"/api/v1/member/adapter-artifacts/{made.data['artifact_id']}/url").status_code == 404


def test_expired_artifacts_are_deleted_and_marked_purged():
    from apps.devices.services_adapter_artifacts import purge_expired
    case = adapter_case("art-purge", caps=ARTIFACT)
    made = _artifact(case)
    case["sim"].post(f"artifacts/{made.data['artifact_id']}/complete")
    AdapterArtifact.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
    assert purge_expired() == 1
    row = AdapterArtifact.objects.get()
    assert row.status == "purged" and row.purged_at is not None
    assert purge_expired() == 0  # idempotent
    listed = case["client"].get(reverse("devices:admin-adapter-artifacts", args=[case["binding_id"]]))
    assert listed.data["results"][0]["status"] == "purged"


# --- c) detections ----------------------------------------------------------------------------------------------
def _detect(case, kind="failure", confidence=0.9, **extra):
    event = {"operation_id": str(uuid.uuid4()), "binding_id": case["binding_id"], "type": "detection.reported",
             "observed_at": int(time.time()), "data": {"kind": kind, "confidence": confidence, **extra}}
    return case["sim"].post("events", {"events": [event]})


def test_a_detection_is_stored_notifies_and_never_acts(monkeypatch):
    sent = []
    monkeypatch.setattr("apps.devices.adapter_notifications.notify_event", lambda row: sent.append(row.event_type))
    case = adapter_case("detect", caps=ARTIFACT)
    before = (case["machine"].status, case["machine"].pk)
    assert _detect(case, "spaghetti", 0.97).data["results"][0]["result"] == "stored"
    case["machine"].refresh_from_db()
    assert (case["machine"].status, case["machine"].pk) == before  # core never pauses, powers off or cancels
    assert sent == ["detection.reported"]
    from apps.devices.models import AdapterCommand
    assert not AdapterCommand.objects.exists()
    listed = case["client"].get(reverse("devices:admin-adapter-detections", args=[case["binding_id"]]))
    assert listed.data["count"] == 1 and listed.data["results"][0]["kind"] == "spaghetti"


def test_detections_validate_their_kind_confidence_and_evidence_frame():
    case = adapter_case("detect-bad", caps=ARTIFACT)
    assert _detect(case, "alien", 0.5).status_code == 400
    assert _detect(case, "fire", 1.2).status_code == 400
    other = _detect(case, "smoke", 0.5, artifact_id=str(uuid.uuid4()))
    assert other.status_code == 400 and other.data["code"] == "invalid_artifact"
    made = _artifact(case, kind="failure_snapshot")
    assert _detect(case, "smoke", 0.5, artifact_id=made.data["artifact_id"]).status_code == 200


def test_detections_are_rate_limited_and_404_when_the_switch_is_off():
    from apps.devices.services_adapter_detect import RATE_LIMIT
    case = adapter_case("detect-rate", caps=ARTIFACT)
    for _ in range(RATE_LIMIT):
        assert _detect(case).status_code == 200
    refused = _detect(case)
    assert refused.status_code == 429 and refused.data["code"] == "rate_limited"
    assert AdapterEvent.objects.filter(event_type="detection.reported").count() == RATE_LIMIT
    off = adapter_case("detect-off", caps=ARTIFACT, features=tuple(f for f in ON if not f.endswith("detections")))
    assert _detect(off).status_code == 404


def test_the_job_owner_sees_detections_on_their_machine_without_the_note():
    from tests.test_machine_service_workflow import in_progress
    case = adapter_case("detect-owner", caps=ARTIFACT)
    row = in_progress(case["space"], actor=case["manager"], target=case["machine"])
    _detect(case, "failure", 0.8, note="staff only wording")
    owner = authenticated_client(row.member or row.requester)
    seen = owner.get(f"/api/v1/member/adapter-detections/requests/{row.pk}")
    assert seen.status_code == 200 and seen.data["count"] == 1 and "note" not in seen.data["results"][0]
    stranger = authenticated_client(plain_member("detect-stranger", case["space"]))
    assert stranger.get(f"/api/v1/member/adapter-detections/requests/{row.pk}").status_code == 404
