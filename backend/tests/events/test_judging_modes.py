"""The pairwise mode beside rubric and top-three: switch on/off, >=3 reviews, rules and routes."""

from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.events.judging.definitions_workflow import save_definition
from apps.events.judging.errors import ProgrammeError
from apps.events.judging.models_definitions import JudgingRound
from apps.events.judging.models_pairwise import JudgePairwiseCursor
from apps.events.judging.projections import progress
from tests.events.collab_helpers import client_for
from tests.events.pairwise_helpers import command, judge_command, pairwise_round, pairwise_world

pytestmark = pytest.mark.django_db


def _set_feature(space, on):
    space.refresh_from_db()
    features = set(space.enabled_features) - {"events.pairwise_judging"}
    space.enabled_features = sorted(features | ({"events.pairwise_judging"} if on else set()))
    space.save(update_fields=["enabled_features"])


def _save(world, **fields):
    return save_definition(world.event.pk, actor=world.manager, kind="judging-rounds", data=command(**fields))


@pytest.mark.parametrize("fields,field", [
    ({"min_reviews": 2}, "min_reviews"),
    ({"normalization": "zscore"}, "normalization"),
    ({"criteria": [{"key": "impact", "label": "Impact", "weight": "1",
                    "anchors": {str(i): "x" for i in range(1, 6)}}]}, "criteria"),
])
def test_pairwise_rounds_keep_three_reviews_and_refuse_rubric_settings(settings, monkeypatch, fields, field):
    world = pairwise_world(settings, monkeypatch, projects=1, judges=0)
    with pytest.raises(ValidationError) as error:
        _save(world, key="pw", mode="pairwise", **fields)
    assert field in error.value.detail
    assert not JudgingRound.objects.filter(event=world.event).exists()


def test_guidance_and_exploration_are_pairwise_only_and_frozen_at_open(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=2, judges=1)
    with pytest.raises(ValidationError):
        _save(world, key="top", mode="top3", guidance="Pick the clearer demo")
    round = pairwise_round(world, guidance="Which solves the brief better?", exploration="0.20")
    assert round.configuration["guidance"] == "Which solves the brief better?"
    assert round.configuration["pairwise"]["exploration"] == 0.2
    assert round.configuration["min_reviews"] == 3 and round.state == "open"
    view = progress(round, actor=world.manager)
    assert view["allowed_actions"] == ["close"]  # no batch assignment for pairwise
    assert view["estimated_judges"] >= 1


def test_switching_mode_is_audited(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=1, judges=0)
    saved = _save(world, key="r1", mode="top3")
    save_definition(world.event.pk, actor=world.manager, kind="judging-rounds", object_id=saved["id"],
                    data=command(saved["version"], mode="pairwise"))
    row = AuditLog.objects.get(action="event.programme.round_mode_changed")
    assert row.meta["previous"] == "top3" and row.meta["mode"] == "pairwise"


def test_switch_off_refuses_pairwise_and_switch_on_restores_the_same_state(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=3, judges=1)
    round = pairwise_round(world)
    judge_command(world, 0, "next", round)
    before = JudgePairwiseCursor.objects.get(round=round)
    _set_feature(world.space, False)
    with pytest.raises(ProgrammeError) as error:
        _save(world, key="another", mode="pairwise")
    assert error.value.status_code == 403 and error.value.detail["code"] == "feature_disabled"
    with pytest.raises(ProgrammeError):
        from apps.events.judging.round_workflow import transition
        transition(world.event.pk, round.pk, actor=world.manager, action="close", data=command(round.version))
    judge = client_for(world.judges[0])
    state = reverse("events-programme-admin-pairwise-state", kwargs={"pk": world.event.pk, "round_id": round.pk})
    assert judge.get(state).status_code == 404
    op = str(uuid4())
    post = judge.post(reverse("events-programme-admin-pairwise-next", kwargs={"pk": world.event.pk, "round_id": round.pk}),
                      {"operation_id": op, "expected_version": before.version}, format="json", HTTP_IDEMPOTENCY_KEY=op)
    assert post.status_code == 404
    _set_feature(world.space, True)
    restored = judge.get(state)
    assert restored.status_code == 200
    assert restored.json()["version"] == before.version and restored.json()["previous"]["assignment_id"] == before.previous_id
    # Rubric and top-three rounds never depended on the switch.
    _set_feature(world.space, False)
    assert _save(world, key="rubricless", mode="top3")["id"]


def test_standings_are_organiser_only_and_judges_drive_their_own_cursor_over_http(settings, monkeypatch):
    world = pairwise_world(settings, monkeypatch, projects=3, judges=1)
    round = pairwise_round(world)
    kwargs = {"pk": world.event.pk, "round_id": round.pk}
    standings = reverse("events-programme-admin-pairwise-standings", kwargs=kwargs)
    judge, manager = client_for(world.judges[0]), client_for(world.manager)
    assert judge.get(standings).status_code in (403, 404)
    response = manager.get(standings)
    assert response.status_code == 200 and {row["snapshot_id"] for row in response.json()["rows"]} == set(world.snapshots)
    state = judge.get(reverse("events-programme-admin-pairwise-state", kwargs=kwargs)).json()
    assert state["allowed_actions"] == ["next", "skip", "recuse"] and state["previous"] is None
    op = str(uuid4())
    moved = judge.post(reverse("events-programme-admin-pairwise-next", kwargs=kwargs),
                       {"operation_id": op, "expected_version": state["version"]}, format="json", HTTP_IDEMPOTENCY_KEY=op)
    assert moved.status_code == 200
    state = judge.get(reverse("events-programme-admin-pairwise-state", kwargs=kwargs)).json()
    assert state["allowed_actions"] == ["compare", "skip", "recuse"] and state["previous"]["title"].startswith("Project")
    listing = judge.get(reverse("events-programme-admin-pairwise-rounds-list", kwargs={"pk": world.event.pk}))
    assert listing.status_code == 200 and listing.json()["count"] == 1
