from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.events.judging import results_workflow as workflow
from apps.events.judging.models_results import EventResultRevision


@pytest.mark.parametrize("already_announced", [False, True])
def test_only_first_announcement_sets_retention_anchor(monkeypatch, already_announced):
    event = SimpleNamespace(pk=42)
    actor = SimpleNamespace(pk=17)
    locks = object()
    result = SimpleNamespace(pk=101, version=2, awards=Mock(), rounds=Mock())
    result.awards.all.return_value = []
    result.rounds.select_related.return_value.all.return_value = []
    earlier = SimpleNamespace(pk=1, published_at=timezone.now()) if already_announced else None
    model = Mock()
    model.objects.filter.return_value.first.return_value = result
    model.objects.filter.return_value.order_by.return_value.first.return_value = result
    announcements = Mock()
    announcements.objects.filter.return_value.first.return_value = None
    announcements.objects.filter.return_value.order_by.return_value.first.return_value = earlier
    announcements.objects.create.return_value = SimpleNamespace(pk=2)
    state = SimpleNamespace(version=1, current_announcement_id=None, save=Mock())
    state_model = Mock()
    state_model.objects.get_or_create.return_value = (state, True)
    @contextmanager
    def mutation(*args, **kwargs):
        yield event, locks
    ports = Mock()
    monkeypatch.setattr(workflow, "mutation", mutation)
    monkeypatch.setattr(workflow, "command", lambda *args, run, **kwargs: run())
    monkeypatch.setattr(workflow, "EventResultRevision", model)
    monkeypatch.setattr(workflow, "ResultAnnouncement", announcements)
    monkeypatch.setattr(workflow, "ResultPublicationState", state_model)
    monkeypatch.setattr(workflow, "runtime", lambda: ports)
    monkeypatch.setattr(workflow, "audit", Mock())
    monkeypatch.setattr(workflow, "notice", Mock())
    response = workflow.publish(42, actor=actor, data={"operation_id": str(uuid4()),
        "expected_version": 2, "result_revision_id": 101})
    assert response["state"] == "published"
    assert ports.publish_retention_locked.call_count == (0 if already_announced else 1)
    assert state.current_announcement.pk == 2


def test_result_snapshot_cannot_be_modified_through_model_save():
    result = EventResultRevision(event_id=42, version=1, algorithm_version="spaceworks-judging-v1",
                                 aggregates={}, content_sha256="a" * 64, finalized_at=timezone.now())
    result._state.adding = False
    result.aggregates = {"tampered": True}
    with pytest.raises(RuntimeError, match="append-only"):
        result.save()


def test_invalidating_one_ranked_view_invalidates_its_whole_ballot_exposure(monkeypatch):
    from apps.events.judging import ballot_invalidation
    assignment = SimpleNamespace(pk=81, round_id=2, judge_role_assignment_id=9, batch="v3")
    peer = SimpleNamespace(pk=82, state="scored", version=4, save=Mock())
    ballots = Mock()
    ballots.objects.filter.return_value.exists.return_value = True
    rows = Mock()
    rows.objects.select_for_update.return_value.filter.return_value.exclude.return_value.order_by.return_value = [peer]
    monkeypatch.setattr(ballot_invalidation, "JudgeRankingBallot", ballots)
    monkeypatch.setattr(ballot_invalidation, "JudgeAssignment", rows)
    monkeypatch.setattr(ballot_invalidation, "audit", Mock())
    monkeypatch.setattr(ballot_invalidation, "assert_locked", Mock())
    notification = Mock()
    monkeypatch.setattr(ballot_invalidation, "notice", notification)
    assert ballot_invalidation.invalidate_peers_locked(event=object(), actor=object(), assignment=assignment, locks=object()) == 1
    assert peer.state == "invalidated" and peer.version == 5
    assert notification.call_args.args[1:] == ("assignment_invalidated", 82, 5)
