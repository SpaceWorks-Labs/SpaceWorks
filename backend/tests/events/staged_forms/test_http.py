"""Exercise owned views without depending on G's not-yet-installed URL mounts."""
from uuid import uuid4
import pytest
from django.urls import path, include, reverse
from django.test import override_settings
from rest_framework.test import APIRequestFactory, force_authenticate
from apps.events.staged_forms.views_member import StageFormContextView, StageResponseSubmitView
from apps.events.staged_forms.response_models import StageFormAssignment, StageFormResponse
from apps.events.staged_forms.stage_workflow import activate_locked
from apps.events.staged_forms.trigger_service import Participant
from apps.events.staged_forms import views_member
from .conftest import definition, participant, payload
from .test_inline_submission import outer

urlpatterns = [
    path("api/v1/member/makerspaces/<int:makerspace_id>/events/<int:pk>/", include("apps.events.staged_forms.urls_member")),
    path("api/v1/admin/events/<int:pk>/", include("apps.events.staged_forms.urls_admin")),
]
pytestmark = pytest.mark.django_db(transaction=True)


def test_virtual_context_get_is_repeatable_and_has_no_domain_writes(stage_env):
    env = stage_env
    row = definition(env)
    request = APIRequestFactory().get("/context/", {"creation_operation_id": str(uuid4())})
    force_authenticate(request, user=env.owner)
    for _ in range(2):
        response = StageFormContextView.as_view()(request, makerspace_id=env.space.pk, pk=env.event.pk, stage_form_id=row.pk)
        assert response.status_code == 200
        assert response["Cache-Control"] == "private, no-store"
    assert not StageFormAssignment.objects.exists() and not StageFormResponse.objects.exists()


def test_exact_response_replay_precedes_expensive_preparation(stage_env, monkeypatch):
    env = stage_env
    registration, application = participant(env)
    row = definition(env)
    with outer(env) as (event, locks):
        assignment = activate_locked(definition=row, subject=Participant(event, env.owner.pk, registration, application), locks=locks)
    data = payload(row, operation_id=str(uuid4()), expected_version=assignment.response.version,
        expected_assignment_version=assignment.version)
    data.pop("stage_form_id")
    def send(body):
        request = APIRequestFactory().post("/submit/", body, format="json", HTTP_IDEMPOTENCY_KEY=body["operation_id"])
        force_authenticate(request, user=env.owner)
        return StageResponseSubmitView.as_view()(request, makerspace_id=env.space.pk, pk=env.event.pk, response_id=assignment.response.pk)
    first = send(data)
    assert first.status_code == 200
    def forbidden(**kwargs):
        pytest.fail("Replay must not revalidate files or provision account keys")
    monkeypatch.setattr(views_member, "prepare", forbidden)
    replay = send(data)
    assert replay.status_code == 200 and replay.data == first.data
    changed = send({**data, "answers": {"answer": "Changed"}})
    assert changed.status_code == 409


@override_settings(ROOT_URLCONF=__name__)
def test_all_frozen_stage_route_names_resolve_inside_owned_url_modules():
    import json
    from pathlib import Path
    contract = json.loads((Path(__file__).parents[1] / "programme/contracts/reimbursement_addon.json").read_text(encoding="utf-8"))
    values = {"makerspace_id": 1, "pk": 2, "stage_form_id": 3, "assignment_id": 4, "response_id": 5, "asset_id": 6}
    for route in contract["routes"]:
        if "stage-" not in route["name"]:
            continue
        kwargs = {key: value for key, value in values.items() if "{" + key + "}" in route["path"]}
        expected = route["path"].format(**kwargs)
        assert reverse(route["name"], kwargs=kwargs) == expected
