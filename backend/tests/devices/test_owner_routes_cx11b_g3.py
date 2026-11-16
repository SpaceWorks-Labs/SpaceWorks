"""Job owner/watch viewer routes: same-space non-owner and foreign actor are 404 (520)."""
import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.core.cache import cache

from apps.devices.models import AdapterWatch
from tests.devices.route_world_cx11b_g3 import BASE_KEYS, artifact, event, watch, world
from tests.maintenance.route_support_cx11b_g3 import foreign_refusal, prove, send

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_devices, pytest.mark.area_machines]
OPS = {"start": "video", "end": "video", "poll": "video", "signal": "video", "frame": "video",
       "talk": "talk", "artifacts": "artifacts", "artifact_url": "artifacts", "detections": "detections"}
CASES = [(op, key, native) for op, child in OPS.items() for key in
         (*BASE_KEYS, "machines.integrations." + child, *(["machines.integrations.video"] if op == "talk" else []))
         for native in (False, True)]


@pytest.mark.parametrize("op,key,native", CASES)
def test_owner_route_effect_standing_and_switch(op, key, native, monkeypatch):
    w = world(native)
    url = "https://storage.example.test/owner-retained"
    monkeypatch.setattr("apps.machines.service_storage.presigned_download_url", lambda *a: url)
    method, body, status, audits = "get", {}, 200, {}
    if op == "start":
        name, args, method, status = "member-adapter-watch-start", [w.job.pk], "post", 201
        audits = {"devices.adapter_watch_started": 1, "devices.adapter_watch_viewed": 1}
    elif op in {"end", "poll", "signal", "frame", "talk"}:
        row = watch(w, owner=op != "talk")
        args = [row.pk]
        names = {"end": "end", "poll": "signal", "signal": "signal", "frame": "frame", "talk": "talk"}
        name = "member-adapter-watch-" + names[op]
        if op == "end":
            method, audits = "delete", {"devices.adapter_watch_ended": 1}
        elif op in {"signal", "talk"}:
            method, status = "post", 201
            body = {"kind": "offer", "sdp": "v=0 new"} if op == "signal" else {"active": True}
            if op == "talk":
                audits = {"devices.adapter_talk_started": 1}
    elif op in {"artifacts", "artifact_url"}:
        row = artifact(w)
        name = "member-adapter-artifacts" if op == "artifacts" else "member-adapter-artifact-url"
        args = [w.job.pk] if op == "artifacts" else [row.pk]
    else:
        row, name, args = event(w), "member-adapter-detections", [w.job.pk]

    def call(c):
        if op == "frame":
            cache.set(f"adapter-frame:{row.pk}", "retained-jpeg", 60)
        return send(c or (w.client if op == "talk" else w.owner), "devices:" + name, args, method, body)

    def check(response):
        data = response.data
        if op == "start":
            saved = AdapterWatch.objects.get(pk=data["id"])
            assert (saved.viewer_id, saved.binding_id, saved.status, saved.record) == (
                w.member.pk, w.binding.pk, "active", False)
            assert AdapterWatch.objects.filter(binding=w.binding).count() == 1
        elif op in {"end", "poll", "signal", "talk"}:
            row.refresh_from_db()
            if op == "end":
                assert row.status == "ended" and row.ended_at is not None
            elif op == "poll":
                assert data["signals"] == [{"n": 1, "from": "adapter", "kind": "answer",
                                            "sdp": "v=0 retained", "candidate": ""}]
            else:
                expected = {"n": 2, "from": "viewer", "kind": "offer" if op == "signal" else "ptt_on",
                            "sdp": "v=0 new" if op == "signal" else "", "candidate": ""}
                assert row.signals[-1] == expected and len(row.signals) == 2
                assert data["n"] == 2
                if op == "talk":
                    assert row.talk_presses == 1 and data["active"] is True
        elif op == "frame":
            assert data == {"content_type": "image/jpeg", "data": "retained-jpeg"}
        elif op == "artifact_url":
            assert data == {"url": url, "content_type": "image/jpeg", "kind": "thumbnail"}
        else:
            assert [r["id"] for r in data["results"]] == [str(row.pk)]
            if op == "detections":
                assert (data["results"][0]["kind"], data["results"][0]["confidence"]) == ("smoke", 0.75)
                assert "note" not in data["results"][0]
            else:
                assert data["results"][0]["service_request_id"] == w.job.pk
    prove(w.space, w.objects, key, call, check, status=status, audits=audits,
          outsiders=[(w.foreign, foreign_refusal(native)), (w.second, (404, "not_found"))])

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]
