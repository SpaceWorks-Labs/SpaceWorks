"""Decision 246: the machine job-request intake with the capability ON (roles, validation, isolation)."""
import pytest
from rest_framework.test import APIClient

from apps.machines.models import MachineServiceRequest
from tests.machines.eta_helpers import enable, owner, world
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def _on(slug):
    w = world(slug)
    enable(w.space)
    w.space.enabled_features = sorted(set(w.space.enabled_features or []) | {"machines.job_requests"})
    w.space.save(update_fields=["enabled_features"])
    return w


def test_with_the_capability_on_a_signed_in_owner_sees_types_and_anonymous_does_not():
    w = _on("jrc-on")
    # Intake needs the membership and presence modules as well as the capability (decision 221e).
    enable(w.space, "membership", "presence")
    url = f"/api/v1/public/{w.space.slug}/machine-jobs/types"
    assert authenticated_client(owner("jrc-on-owner")).get(url).status_code == 200
    # Decision 221(e) gates intake on the modules and capability, not on identity: the types catalogue is a
    # public read (`PublicJobTypesView` is AllowAny); staging files and submitting still need a signed-in member.
    assert APIClient().get(url).status_code == 200


@pytest.mark.parametrize("body", [
    {}, {"title": "Part"}, {"queue_id": 999999, "title": "Part", "file_ids": [1]},
    {"queue_id": "x", "title": "", "file_ids": []},
])
def test_job_submission_validation_creates_nothing(body):
    w = _on("jrc-valid")
    client = authenticated_client(owner("jrc-valid-owner"))
    response = client.post(f"/api/v1/public/{w.space.slug}/machine-jobs", body, format="json")
    assert response.status_code in (400, 404, 409, 422)
    assert not MachineServiceRequest.objects.filter(makerspace=w.space).exists()


def test_another_spaces_queue_cannot_be_used_and_nothing_is_created():
    mine, theirs = _on("jrc-iso-a"), _on("jrc-iso-b")
    client = authenticated_client(owner("jrc-iso-owner"))
    body = {"queue_id": theirs.queue.pk, "title": "Part", "file_ids": [1],
            "acknowledgements": {"pickup_policy": True, "failure_policy": True, "own_content": True}}
    response = client.post(f"/api/v1/public/{mine.space.slug}/machine-jobs", body, format="json")
    assert response.status_code in (400, 404, 409, 422)
    assert not MachineServiceRequest.objects.exists()


def test_anonymous_cannot_upload_or_submit_even_with_the_capability_on():
    w = _on("jrc-anon")
    base = f"/api/v1/public/{w.space.slug}"
    for path, body in (
        (f"{base}/machine-jobs/uploads", {"queue_id": w.queue.pk, "filename": "p.stl", "content_type": "model/stl", "kind": "model"}),
        (f"{base}/machine-jobs", {"queue_id": w.queue.pk, "title": "Part", "file_ids": [1]}),
    ):
        assert APIClient().post(path, body, format="json").status_code in (401, 403)
    assert not MachineServiceRequest.objects.exists()
