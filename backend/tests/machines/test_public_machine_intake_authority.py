"""Decision 142: public intake requires local membership and an open local visit."""
import pytest

from apps.machines.models import MachineServiceRequest, ServiceRequestFile
from apps.makerspaces.waiver_services import accept_waiver, publish_waiver
from tests.machines.eta_helpers import enable, owner, world
from tests.machines.session_helpers import check_in
from tests.rbac_f6_helpers import community_member
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def post_paths(w):
    base = f"/api/v1/public/{w.space.slug}"
    return [
        (f"{base}/machine-jobs/uploads", {"queue_id": w.queue.pk, "filename": "part.stl", "content_type": "model/stl", "kind": "model"}),
        (f"{base}/machine-jobs", {"queue_id": w.queue.pk, "title": "Part", "file_ids": [1], "acknowledgements": {"pickup_policy": True, "failure_policy": True, "own_content": True}}),
        (f"{base}/machine-service-requests", {"machine_id": w.machines[0].pk, "title": "Part"}),
        (f"{base}/machine-service/3d-printer/uploads", {"queue_id": w.queue.pk, "filename": "part.stl", "kind": "stl"}),
        (f"{base}/machine-service/3d-printer/requests", {"queue_id": w.queue.pk, "title": "Part", "file_ids": [1]}),
    ]


@pytest.mark.parametrize("disabled", ["membership", "presence"])
def test_unavailable_precedes_real_upload_or_submit(disabled):
    w = world("intake-off", printing=True, membership=True)
    enable(w.space, "membership", "presence", "printing", off=(disabled,))
    client = authenticated_client(owner("intake-off-owner"))
    discovery = client.get(f"/api/v1/public/{w.space.slug}/machine-jobs/types")
    assert discovery.status_code == 404 and discovery.json()["code"] == "machine_intake_unavailable"
    for path, payload in post_paths(w):
        result = client.post(path, payload, format="json")
        assert result.status_code == 404, (path, result.content)
        assert result.json()["code"] == "machine_intake_unavailable"
    assert not MachineServiceRequest.objects.filter(makerspace=w.space).exists()
    assert not ServiceRequestFile.objects.filter(makerspace=w.space).exists()


def test_active_local_membership_still_needs_open_local_session():
    w = world("intake-visit", printing=True, membership=True)
    enable(w.space, "membership", "presence", "printing")
    membership = community_member(w.space, "intake-member")
    client = authenticated_client(membership.user)
    for path, payload in post_paths(w):
        result = client.post(path, payload, format="json")
        assert result.status_code == 403, (path, result.content)
        assert result.json()["code"] == "presence_required"
    assert not MachineServiceRequest.objects.filter(makerspace=w.space).exists()
    assert not ServiceRequestFile.objects.filter(makerspace=w.space).exists()
    check_in(w.space, membership)
    response = client.get(f"/api/v1/public/{w.space.slug}/machine-jobs/types")
    assert response.status_code == 200


def test_foreign_membership_does_not_authorize_local_intake():
    w = world("intake-local", membership=True)
    other = world("intake-foreign", membership=True)
    enable(w.space, "membership", "presence")
    enable(other.space, "membership", "presence")
    membership = community_member(other.space, "foreign")
    check_in(other.space, membership)
    client = authenticated_client(membership.user)
    path, payload = post_paths(w)[0]
    response = client.post(path, payload, format="json")
    assert response.status_code == 403 and response.json()["code"] == "membership_required"
    assert not ServiceRequestFile.objects.filter(makerspace=w.space).exists()


def test_revocation_expiry_and_current_waiver_are_checked_before_staging():
    w = world("intake-recheck", membership=True)
    enable(w.space, "membership", "presence")
    membership = community_member(w.space, "local")
    client = authenticated_client(membership.user)
    path, payload = post_paths(w)[0]
    publish_waiver(w.staff, w.space, "Liability terms", "v1")
    check_in(w.space, membership)
    denied = client.post(path, payload, format="json")
    assert denied.status_code == 403 and denied.json()["code"] == "waiver_acceptance_required"
    accept_waiver(membership)
    membership.status = "revoked"
    membership.save(update_fields=["status"])
    denied = client.post(path, payload, format="json")
    assert denied.status_code == 403 and denied.json()["code"] == "membership_required"
    membership.status = "active"
    membership.save(update_fields=["status"])
    from apps.presence.models import PresenceSession
    from django.utils import timezone
    PresenceSession.objects.filter(member=membership.user, makerspace=w.space).update(expires_at=timezone.now())
    denied = client.post(path, payload, format="json")
    assert denied.status_code == 403 and denied.json()["code"] == "presence_required"
    assert not ServiceRequestFile.objects.filter(makerspace=w.space).exists()


def test_printer_upload_uses_job_capability_before_storage(monkeypatch):
    w = world("intake-printer-switch", printing=True, membership=True)
    enable(w.space, "membership", "presence", "printing")
    membership = community_member(w.space, "printer")
    check_in(w.space, membership)
    w.space.enabled_features = [key for key in w.space.enabled_features if key != "machines.job_requests"]
    w.space.save(update_fields=["enabled_features"])
    calls = []
    monkeypatch.setattr("apps.machines.service_storage.presigned_upload", lambda *args: calls.append(args))
    path, payload = post_paths(w)[3]
    response = authenticated_client(membership.user).post(path, payload, format="json")
    assert response.status_code == 404 and response.json()["code"] == "feature_disabled"
    assert response.json()["feature"] == "machines.job_requests"
    assert calls == [] and not ServiceRequestFile.objects.filter(makerspace=w.space).exists()


def test_job_requests_off_refuses_every_intake_before_presence():
    """Decision 221e: print, per-machine and job intake all sit behind `machines.job_requests`."""
    w = world("intake-jobs-off", printing=True, membership=True)
    enable(w.space, "membership", "presence", "printing")
    w.space.enabled_features = [key for key in w.space.enabled_features if key != "machines.job_requests"]
    w.space.save(update_fields=["enabled_features"])
    membership = community_member(w.space, "not-checked-in")
    client = authenticated_client(membership.user)
    base = f"/api/v1/public/{w.space.slug}"
    for path in (f"{base}/machine-jobs/types", f"{base}/machine-service/3d-printer/queues",
                 f"{base}/machine-service/3d-printer/consumable-pools"):
        result = client.get(path)
        assert result.status_code == 404, (path, result.content)
        assert result.json()["code"] == "feature_disabled" and result.json()["feature"] == "machines.job_requests"
    for path, payload in post_paths(w):
        result = client.post(path, payload, format="json")
        assert result.status_code == 404, (path, result.content)
        assert result.json()["code"] == "feature_disabled" and result.json()["feature"] == "machines.job_requests"
    assert not MachineServiceRequest.objects.filter(makerspace=w.space).exists()
    assert not ServiceRequestFile.objects.filter(makerspace=w.space).exists()


def test_valid_member_can_stage_a_legacy_printer_upload(monkeypatch):
    w = world("intake-printer-yes", printing=True, membership=True)
    enable(w.space, "membership", "presence", "printing")
    membership = community_member(w.space, "printer")
    check_in(w.space, membership)
    monkeypatch.setattr("apps.machines.service_storage.presigned_upload", lambda *args: {"url": "https://upload.test"})
    path, payload = post_paths(w)[3]
    response = authenticated_client(membership.user).post(path, payload, format="json")
    assert response.status_code == 201, response.content
    assert ServiceRequestFile.objects.filter(pk=response.json()["file_id"], owner_user=membership.user).exists()
