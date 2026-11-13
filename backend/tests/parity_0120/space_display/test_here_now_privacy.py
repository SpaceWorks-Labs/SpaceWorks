"""Decision 307b: the "Here now" privacy matrix per audience."""
import pytest

from apps.presence.here_now import here_now
from apps.presence.privacy import update_preference, update_settings

pytestmark = pytest.mark.django_db
URL = "/api/v1/public/makerspaces/display-lane/presence/here-now/"


def _people(lane, viewer=None):
    return [p["display_name"] for p in here_now(lane.space, viewer)["people"]]


def test_logged_out_sees_only_open_web_profiles(lane):
    open_web, private, no_profile = lane.person("open"), lane.person("private"), lane.person("bare")
    lane.profile(open_web, public=True)
    lane.profile(private, public=False)
    for user in (open_web, private, no_profile):
        lane.check_in(user)
    result = here_now(lane.space, None)
    assert [p["handle"] for p in result["people"]] == ["open"]
    assert result["others_count"] == 2 and result["total"] == 3 and result["audience"] == "public"


def test_signed_in_sees_every_visible_profile(lane):
    a, b, hidden = lane.person("a"), lane.person("b"), lane.person("hidden")
    lane.profile(a)
    lane.profile(b, public=True)
    lane.profile(hidden, is_visible=False)
    for user in (a, b, hidden):
        lane.check_in(user)
    viewer = lane.person("viewer")
    result = here_now(lane.space, viewer)
    assert sorted(p["handle"] for p in result["people"]) == ["a-x", "b-x"]
    assert result["others_count"] == 1 and result["audience"] == "member"


def test_hidden_presence_is_counted_never_named_for_every_audience(lane):
    user = lane.person("shy")
    lane.profile(user, public=True)
    lane.check_in(user)
    update_preference(user, lane.space, True)
    for viewer in (None, lane.person("viewer")):
        result = here_now(lane.space, viewer)
        assert result["people"] == [] and result["others_count"] == 1


def test_space_that_hides_names_names_nobody(lane):
    user = lane.person("named")
    lane.profile(user, public=True)
    lane.check_in(user)
    update_settings(lane.staff, lane.space, {"show_names": False})
    assert here_now(lane.space, None)["people"] == []


def test_guest_and_minor_are_counted_only(lane, monkeypatch):
    guest, minor = lane.person("visitor", member=False), lane.person("kid")
    lane.profile(guest, public=True)
    lane.profile(minor, public=True)
    lane.check_in(minor)
    lane.check_in(guest, status="guest")
    monkeypatch.setattr("apps.presence.here_now._minor_ids", lambda space, ids: {minor.pk})
    result = here_now(lane.space, lane.person("viewer"))
    assert result["people"] == [] and result["total"] == 2


def test_section_toggles_shape_the_card(lane):
    user = lane.person("toggler")
    lane.profile(user, public=True, status="working", skills=[{"name": "Welding", "level": 2}],
                 show_status=False, show_skills=True)
    lane.check_in(user)
    card = here_now(lane.space, None)["people"][0]
    assert card["status"] is None and card["skills"] == ["Welding"]
    assert set(card) == {"handle", "display_name", "avatar_url", "headline", "status", "skills",
                         "presence_status", "since"}  # no account id, email or history


def test_restricted_account_is_not_shown(lane):
    user = lane.person("restricted")
    lane.profile(user, public=True)
    lane.check_in(user)
    user.access_status = "restricted"
    user.save(update_fields=["access_status"])
    assert _people(lane) == []


def test_http_endpoint_audience_and_module_off(lane):
    user = lane.person("open")
    lane.profile(user, public=True)
    lane.check_in(user)
    body = lane.client().get(URL).json()
    assert body["audience"] == "public" and len(body["people"]) == 1
    assert "no-store" in lane.client().get(URL)["Cache-Control"]
    lane.space.enabled_modules = [m for m in lane.space.enabled_modules if m != "presence"]
    lane.space.save(update_fields=["enabled_modules"])
    assert lane.client().get(URL).status_code == 404
