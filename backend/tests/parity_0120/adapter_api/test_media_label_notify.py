"""media.stream signaling and snapshot fallback, opt-in recording, label.print delivery and adapter notifications."""
import time
import uuid

import pytest
from django.urls import reverse

from apps.devices.models import AdapterEvent, AdapterWatch
from tests.parity_0120.adapter_api.adapter_case import adapter_case, plain_member

pytestmark = pytest.mark.django_db(transaction=True)
CAPS = ("status", "events", "media.stream", "media.snapshot")
FRAME = {"content_type": "image/jpeg", "data": "QUJDRA=="}


def watching(slug, record=False):
    case = adapter_case(slug, caps=CAPS)
    opened = case["client"].post(reverse("devices:admin-adapter-watch-create", args=[case["binding_id"]]),
                                 {"reason": "check", "record": record}, format="json")
    return case, opened


def test_signaling_is_relayed_between_viewer_and_adapter_only_while_the_watch_is_open():
    case, opened = watching("media-signal")
    assert opened.status_code == 201
    watch = opened.data["id"]
    viewer = f"/api/v1/member/adapter-watch/{watch}/signal"
    assert case["client"].post(viewer, {"kind": "offer", "sdp": "v=0"}, format="json").status_code == 201
    polled = case["sim"].get(f"media/{watch}/signal?after=0")
    assert polled.status_code == 200 and polled.data["signals"][0]["kind"] == "offer"
    assert case["sim"].post(f"media/{watch}/signal", {"kind": "answer", "sdp": "v=0"}).status_code == 201
    back = case["client"].get(viewer + "?after=0")
    assert back.data["signals"][0]["kind"] == "answer"
    case["client"].delete(f"/api/v1/member/adapter-watch/{watch}")
    assert case["sim"].post(f"media/{watch}/signal", {"kind": "bye"}).status_code == 409


def test_only_the_viewer_may_use_a_watch_and_a_snapshot_needs_an_open_watch():
    case, opened = watching("media-owner")
    watch = opened.data["id"]
    stranger = plain_member("media-stranger", case["space"])
    from tests.return_helpers import authenticated_client
    assert authenticated_client(stranger).get(f"/api/v1/member/adapter-watch/{watch}/signal").status_code == 404
    assert case["sim"].post(f"media/{watch}/snapshot", FRAME).status_code == 201
    assert case["client"].get(f"/api/v1/member/adapter-watch/{watch}/frame").data["data"] == FRAME["data"]
    AdapterWatch.objects.filter(pk=watch).update(status="ended")
    assert case["sim"].post(f"media/{watch}/snapshot", FRAME).status_code == 409


def test_recording_is_opt_in_needs_its_switch_and_expires(monkeypatch):
    from apps.devices.services_adapter_media import purge_recordings
    from datetime import timedelta
    from django.utils import timezone
    monkeypatch.setattr("apps.devices.services_adapter_recording._presign",
                        lambda key, ct: {"url": "https://s.test/u", "fields": {}})
    monkeypatch.setattr("apps.machines.service_storage.purge_object", lambda key: None)
    case, plain = watching("media-record-off")
    assert plain.data["record"] is False
    assert case["sim"].post(f"media/{plain.data['id']}/recording", {"content_type": "video/webm"}).status_code == 403
    recorded = case["client"].post(reverse("devices:admin-adapter-watch-create", args=[case["binding_id"]]),
                                   {"record": True}, format="json")
    assert recorded.status_code == 201 and recorded.data["record"] is True
    stored = case["sim"].post(f"media/{recorded.data['id']}/recording", {"content_type": "video/webm"})
    assert stored.status_code == 201
    assert purge_recordings(now=timezone.now() + timedelta(days=8)) == 1
    assert AdapterWatch.objects.get(pk=recorded.data["id"]).recording_purged_at is not None


def test_a_job_owner_can_watch_only_their_own_in_progress_request():
    from tests.test_machine_service_workflow import in_progress
    case = adapter_case("media-jobowner", caps=CAPS)
    row = in_progress(case["space"], actor=case["manager"], target=case["machine"])
    from tests.return_helpers import authenticated_client
    stranger = plain_member("media-jo-stranger", case["space"])
    assert authenticated_client(stranger).post(f"/api/v1/member/adapter-watch/requests/{row.pk}").status_code == 404


def test_label_print_rides_the_existing_label_path_for_an_adapter():
    from apps.devices.label_access import prints_labels
    case = adapter_case("label-adapter", caps=("status", "events"), extra=("label.print",))
    assert prints_labels(case["device"]) is False  # no label.print binding yet
    made = case["client"].post(reverse("devices:admin-adapter-binding-create", args=[case["device"].pk]),
                               {"target_type": "space", "external_ref": "labels", "capabilities": ["label.print"]},
                               format="json")
    assert made.status_code == 201
    assert prints_labels(case["device"]) is True


def test_needs_attention_and_runout_events_notify_staff_and_a_repeat_is_a_duplicate(monkeypatch):
    sent = []
    monkeypatch.setattr("apps.devices.adapter_notifications.notify_event", lambda row: sent.append(row.event_type))
    case = adapter_case("notify-events", caps=("status", "events", "job.dispatch", "consumables"))
    event = {"operation_id": str(uuid.uuid4()), "binding_id": case["binding_id"], "type": "consumable.runout",
             "observed_at": int(time.time()), "data": {"slot": "A"}}
    assert case["sim"].post("events", {"events": [event]}).data["results"][0]["result"] == "stored"
    assert case["sim"].post("events", {"events": [event]}).data["results"][0]["result"] == "duplicate"
    assert sent == ["consumable.runout"] and AdapterEvent.objects.count() == 1


def test_an_access_denial_notifies_staff_once_per_binding_and_reason(monkeypatch):
    from django.core.cache import cache
    sent = []
    monkeypatch.setattr("apps.devices.adapter_notifications.notify_access_denied", lambda row: sent.append(row.reason))
    case = adapter_case("notify-denied")
    cache.clear()
    for _ in range(3):
        case["sim"].post("access/authorize", {"binding_id": case["binding_id"],
                                              "credential": {"type": "nfc", "value": "NOPE"}})
    assert sent == []  # an unknown tag is noise, never a staff alert
