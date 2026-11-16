from tests.events.manual_grant_fixture import create_manual_grant
from datetime import timedelta
from types import SimpleNamespace

import pytest

from apps.events.models import Event, EventStaffGrant
from apps.makerspaces.profile_history_public import event_history

from .conftest import enable, make_event, public_get, registration

pytestmark = pytest.mark.django_db


def test_hosted_spoke_attended_badges_deduplicate_collaborative_event(published, moment, speaker_source):
    enable(published, show_events=True, show_speaking=True)
    event = make_event(published, moment, created_by=published.membership.user)
    registration(published, event)
    create_manual_grant(makerspace=event.makerspace, event=event, user=published.membership.user,
                                  permissions=["edit_details"])
    speaker_source.rows.extend([SimpleNamespace(event=event, occurred_at=moment, role="speaker")] * 3)
    rows = event_history(published)
    assert len(rows) == 1 and rows[0]["badge"] == "SPOKE"
    enable(published, show_speaking=False)
    assert event_history(published)[0]["badge"] == "HOSTED"
    EventStaffGrant.objects.filter(event=event).update(revoked_at=moment)
    Event.objects.filter(pk=event.pk).update(created_by=None)
    assert event_history(published)[0]["badge"] == "ATTENDED"
    response = public_get("events")
    assert response.status_code == 200 and response.data["count"] == 1
    assert set(response.data["results"][0]) == {"title", "starts_at", "ends_at", "badge", "host"}


def test_host_grant_is_personal_and_live(published, moment, other_user):
    enable(published, show_events=True)
    event = make_event(published, moment)
    grant = create_manual_grant(makerspace=event.makerspace, event=event,
        user=other_user, permissions=["edit_details"])
    assert not event_history(published)
    grant.user = published.membership.user; grant.save()
    assert event_history(published)[0]["badge"] == "HOSTED"
    grant.revoked_at = moment; grant.save()
    assert not event_history(published)


def test_checkin_only_speaker_grant_is_not_host_credit(published, moment):
    enable(published, show_events=True)
    event = make_event(published, moment)
    create_manual_grant(makerspace=event.makerspace, event=event, user=published.membership.user,
                                  permissions=["check_in"], role_label="speaker")
    assert not event_history(published)


def test_remote_host_requires_durable_participation_provenance(published, moment, other_space):
    enable(published, show_events=True)
    own = published.membership.makerspace
    event = make_event(published, moment, makerspace=other_space, created_by=published.membership.user)
    assert not event_history(published)
    registration(published, event, via=own)
    assert event_history(published)[0]["badge"] == "HOSTED"
    # No current collaboration is needed. History is based on registration provenance.
    other_space.enabled_modules = []; other_space.save()
    assert not event_history(published)


def test_attendance_correction_and_null_provenance_fallback(published, moment, other_space):
    from apps.events.models import EventRegistration
    enable(published, show_events=True)
    local = make_event(published, moment)
    row = registration(published, local)  # legacy NULL -> local host
    remote = make_event(published, moment, makerspace=other_space)
    registration(published, remote)  # NULL remote provenance cannot enter this history
    assert len(event_history(published)) == 1
    EventRegistration.objects.filter(pk=row.pk).update(status="registered")
    assert not event_history(published)


def test_events_and_speaking_consents_are_independent(published, moment, speaker_source):
    event = make_event(published, moment, created_by=published.membership.user)
    speaker_source.rows.append(SimpleNamespace(event=event, occurred_at=moment, role="session_speaker"))
    enable(published, show_events=False)  # sections default ON now (decision 303a): switch this one off first
    assert public_get("events").data["results"] == []
    enable(published, show_speaking=True)
    assert public_get("events").data["results"][0]["badge"] == "SPOKE"
    enable(published, show_speaking=False, show_events=True)
    assert public_get("events").data["results"][0]["badge"] == "HOSTED"
    assert len(speaker_source.calls) == 1


@pytest.mark.parametrize("values", [{"is_public": False}, {"status": "draft"}, {"status": "cancelled"}])
def test_private_or_unpublished_event_titles_never_appear(published, moment, values):
    enable(published, show_events=True)
    make_event(published, moment, title="Never expose", created_by=published.membership.user, **values)
    assert not event_history(published)


def test_event_pagination_is_stable(published, moment):
    enable(published, show_events=True)
    for index in range(25):
        make_event(published, moment + timedelta(minutes=index), title=f"Event {index}",
                   created_by=published.membership.user)
    response = public_get("events")
    assert response.data["count"] == 25 and len(response.data["results"]) == 24
    assert response.data["next"] and response.data["results"][0]["title"] == "Event 24"
