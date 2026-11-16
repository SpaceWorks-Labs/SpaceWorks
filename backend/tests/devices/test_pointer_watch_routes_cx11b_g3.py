"""Shelf calibration and staff watch commands persist exact effects (312/321, 520)."""
import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401

from apps.devices.models import AdapterCommand, AdapterPose, AdapterWatch
from tests.devices.route_world_cx11b_g3 import BASE_KEYS, event, pose, watch, world
from tests.maintenance.route_support_cx11b_g3 import foreign_refusal, prove, send

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_devices, pytest.mark.area_machines]
OPS = ("poses", "pose_set", "pose_delete", "aim", "jog", "indicate", "position", "watch", "end", "snapshot")
CASES = [(op, key, native) for op in OPS for key in
         (*BASE_KEYS, *(["machines.integrations.video"] if op in {"watch", "end", "snapshot"} else []))
         for native in (False, True)]


@pytest.mark.parametrize("op,key,native", CASES)
def test_pointer_or_watch_effect_standing_and_switch(op, key, native):
    pointer = op not in {"watch", "end", "snapshot"}
    w = world(native, pointer=pointer)
    args, method, body, status, audit = [w.binding.pk], "get", {}, 200, None
    if pointer:
        saved = pose(w)
        name = "admin-adapter-poses"
        if op == "pose_set":
            method, audit = "put", "devices.adapter_pose_saved"
            body = {"target_type": "item", "target_id": str(w.product.pk), "pose": {"pan": 25}, "note": "New pose"}
        elif op == "pose_delete":
            method, status, audit = "delete", 204, "devices.adapter_pose_cleared"
            body = {"target_type": "item", "target_id": str(w.product.pk)}
        elif op in {"aim", "jog", "indicate"}:
            name, method, status, audit = "admin-adapter-" + op, "post", 201, "devices.adapter_command_queued"
            body = {"aim": {"pose": {"pan": 9}}, "jog": {"dx": 1.5, "dy": -2},
                    "indicate": {"target_type": "item", "target_id": str(w.product.pk)}}[op]
        elif op == "position":
            event(w, "calibration.position", {"pose": {"pan": 38}})
            name = "admin-adapter-position"
    elif op == "watch":
        name, method, status, audit = "admin-adapter-watch-create", "post", 201, "devices.adapter_watch_started"
        body = {"reason": "Retained inspection", "record": False}
    else:
        saved = watch(w)
        name, args = "admin-adapter-watch-" + ("detail" if op == "end" else "snapshot"), [saved.pk]
        method, status, audit = ("delete", 200, "devices.adapter_watch_ended") if op == "end" else (
            "post", 201, "devices.adapter_command_queued")

    def check(response):
        data = response.data
        if op == "poses":
            assert [(r["id"], r["target_id"], r["pose"]) for r in data] == [
                (str(saved.pk), str(w.product.pk), {"pan": 12, "tilt": 3})]
        elif op == "pose_set":
            saved.refresh_from_db()
            assert (saved.pose, saved.note, saved.saved_by_id) == ({"pan": 25}, "New pose", w.actor.pk)
            assert AdapterPose.objects.filter(binding=w.binding).count() == 1
        elif op == "pose_delete":
            assert not AdapterPose.objects.filter(pk=saved.pk).exists()
        elif op == "position":
            assert data == {"pose": {"pan": 38}}
        elif op == "watch":
            row = AdapterWatch.objects.get(pk=data["id"])
            assert (row.viewer_id, row.binding_id, row.status, row.record) == (w.actor.pk, w.binding.pk, "active", False)
            assert AdapterWatch.objects.filter(binding=w.binding).count() == 1
        elif op == "end":
            saved.refresh_from_db()
            assert saved.status == "ended" and saved.ended_at is not None
        else:
            row = AdapterCommand.objects.get(pk=data["id"])
            params = {"aim": {"pose": {"pan": 9}}, "jog": {"dx": 1.5, "dy": -2},
                      "indicate": {"mode": "point", "pose": {"pan": 12, "tilt": 3}, "duration_seconds": 10},
                      "snapshot": {"watch_id": str(saved.pk)}}[op]
            assert (row.binding_id, row.command, row.params, row.status) == (
                w.binding.pk, "snapshot" if op == "snapshot" else op, params, "queued")
            assert row.capability == ({"aim": "locate.calibrate", "jog": "locate.calibrate",
                "indicate": "locate.indicate", "snapshot": "media.snapshot"}[op])
            assert AdapterCommand.objects.filter(binding=w.binding).count() == 1

    prove(w.space, w.objects, key, lambda c: send(c or w.client, "devices:" + name, args, method, body), check,
          status=status, outsiders=[(w.foreign, foreign_refusal(native))], audits={audit: 1} if audit else {})


WATCH_BRANCHES = [("record", "machines.integrations.recording"), ("audio", "machines.integrations.audio"),
                  ("talk", "machines.integrations.talk"), ("audio_record", "machines.integrations.audio_recording")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("branch,key", WATCH_BRANCHES)
def test_watch_opt_in_child_switches_are_independent(branch, key, native):
    w = world(native)
    record, audio, talk = branch in {"record", "audio_record"}, branch in {"audio", "talk", "audio_record"}, branch == "talk"
    body = {"reason": "Audio inspection", "record": record, "audio": audio, "talk": talk, "notice_ack": True}

    def check(response):
        row = AdapterWatch.objects.get(pk=response.data["id"])
        assert (row.record, row.audio, row.talk, row.audio_notice_ack) == (record, audio, talk, True)
        assert AdapterWatch.objects.filter(binding=w.binding).count() == 1

    audits = {"devices.adapter_watch_started": 1}
    if record:
        audits["devices.adapter_watch_recording_requested"] = 1
    if audio:
        audits["devices.adapter_audio_started"] = 1
    prove(w.space, w.objects, key,
          lambda c: send(c or w.client, "devices:admin-adapter-watch-create", [w.binding.pk], "post", body), check,
          status=201, outsiders=[(w.foreign, foreign_refusal(native))], audits=audits)

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
