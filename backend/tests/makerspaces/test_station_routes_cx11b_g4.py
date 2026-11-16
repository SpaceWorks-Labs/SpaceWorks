"""Station transport routes: real signed session/lease, domain effects and independent gates."""
from uuid import UUID

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.boxes.models import BoxScan
from apps.evidence.models import EvidencePhoto
from apps.hardware_requests.models import ReplayCommand
from tests.hardware_requests.replay_helpers import envelope
from tests.makerspaces.station_support_cx11b_g4 import station_world
from tests.operations.route_support_cx11b_g4 import cycle, outsider

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending, pytest.mark.area_devices]

CASES = [(name, key) for name, keys in [
    ("kiosk-station-work-package", ("inventory.kiosk", "loans.enabled", "request_workflow")),
    ("kiosk-station-evidence-prepare", ("inventory.kiosk", "loans.enabled", "evidence_uploads")),
    ("kiosk-station-command-online", ("inventory.kiosk", "loans.enabled", "request_workflow")),
    ("kiosk-replay-prepare", ("inventory.kiosk", "loans.enabled", "request_workflow")),
    ("kiosk-replay-execute", ("inventory.kiosk", "loans.enabled", "request_workflow")),
] for key in keys]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,key", CASES)
def test_station_route_has_effect_and_refuses_without_a_domain_write(native, name, key, settings, monkeypatch):
    w = station_world(native, settings)
    uploads = []
    def presign(key, mime, *, max_bytes, exact_bytes):
        uploads.append((key, mime))
        return {"url": "https://storage.example.test/upload", "fields": {"key": f"staging/{key}", "Content-Type": mime}}
    monkeypatch.setattr("apps.evidence.services_upload.presigned_upload", presign)
    replay = name.startswith("kiosk-replay")
    kwargs = {"public_token": w.credential.public_token}
    data = envelope(w)
    if name == "kiosk-replay-execute":
        prepared = w.client.post(reverse("kiosk-replay-prepare", kwargs=kwargs), data, format="json", **w.headers)
        assert prepared.status_code == 200 and prepared.data["state"] == "prepared", prepared.data
        kwargs["client_command_id"] = data["client_command_id"]
    if name == "kiosk-station-work-package":
        body = {"kind": "reviewed_request", "id": w.request.pk}
    elif name == "kiosk-station-evidence-prepare":
        body = {"evidence_type": "issue", "content_type": "image/jpeg", "size_bytes": 123}
    elif name == "kiosk-station-command-online":
        body = {"version": 1, "kind": "assign_box", "payload": {"request_id": w.request.pk, "box_code": w.box.code}}
    else:
        body = data
    url = reverse(name, kwargs=kwargs)

    def check(response):
        w.request.refresh_from_db()
        if name == "kiosk-station-work-package":
            assert (response.data["id"], response.data["status"], response.data["lines"]) == (w.request.pk, "accepted", [
                {"item_id": w.item.pk, "label": w.product.name, "quantity": 1, "returned": 0}])
        elif name == "kiosk-station-evidence-prepare":
            photo = EvidencePhoto.objects.get(pk=response.data["evidence_id"])
            assert (photo.uploaded_by_id, photo.makerspace_id, photo.evidence_type, photo.size_bytes) == (w.user.pk, w.space.pk, "issue", 123)
            assert response.data["fields"]["key"] == f"staging/{photo.object_key}"
            assert uploads[-1] == (photo.object_key, "image/jpeg")
        elif name == "kiosk-replay-prepare":
            row = ReplayCommand.objects.get(pk=response.data["replay_id"])
            assert (row.state, row.actor_id, row.subject_request_id, row.client_command_id) == ("prepared", w.user.pk, w.request.pk, UUID(data["client_command_id"]))
            assert ReplayCommand.objects.filter(station=w.station).count() == 1
        else:
            assert w.request.assigned_box_id == w.box.pk
            scan = BoxScan.objects.get(request=w.request)
            assert (scan.box_id, scan.actor_id, scan.context) == (w.box.pk, w.user.pk, "issue")
            if replay:
                row = ReplayCommand.objects.get(pk=response.data["replay_id"])
                assert (row.state, row.result_request_id, row.claim_attempts) == ("succeeded", w.request.pk, 1)
    actions = {"kiosk-station-work-package": ("kiosk.work_package_issued",), "kiosk-station-evidence-prepare": ("kiosk.evidence_upload_issued",),
        "kiosk-station-command-online": ("box.assigned", "box.scanned", "kiosk.online_command_executed"),
        "kiosk-replay-prepare": ("kiosk.replay_prepared",),
        "kiosk-replay-execute": ("kiosk.replay_claimed", "box.assigned", "box.scanned", "kiosk.replay_succeeded")}
    foreign = APIClient() if replay else outsider(native)
    # Replay uses station-cookie authentication, not native/browser account authority;
    # a missing signature remains 403 session_mismatch (520, authentication unchanged).
    off = (404, "feature_disabled" if key == "inventory.kiosk" else "module_disabled")
    if not replay:
        # live_session conceals disabled station capabilities with its generic session
        # refusal; an operation-only source gate remains typed (station cookie contract).
        off = (403, "permission_denied") if key in {"inventory.kiosk", "loans.enabled"} else (404, "feature_disabled")
    cycle(w.space, key, lambda: w.client.post(url, body, format="json", **w.headers), check,
          on=(201 if name == "kiosk-station-evidence-prepare" else 200, None), off=off,
          refusal_key="kiosk_operation", named_switch=not replay, audit=actions[name],
          foreign=lambda: foreign.post(url, body, format="json", **w.headers),
          foreign_pair=(403, "session_mismatch" if replay else "permission_denied"))
