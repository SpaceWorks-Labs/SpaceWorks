"""Decision 221(e): every member/public intake route needs `machines.job_requests` on the server."""
import pytest

from apps.machines.models import MachineServiceRequest
from tests.machines.eta_helpers import enable, owner, world
from tests.machines.test_public_machine_intake_authority import post_paths
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def test_capability_off_refuses_every_intake_route_before_any_work():
    w = world("jr-off", printing=True, membership=True)
    enable(w.space, "membership", "presence", "printing")
    w.space.enabled_features = sorted(set(w.space.enabled_features or []) - {"machines.job_requests"})
    w.space.save(update_fields=["enabled_features"])
    client = authenticated_client(owner("jr-off-owner"))
    base = f"/api/v1/public/{w.space.slug}"
    gets = [f"{base}/machine-jobs/types", f"{base}/machine-service/3d-printer/queues",
            f"{base}/machine-service/3d-printer/pools"]
    for path in gets:
        assert client.get(path).status_code == 404, path
    assert client.get(gets[0]).json()["code"] == "feature_disabled"
    for path, payload in post_paths(w):
        result = client.post(path, payload, format="json")
        assert result.status_code == 404, (path, result.content)
        assert result.json()["code"] == "feature_disabled" and result.json()["feature"] == "machines.job_requests"
    assert not MachineServiceRequest.objects.filter(makerspace=w.space).exists()
