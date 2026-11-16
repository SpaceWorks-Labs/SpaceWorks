"""Decision 325a/b: per-screen settings, the public page config, privacy that only narrows, public stats panel."""
import pytest

from apps.audit.models import AuditLog
from apps.presence.display_config import apply_privacy

pytestmark = pytest.mark.django_db


def _admin(space, tail="presence-displays"):
    return f"/api/v1/admin/makerspace/{space.pk}/{tail}"


def _here(total=3):
    people = [{"handle": f"h{i}", "display_name": f"Ada Lovelace {i}", "avatar_url": "x", "headline": "Maker",
               "status": {"preset": "a", "note": "b"}, "skills": ["TIG"], "presence_status": "working", "since": "t"}
              for i in range(2)]
    return {"audience": "public", "people": people, "others_count": total - 2, "total": total}


def test_privacy_levels_only_narrow():
    data = _here()
    assert apply_privacy(data, "profiles") is data
    first = apply_privacy(data, "first_names")
    assert [p["display_name"] for p in first["people"]] == ["Ada", "Ada"]
    assert all(p["handle"] is None and p["avatar_url"] is None and p["skills"] == [] for p in first["people"])
    counts = apply_privacy(data, "counts")
    assert counts["people"] == [] and counts["others_count"] == 3 and counts["total"] == 3


def test_settings_roundtrip_validation_and_audit(lane):
    admin = lane.client(lane.staff)
    made = admin.post(_admin(lane.space, "presence-displays/link"), {"name": "Wall"}, format="json")
    assert made.status_code == 201
    body = made.json()
    assert (body["layout"], body["theme"], body["privacy"], body["refresh_seconds"]) == ("playlist", "dark", "profiles", 30)
    row = f"{_admin(lane.space)}/{body['id']}"
    ok = admin.patch(row, {"panels": ["public_stats", "opening_hours", "here_now"], "layout": "grid", "theme": "black",
                           "privacy": "counts", "refresh_seconds": 60, "slide_seconds": {"here_now": 12}}, format="json")
    assert ok.status_code == 200 and ok.json()["panels"][0] == "public_stats" and ok.json()["privacy"] == "counts"
    for bad in ({"layout": "wall"}, {"theme": "neon"}, {"privacy": "everyone"}, {"refresh_seconds": 5},
                {"slide_seconds": {"nope": 10}}, {"slide_seconds": {"here_now": 1}}, {"panels": ["x"]}):
        assert admin.patch(row, bad, format="json").status_code == 400, bad
    assert AuditLog.objects.filter(action="presence.display_updated", makerspace=lane.space).count() == 1


def test_screen_state_applies_privacy_and_new_panels(lane, settings):
    settings.PUBLIC_APP_BASE_URL = "https://spaces.example.test"  # the screen link is built from the public origin
    admin = lane.client(lane.staff)
    made = admin.post(_admin(lane.space, "presence-displays/link"),
                      {"panels": ["here_now", "opening_hours", "public_stats"], "privacy": "counts"}, format="json").json()
    token = made["url"].split("#k=")[1]
    lane.check_in(lane.person("walker"))
    state = lane.client().get(f"/api/v1/space-displays/{token}/state/").json()
    assert state["here_now"]["people"] == [] and state["config"]["privacy"] == "counts"
    assert state["here_now"]["total"] == 1
    assert "public_stats" in state and "opening_hours" in state


def test_now_config_staff_and_public(lane):
    admin = lane.client(lane.staff)
    url = _admin(lane.space, "presence-now-config")
    assert admin.get(url).json()["sections"] == ["here_now", "machines", "events"]
    put = admin.put(url, {"sections": ["events", "public_stats"], "privacy": "first_names", "refresh_seconds": 45}, format="json")
    assert put.status_code == 200 and put.json()["sections"] == ["events", "public_stats"]
    assert admin.put(url, {"sections": ["nope"]}, format="json").status_code == 400
    assert admin.put(url, {"sections": ["events", "events"]}, format="json").status_code == 400
    assert admin.put(url, {"refresh_seconds": 3}, format="json").status_code == 400
    public = lane.client().get(f"/api/v1/public/makerspaces/{lane.space.slug}/presence/now-config/")
    assert public.status_code == 200 and public.json()["privacy"] == "first_names"
    assert AuditLog.objects.filter(action="presence.now_config_updated").count() == 1


def test_public_here_now_honours_page_privacy(lane):
    admin = lane.client(lane.staff)
    admin.put(_admin(lane.space, "presence-now-config"), {"privacy": "counts"}, format="json")
    lane.check_in(lane.person("walker"))
    body = lane.client().get(f"/api/v1/public/makerspaces/{lane.space.slug}/presence/here-now/").json()
    assert body["people"] == [] and body["total"] == 1


def test_non_staff_cannot_change_settings(lane):
    member = lane.person("plain")
    assert lane.client(member).put(_admin(lane.space, "presence-now-config"), {"privacy": "counts"}, format="json").status_code in (403, 404)
