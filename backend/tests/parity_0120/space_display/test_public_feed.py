"""Decision 307a: machines now never expose who; the calendar lists only public, listed events."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.models import Event
from apps.machines.models import Machine
from apps.presence.public_feed import calendar_events, machines_now

pytestmark = pytest.mark.django_db


def _event(lane, title, **values):
    start = values.pop("starts_at", timezone.now() + timedelta(days=1))
    return Event.objects.create(
        makerspace=lane.space, title=title, status=values.pop("status", "published"),
        starts_at=start, ends_at=values.pop("ends_at", start + timedelta(hours=2)),
        is_public=values.pop("is_public", True), **values)


def test_machines_now_buckets_and_never_names_people(lane):
    lane.machine("Prusa", Machine.Status.RUNNING)
    lane.machine("Ender", Machine.Status.IDLE)
    lane.machine("Laser", Machine.Status.MAINTENANCE)
    hidden = lane.machine("Secret", Machine.Status.IDLE)
    Machine.objects.filter(pk=hidden.pk).update(is_public=False)
    result = machines_now(lane.space)
    assert (result["in_use"], result["free"], result["out_of_service"]) == (1, 1, 1)
    assert {i["name"] for i in result["items"]} == {"Prusa", "Ender", "Laser"}
    assert all(set(i) == {"name", "type", "status"} for i in result["items"])


def test_machines_module_off_is_404_and_none(lane):
    lane.space.enabled_modules = [m for m in lane.space.enabled_modules if m != "machines"]
    lane.space.save(update_fields=["enabled_modules"])
    assert machines_now(lane.space) is None
    assert lane.client().get("/api/v1/public/makerspaces/display-lane/machines/now/").status_code == 404


def test_calendar_lists_only_public_listed_published_events(lane):
    _event(lane, "Open night")
    _event(lane, "Private", is_public=False)
    _event(lane, "Draft", status="draft")
    _event(lane, "Unlisted", listing=Event.Listing.UNLISTED)
    month = (timezone.now() + timedelta(days=1)).astimezone(timezone.get_current_timezone()).strftime("%Y-%m")
    titles = [e["title"] for e in calendar_events(lane.space, month)["events"]]
    assert "Open night" in titles
    assert not {"Private", "Draft", "Unlisted"} & set(titles)


def test_live_card_marks_the_running_event(lane):
    now = timezone.now()
    _event(lane, "On now", starts_at=now - timedelta(minutes=10), ends_at=now + timedelta(minutes=50))
    result = calendar_events(lane.space, now=now)
    assert [e["title"] for e in result["live"]] == ["On now"]
    assert set(result["events"][0]) == {"token", "title", "starts_at", "ends_at", "location", "delivery_mode", "live"}


def test_calendar_module_off_is_none(lane):
    lane.space.enabled_modules = [m for m in lane.space.enabled_modules if m != "events"]
    lane.space.save(update_fields=["enabled_modules"])
    assert calendar_events(lane.space) is None


def test_display_state_matches_logged_out_view(lane):
    """A paired display never carries more than the anonymous projection: same keys, no viewer data."""
    token = lane.client().post("/api/v1/space-displays/register/").json()
    code = token["code"]
    lane.client(lane.staff).post(f"/api/v1/admin/makerspace/{lane.space.pk}/presence-displays",
                                 {"code": code, "panels": ["here_now", "machines", "calendar"]}, format="json")
    user = lane.person("someone")
    lane.profile(user, public=False)
    lane.check_in(user)
    state = lane.client().get(f"/api/v1/space-displays/{token['token']}/state/").json()
    assert state["here_now"]["people"] == [] and state["here_now"]["others_count"] == 1
    assert state["here_now"]["audience"] == "public"
