import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.makerspaces.models import Makerspace
from apps.presence import services
from apps.presence.display import tv_payload
from apps.presence.models import PresenceSettings
from apps.presence.privacy import update_preference, update_settings

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("show_names,opt_out,hide,named", [
    (False, False, False, False), (False, False, True, False),
    (False, True, False, False), (False, True, True, False),
    (True, False, False, True), (True, False, True, True),
    (True, True, False, True), (True, True, True, False),
])
def test_tv_privacy_matrix(lane, show_names, opt_out, hide, named):
    services.start_session(lane.owner, lane.space, 60, latitude=0, longitude=0,
        status="working", project_id=lane.project.pk, hide_on_display=hide)
    update_settings(lane.staff, lane.space, {"show_names": show_names, "allow_personal_opt_out": opt_out})
    payload = tv_payload(lane.space)
    assert len(payload) == 1
    assert payload[0]["display_name"] == (lane.owner.display_name if named else "A member")
    assert ("project_title" in payload[0]) is named
    assert set(payload[0]) <= {"display_name", "status", "project_title", "event_title", "since"}
    assert lane.owner.email not in str(payload)


def test_guest_anonymity_and_profile_independence(lane):
    lane.profile.public_visible = False
    lane.profile.save(update_fields=["public_visible"])
    services.start_session(lane.owner, lane.space, 60, latitude=0, longitude=0)
    services.start_session(lane.guest, lane.space, 60, latitude=0, longitude=0, hide_on_display=True)
    rows = tv_payload(lane.space)
    assert rows[0]["display_name"] == lane.owner.display_name
    assert rows[1]["display_name"] == "A guest"


def test_private_project_or_profile_never_projects_title(lane):
    services.start_session(lane.owner, lane.space, 60, latitude=0, longitude=0,
                           status="working", project_id=lane.project.pk)
    assert tv_payload(lane.space)[0]["project_title"] == "Public rover"
    lane.project.public_visible = False
    lane.project.save(update_fields=["public_visible"])
    assert "project_title" not in tv_payload(lane.space)[0]
    lane.project.public_visible = True
    lane.project.save(update_fields=["public_visible"])
    assert tv_payload(lane.space)[0]["project_title"] == "Public rover"
    lane.profile.public_visible = False
    lane.profile.save(update_fields=["public_visible"])
    assert "project_title" not in tv_payload(lane.space)[0]


def test_cache_generations_and_personal_preference(lane):
    row = services.start_session(lane.owner, lane.space, 60, latitude=0, longitude=0,
        status="working", project_id=lane.project.pk)
    def version():
        return PresenceSettings.objects.get(makerspace=lane.space).display_version
    first = version()
    tv_payload(lane.space)
    update_preference(lane.owner, lane.space, True)
    assert version() != first and tv_payload(lane.space)[0]["display_name"] == "A member"
    second = version()
    lane.project.public_visible = False
    lane.project.save(update_fields=["public_visible"])
    assert version() != second
    third = version()
    services.renew_session(lane.owner, lane.space, 120)
    assert version() != third
    fourth = version()
    services.end_session(lane.owner, lane.space)
    assert version() != fourth and tv_payload(lane.space) == []


def test_shared_cache_key_has_no_viewer_identity(lane, monkeypatch):
    services.start_session(lane.owner, lane.space, 60, latitude=0, longitude=0)
    keys = []
    monkeypatch.setattr("apps.presence.cache.read", lambda key: keys.append(key))
    tv_payload(lane.space)
    tv_payload(lane.space)
    assert keys[0] == keys[1]
    assert keys[0].startswith(f"presence:tv:{lane.space.pk}:")


def test_cache_hit_skips_recompute_until_generation_bumps(lane):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    services.start_session(lane.owner, lane.space, 60, latitude=0, longitude=0)
    first = tv_payload(lane.space)
    with CaptureQueriesContext(connection) as queries:
        assert tv_payload(lane.space) == first
    assert not any("presence_presencesession" in q["sql"] for q in queries.captured_queries)
    update_settings(lane.staff, lane.space, {"show_names": False, "allow_personal_opt_out": True})
    assert tv_payload(lane.space)[0]["display_name"] == "A member"


def test_cache_outage_serves_live_safe_projection(lane, monkeypatch):
    services.start_session(lane.owner, lane.space, 60, latitude=0, longitude=0, hide_on_display=True)
    def fail(*args, **kwargs):
        raise RuntimeError("Cache unavailable")
    monkeypatch.setattr(cache, "get", fail)
    monkeypatch.setattr(cache, "set", fail)
    assert tv_payload(lane.space)[0]["display_name"] == "A member"


def test_tv_anonymous_and_staff_preview_headers(lane):
    services.start_session(lane.owner, lane.space, 60, latitude=0, longitude=0)
    path = f"/api/v1/public/makerspaces/{lane.space.slug}/presence/now/"
    public = lane.client().get(path)
    assert public.status_code == 200
    assert public.data[0]["status"] == "visiting"
    assert "max-age=0" in public["Cache-Control"]
    staff = lane.client(lane.staff).get(path)
    assert staff.status_code == 200 and staff["Cache-Control"] == "no-store"


def test_tv_checks_origin_module_and_servability_before_cache(lane):
    path = f"/api/v1/public/makerspaces/{lane.space.slug}/presence/now/"
    assert lane.client().get(path, HTTP_ORIGIN="https://evil.example").status_code == 403
    assert lane.client().get(path).status_code == 200
    lane.space.enabled_modules.remove("presence")
    lane.space.save(update_fields=["enabled_modules"])
    assert lane.client().get(path).status_code == 404
    lane.space.enabled_modules.append("presence")
    lane.space.archived_at = timezone.now()
    lane.space.save(update_fields=["enabled_modules", "archived_at"])
    assert lane.client().get(path).status_code == 404


def test_member_api_boundaries_and_projects(lane):
    prefix = f"/api/v1/public/{lane.space.slug}/presence-sessions"
    api = lane.client(lane.owner)
    missing = api.post(prefix, {"duration_minutes": 60}, format="json")
    assert missing.status_code == 400 and missing.data["code"] == "location_required"
    checked = api.post(prefix, {"duration_minutes": 60, "latitude": 0, "longitude": 0}, format="json")
    assert checked.status_code == 201 and checked.data["names_displayed"] is True
    assert api.get(prefix + "/current").data["presets"] == [60, 120, 180, 240]
    assert api.get(prefix + "/projects").data["results"][0]["id"] == lane.project.pk
    changed = api.patch(prefix + "/preferences", {"hide_on_display": True}, format="json")
    assert changed.status_code == 200
    assert api.post(prefix + "/current/renew", {"duration_minutes": 120}, format="json").status_code == 200
    assert api.post(prefix + "/current/end").status_code == 200


def test_staff_apis_scope_accounts_roster_and_privacy(lane):
    api = lane.client(lane.staff)
    prefix = f"/api/v1/admin/makerspace/{lane.space.pk}/presence-sessions"
    # An account-only guest is not on this roster: staff cannot record it (no
    # cross-tenant probing by numeric id); the guest self-checks-in instead.
    assert api.post(prefix + "/check-in", {"account_id": lane.guest.pk, "duration_minutes": 60}, format="json").status_code == 404
    services.start_session(lane.guest, lane.space, 60, latitude=0, longitude=0)
    assert api.post(prefix + "/check-in", {"account_id": lane.owner.pk, "duration_minutes": 60}, format="json").status_code == 201
    roster = api.get(prefix + "/current")
    assert roster.status_code == 200 and {r["status"] for r in roster.data["results"]} == {"guest", "visiting"}
    assert lane.guest.email not in str(roster.data)
    assert api.patch(prefix + "/privacy", {"show_names": False}, format="json").status_code == 200
    assert api.post(prefix + "/check-out", {"account_id": lane.guest.pk}, format="json").status_code == 200
    foreign = Makerspace.objects.create(name="Other", slug="other-tv", enabled_modules=["presence"])
    stranger = lane.person("stranger", target=foreign)
    assert api.post(prefix + "/check-in", {"account_id": stranger.pk, "duration_minutes": 60}, format="json").status_code == 404
    assert api.post(prefix + "/check-out", {"account_id": stranger.pk}, format="json").status_code == 404
    assert api.get(f"/api/v1/admin/makerspace/{foreign.pk}/presence-sessions/current").status_code == 404
    assert lane.client(lane.owner).patch(prefix + "/privacy", {"show_names": False}, format="json").status_code in {403, 404}


def test_strict_inputs_refuse_event_assignment_and_unknown_fields(lane):
    prefix = f"/api/v1/public/{lane.space.slug}/presence-sessions"
    api = lane.client(lane.owner)
    for extra in ({"status": "attending_event"}, {"event_registration_id": 1}):
        assert api.post(prefix, {"duration_minutes": 60, **extra}, format="json").status_code == 400
    from apps.presence.serializers import PresenceStartSerializer
    assert not PresenceStartSerializer(data={"duration_minutes": 60, "latitude": float("inf")}).is_valid()


def test_tv_is_throttled(lane, monkeypatch):
    monkeypatch.setattr("apps.presence.views_public.PresenceTVThrottle.rate", "1/minute")
    path = f"/api/v1/public/makerspaces/{lane.space.slug}/presence/now/"
    client = lane.client()
    assert client.get(path).status_code == 200
    assert client.get(path).status_code == 429
