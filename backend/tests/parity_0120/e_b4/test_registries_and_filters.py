"""E-B4: the switch, the route catalogue, the audit catalogue and the D13 filters."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.urls import resolve, reverse
from rest_framework.exceptions import ValidationError

from apps.accounts.programme_route_catalog import BY_NAME, NATIVE_DECISIONS
from apps.audit.presentation_catalog import PRESENTATION_CATALOG
from apps.events import staff_list_specs
from apps.events.judging import views_scoring
from apps.events.judging.feature import SCORES_EXPORT
from apps.events.submissions import gallery_projection
from apps.makerspaces.capability_definitions import FEATURES

ROUTES = {"events-programme-admin-scores-export": ("GET", "HEAD"),
          "events-programme-admin-results-unpublish": ("POST",),
          "events-programme-admin-submissions-reinstate": ("POST",)}


def test_scores_export_is_an_off_by_default_child_of_hackathons():
    feature = FEATURES[SCORES_EXPORT]
    assert feature.default_enabled is False
    assert feature.requires_features == ("events.hackathons",)


@pytest.mark.parametrize("name,methods", sorted(ROUTES.items()))
def test_every_route_is_catalogued_native_and_mounted(name, methods):
    assert BY_NAME[name] == (methods, "event")
    assert NATIVE_DECISIONS[name] == "native"
    kwargs = {"pk": 1, "submission_id": 2} if name.endswith("reinstate") else {"pk": 1}
    assert resolve(reverse(name, kwargs=kwargs)).url_name == name


def test_audit_entries_are_catalogued_without_personal_paths():
    for action in ("event.programme.scores_exported", "event.submission_reinstated", "event.programme.results_unpublished",
                   "event.programme.assignment_applied"):
        entry = PRESENTATION_CATALOG[action]
        assert not {"name", "email", "reason", "score"} & set(entry.permitted_meta_paths)


def rows(*titles, state="assigned"):
    return [{"title": title, "state": state, "id": index} for index, title in enumerate(titles)]


def test_judge_list_filters_by_state_and_title_and_counts_the_matches(monkeypatch):
    items = [*rows("Robot arm"), *rows("Robot dog", state="scored"), *rows("Compost bin", state="scored")]
    request = SimpleNamespace(user=SimpleNamespace(pk=1), query_params={"state": "scored", "q": " robot "})
    captured = {}
    monkeypatch.setattr(views_scoring, "admin_event", lambda *a: SimpleNamespace(pk=5))
    monkeypatch.setattr(views_scoring, "runtime", lambda: SimpleNamespace(judges=lambda pk: [
        SimpleNamespace(member_id=1, active=True, role_assignment_id=9)]))
    queryset = Mock()
    queryset.select_related.return_value.order_by.return_value = [object()] * len(items)
    monkeypatch.setattr(views_scoring, "JudgeAssignment", SimpleNamespace(objects=Mock(filter=Mock(return_value=queryset))))
    feed = iter(items)
    monkeypatch.setattr(views_scoring, "assignment_projection", lambda *a: next(feed))

    def fake_paginated(req, shown, serializer, **extra):
        captured.update(shown=shown, **extra)
        return captured
    monkeypatch.setattr(views_scoring, "paginated", fake_paginated)
    views_scoring.AssignmentList().get(request, 5)
    assert [item["title"] for item in captured["shown"]] == ["Robot dog"]
    assert captured["state_counts"] == {"assigned": 1, "scored": 1, "skipped": 0, "recused": 0, "invalidated": 0}


def test_judge_list_rejects_an_unknown_state(monkeypatch):
    monkeypatch.setattr(views_scoring, "admin_event", lambda *a: SimpleNamespace(pk=5))
    request = SimpleNamespace(user=SimpleNamespace(pk=1), query_params={"state": "bogus"})
    with pytest.raises(ValidationError):
        views_scoring.AssignmentList().get(request, 5)


def test_staff_results_list_accepts_a_search_filter():
    assert "q" in staff_list_specs.SPECS["results"][0].filters


def test_public_results_search_matches_project_or_prize(monkeypatch):
    awards = [SimpleNamespace(prize_name="Best hardware", rank=1, submission_snapshot_id=1, prize=None),
              SimpleNamespace(prize_name="Best software", rank=1, submission_snapshot_id=2, prize=None)]
    announcement = SimpleNamespace(published_at="t", result=SimpleNamespace(version=3, awards=Mock()))
    announcement.result.awards.select_related.return_value.filter.return_value.order_by.return_value = awards
    state = SimpleNamespace(current_announcement_id=1, current_announcement=announcement)
    monkeypatch.setattr(gallery_projection, "ResultPublicationState", SimpleNamespace(objects=Mock(filter=Mock(
        return_value=Mock(select_related=Mock(return_value=Mock(first=Mock(return_value=state))))))))
    monkeypatch.setattr(gallery_projection, "public_finalists", lambda event: None)
    titles = {1: "Robot arm", 2: "Compost bin"}
    monkeypatch.setattr(gallery_projection, "runtime", lambda: SimpleNamespace(
        snapshot=lambda pk: SimpleNamespace(id=pk, current=True, eligible=True, event_id=42, title=titles[pk])))
    monkeypatch.setattr(gallery_projection, "GalleryConsent", SimpleNamespace(objects=Mock(filter=Mock(
        return_value=Mock(first=Mock(return_value=object()))))))
    event = SimpleNamespace(pk=42)
    assert [a["title"] for a in gallery_projection.public_results(event, "compost")["awards"]] == ["Compost bin"]
    assert [a["title"] for a in gallery_projection.public_results(event, "HARDWARE")["awards"]] == ["Robot arm"]
    assert len(gallery_projection.public_results(event)["awards"]) == 2
