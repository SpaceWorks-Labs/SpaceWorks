"""Open items B10, C31, F2 (batch 1): events authority fallbacks."""
import inspect
import json
import pathlib

import pytest

pytestmark = pytest.mark.django_db


def test_f2_judging_route_manifest_records_the_read_only_fallback():
    path = pathlib.Path(__file__).resolve().parents[2] / "apps" / "events" / "judging" / "route_manifest.json"
    rows = {row["name"]: row for row in json.loads(path.read_text(encoding="utf-8"))["routes"]}
    for name in ("events-programme-admin-tracks-list", "events-programme-admin-tracks-detail"):
        assert "manage_team" in rows[name]["authority"]
    assert rows["events-programme-admin-prizes-list"]["authority"] == "manage_hackathon"


def test_c31_track_detail_has_the_same_read_only_fallback_as_the_list():
    from apps.events.judging import views_definitions as views
    assert "get" in views.TrackDetail.__dict__ and "get" in views.TrackList.__dict__


def test_b10_feedback_resolves_an_account_only_registration_without_membership():
    from apps.events import views_feedback_member as views
    source = inspect.getsource(views._owned_registration)
    assert "participant_space" in source and "MemberPresenceRequired" not in source
