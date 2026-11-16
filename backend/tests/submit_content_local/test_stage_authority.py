"""Authority (#177 item 3): whoever may manage the hackathon edits stages; participants only read them.

These run through the production ProgrammeBoundary, not the fake one.
"""
from uuid import uuid4

import pytest
from django.apps import apps
from django.http import Http404
from rest_framework.exceptions import APIException

from apps.events.submissions import stage_service
from apps.events.submissions.boundary_runtime import STAFF_STAGE_ACTIONS
from apps.events.submissions.stage_service import fingerprint
from tests.events.collab_helpers import make_staff
from tests.events.ticketing_helpers import account, event_space, open_event

pytestmark = pytest.mark.django_db


@pytest.fixture
def programme(settings):
    settings.PII_ENCRYPTION_ENABLED = False
    space = event_space(f"stage-auth-{uuid4().hex[:8]}")
    space.enabled_features += ["events.hackathons"]
    space.save(update_fields=["enabled_features"])
    event = open_event(space)
    apps.get_model("events", "HackathonConfig").objects.create(event=event, enabled=True)
    return space, event


def test_staff_stage_actions_need_the_hackathon_manager():
    assert STAFF_STAGE_ACTIONS == {"stage_edit", "stage_shortlist", "stage_extension"}


def test_a_member_cannot_read_or_edit_the_stage_plan(programme):
    space, event = programme
    member = account(f"member-{uuid4().hex[:6]}")
    with pytest.raises((Http404, APIException)):
        stage_service.read(actor=member, event_id=event.pk)
    with pytest.raises((Http404, APIException)):
        stage_service.replace(actor=member, event_id=event.pk, data={
            "operation_id": uuid4(), "expected_fingerprint": fingerprint([]), "preset": "",
            "stages": [{"name": "Sneaky"}]})


def test_the_space_manager_reads_the_virtual_single_stage_then_saves_a_plan(programme):
    space, event = programme
    manager = make_staff(space, username=f"stage-boss-{uuid4().hex[:6]}")
    plan = stage_service.read(actor=manager, event_id=event.pk)
    assert [row["name"] for row in plan["stages"]] == ["Submission"] and plan["stages"][0]["id"] is None
    assert {"single", "full_pipeline"} <= {preset["key"] for preset in plan["presets"]}
    saved = stage_service.replace(actor=manager, event_id=event.pk, data={
        "operation_id": uuid4(), "expected_fingerprint": plan["fingerprint"], "preset": "single",
        "stages": [{"name": "Submission", "content_mode": "links_only", "required_link_kinds": ["repo"]}]})
    assert saved["stages"][0]["content_mode"] == "links_only"
