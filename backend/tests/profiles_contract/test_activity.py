from datetime import datetime, timedelta, UTC
import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.makerspaces.models import AccountProject as MemberProject, Makerspace
from apps.makerspaces.profile_activity_public import daily_activity
from apps.makerspaces.profile_services import save_profile
from apps.makerspaces import profile_activity_sources as sources

pytestmark = pytest.mark.django_db


def graph(profile, day=None):
    profile.refresh_from_db()
    return daily_activity(profile, {"from": day, "to": day} if day else {})


def enable(profile, **consents):
    save_profile(profile.membership, {"show_activity_graph": True, **consents})
    profile.refresh_from_db()


def test_graph_and_independent_family_consent(published):
    MemberProject.objects.create(profile=published, title="public project", public_visible=True)
    # Sections default ON (decision 303a), so switch the master and the family off explicitly first.
    save_profile(published.membership, {"show_activity_graph": False, "show_projects": False})
    assert graph(published)["days"] == []
    enable(published)
    assert sum(day["count"] for day in graph(published)["days"]) == 0
    enable(published, show_projects=True)
    days = graph(published)["days"]
    assert sum(day["count"] for day in days) == 1
    assert all(set(day) == {"date", "count", "families"} for day in days)
    assert all(set(day["families"]) <= {"projects"} for day in days)


def test_projects_same_day_dedup_timezone_update_and_private_exclusion(published):
    enable(published, show_projects=True)
    before = datetime(2026, 1, 1, 20, 0, tzinfo=UTC)  # Jan 2 in Kolkata
    project = MemberProject.objects.create(profile=published, title="No title in graph", public_visible=True)
    MemberProject.objects.filter(pk=project.pk).update(created_at=before, updated_at=before + timedelta(hours=1))
    MemberProject.objects.create(profile=published, title="Never public", public_visible=False)
    assert graph(published, "2026-01-02")["days"][0] == {
        "date": before.astimezone(__import__('zoneinfo').ZoneInfo("Asia/Kolkata")).date(),
        "count": 1, "families": {"projects": 1},
    }
    MemberProject.objects.filter(pk=project.pk).update(updated_at=before + timedelta(days=1))
    assert graph(published, "2026-01-03")["days"][0]["count"] == 1
    MemberProject.objects.filter(pk=project.pk).update(public_visible=False)
    assert graph(published, "2026-01-02")["days"][0]["count"] == 0


@pytest.mark.parametrize("params", [
    {"from": "2026-01-01", "to": "2026-05-01"},
    {"from": "2026-02-01", "to": "2026-01-01"},
    {"to": "9999-12-31"}, {"from": "bad"},
])
def test_window_boundaries(published, params):
    with pytest.raises(ValidationError):
        daily_activity(published, params)


def test_future_lanes_use_registration_and_never_run_without_consent(published, monkeypatch):
    monkeypatch.setattr(sources, "_sources", {key: value for key, value in sources._sources.items() if key != "speaking"})
    calls = []
    moment = timezone.now()
    def speaking(profile, start, end):
        calls.append(profile.pk)
        return [sources.ActivityMilestone("speaker:one", moment)] * 3
    sources.register_activity_source(sources.ActivitySource("speaking", "events", speaking))
    enable(published)
    graph(published)
    assert calls == []
    enable(published, show_speaking=True, show_bookings=True, show_loans=True)
    assert sum(day["count"] for day in graph(published)["days"]) == 1
    with pytest.raises(RuntimeError):
        sources.register_activity_source(sources.ActivitySource("speaking", "events", lambda *args: []))


def event_registration(profile, *, host=None, via=None, public=True):
    from apps.events.models import Event, EventRegistration, EventCheckInEvent
    moment = timezone.now() - timedelta(days=2)
    event = Event.objects.create(makerspace=host or profile.membership.makerspace, title="Safe event",
        starts_at=moment, ends_at=moment + timedelta(hours=2), status="published", is_public=public)
    registration = EventRegistration.objects.create(event=event, member=profile.membership.user,
        registered_via_makerspace=via, status="attended", name="Private name", email="private@example.test", phone="")
    for delta in [timedelta(), timedelta(minutes=1), timedelta(days=1)]:
        EventCheckInEvent.objects.create(makerspace=event.makerspace, event=event, registration=registration,
            source="online", actor=profile.membership.user, attended_at=moment + delta)
    return event, registration


def test_event_live_state_provenance_dedup_and_publication(published):
    from apps.events.models import EventRegistration
    enable(published, show_events=True)
    own = published.membership.makerspace
    host = Makerspace.objects.create(name="Host", slug="activity-host")
    _, registration = event_registration(published, host=host, via=own)
    event_registration(published, host=host)  # no provenance to this space
    event_registration(published, public=False)
    assert sum(day["count"] for day in graph(published)["days"]) == 1
    EventRegistration.objects.filter(pk=registration.pk).update(status="registered")
    assert sum(day["count"] for day in graph(published)["days"]) == 0
    EventRegistration.objects.filter(pk=registration.pk).update(status="attended")
    host.enabled_modules = []; host.save()
    assert sum(day["count"] for day in graph(published)["days"]) == 0


def test_completed_machine_jobs_use_member_ownership_only(published):
    from apps.machines.models import MachineType, ServiceQueue, MachineServiceRequest
    enable(published, show_machine_activity=True)
    space, user = published.membership.makerspace, published.membership.user
    kind = MachineType.objects.create(makerspace=space, name="Contract machine", slug="contract-machine")
    queue = ServiceQueue.objects.create(makerspace=space, machine_type=kind, name="Queue")
    for owner, status in [(user, "completed"), (None, "completed"), (user, "in_progress")]:
        MachineServiceRequest.objects.create(makerspace=space, requester=user, member=owner, queue=queue,
                                            title="Private job", status=status, completed_at=timezone.now())
    assert sum(day["count"] for day in graph(published)["days"]) == 1
    space.enabled_modules = ["membership"]; space.save()
    assert sum(day["count"] for day in graph(published)["days"]) == 0
