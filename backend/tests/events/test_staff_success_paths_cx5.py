"""Direct success and least-authority proofs for the event surfaces missed by MOD-2."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events import services
from apps.events.models import EventPage, EventRegistration, EventSpeaker
from tests.events.collab_helpers import client_for, make_member
from tests.events.ticketing_helpers import account, event_space
from tests.events.staff_grant_helpers import grant_fixture, set_grant_permissions
from tests.events.test_staff_surface_conditions_mod2b import world
from tests.events.website_helpers import session
from tests.refusal_helpers_mod2b import field_error, refused

pytestmark = pytest.mark.django_db
API = "/api/v1/admin"


@pytest.mark.parametrize("role", ["space_manager", "manual_delegate"])
def test_website_content_and_delay_round_trip_with_one_audit_each(role):
    space, manager, organizer, event, grant = grant_fixture(slug="cx5-web")
    set_grant_permissions(grant, ["edit_details", "publish_schedule"])
    space.enabled_features = sorted({*space.enabled_features, "events.website"})
    space.save(update_fields=["enabled_features"])
    api = client_for(manager if role == "space_manager" else organizer)
    url = f"{API}/events/{event.pk}/website/"
    initial = api.get(url)
    assert initial.status_code == 200 and initial.json()["revision"] == 0
    data = {"revision": 0, "sections": [], "sessions": [session(event)]}
    saved = api.put(url, data, format="json")
    assert saved.status_code == 200, saved.content
    revision = saved.json()["revision"]
    assert len(saved.json()["sessions"]) == 1
    assert AuditLog.objects.filter(makerspace=space, action="event.website_saved").count() == 1
    delayed = api.post(url + "sessions/talk/delay/", {"revision": revision, "delay_minutes": 1440}, format="json")
    assert delayed.status_code == 200, delayed.content
    row = delayed.json()["sessions"][0]
    assert row["delay_minutes"] == 1440 and delayed.json()["revision"] == revision + 1
    assert EventPage.objects.get(event=event).sessions.get().delay_minutes == 1440
    assert AuditLog.objects.filter(makerspace=space, action="event.website_delay_changed").count() == 1
    stale = api.post(url + "sessions/talk/delay/", {"revision": revision, "delay_minutes": 0}, format="json")
    field_error(stale, "revision", "invalid")
    assert AuditLog.objects.filter(makerspace=space, action="event.website_delay_changed").count() == 1


@pytest.mark.parametrize("role", ["space_manager", "manual_delegate"])
def test_speaker_invite_candidates_and_remove_use_live_event_authority(role):
    space, manager, organizer, event, grant = grant_fixture(slug="cx5-speaker")
    api = client_for(manager if role == "space_manager" else organizer)
    url = f"{API}/events/{event.pk}/speakers/"
    invited = api.post(url + "invite/", {"display_name": "???? ??"}, format="json")
    assert invited.status_code == 201, invited.content
    speaker = EventSpeaker.objects.get(pk=invited.json()["speaker"]["id"])
    assert speaker.claim_token_digest and speaker.display_name == "???? ??"
    assert speaker.claim_token_digest not in invited.content.decode()
    candidate = make_member(space, "needlecx5-eligible")
    candidate.first_name, candidate.last_name = "CX5 Candidate", "Eligible"
    candidate.save(update_fields=["first_name", "last_name"])
    foreign = make_member(event_space("cx5-candidate-foreign"), "needlecx5-foreign")
    inactive = make_member(space, "needlecx5-inactive")
    inactive.is_active = False
    inactive.save(update_fields=["is_active"])
    unrelated = account("needlecx5-unrelated")
    make_member(space, "different-search")
    found = api.get(f"{API}/events/{event.pk}/speaker-candidates/?search=needlecx5")
    assert found.status_code == 200, found.content
    assert found.json() == {"results": [{"id": candidate.pk, "display_name": "CX5 Candidate Eligible",
                                         "username": candidate.username, "relation": "member"}]}
    assert len(found.json()["results"]) == 1
    assert {foreign.pk, inactive.pk, unrelated.pk}.isdisjoint(row["id"] for row in found.json()["results"])
    remove = f"{API}/event-speakers/{speaker.pk}/remove/"
    result = api.post(remove, {}, format="json")
    assert result.status_code == 200 and result.json()["status"] == "removed"
    replay = api.post(remove, {}, format="json")
    assert replay.status_code == 200 and replay.json()["status"] == "removed"
    for action in ("event.speaker_invited", "event.speaker_removed"):
        assert AuditLog.objects.filter(makerspace=space, action=action, target_id=str(speaker.pk)).count() == 1
    # A revoke takes effect immediately, even on the same authenticated APIClient.
    grant.revoked_at = timezone.now()
    grant.save(update_fields=["revoked_at"])
    if role == "manual_delegate":
        refused(api.post(url + "invite/", {"display_name": "After revoke"}, format="json"), 404, "not_found")
        assert EventSpeaker.objects.filter(event=event).count() == 1


@pytest.mark.parametrize("role", ["space_manager", "manual_delegate"])
def test_registration_answers_and_restore_keep_the_same_row_and_audit_once(role):
    space, manager, organizer, event, grant = grant_fixture(slug="cx5-answers")
    set_grant_permissions(grant, ["manage_registrations"])
    event.custom_form = [{"id": "purpose", "label": "Purpose", "type": "short_text",
                          "options": [], "required": True}]
    event.save(update_fields=["custom_form"])
    registration = services.register(event, member=organizer, actor=manager, staff_registration=True,
                                     custom_answers={"purpose": "Original answer"})
    registration.refresh_from_db()
    assert registration.custom_answers == {"version": 1, "answers": [{
        "id": "purpose", "label": "Purpose", "type": "short_text", "value": "Original answer"}]}
    initial_version = registration.version
    api = client_for(manager if role == "space_manager" else organizer)
    url = f"{API}/event-registrations/{registration.pk}"
    audits = AuditLog.objects.filter(makerspace=space, action="event.registration_answers_edited",
        target_type="events.eventregistration", target_id=str(registration.pk))
    assert audits.count() == 0
    saved = api.patch(url + "/answers/", {"custom_answers": {"purpose": "Build a robot"}}, format="json")
    assert saved.status_code == 200, saved.content
    expected = {"version": 1, "answers": [{"id": "purpose", "label": "Purpose",
                                         "type": "short_text", "value": "Build a robot"}]}
    registration.refresh_from_db()
    assert registration.custom_answers == expected
    assert saved.json()["custom_answers"] == expected
    assert registration.version == initial_version + 1
    assert audits.count() == 1
    invalid = api.patch(url + "/answers/", {"custom_answers": {}}, format="json")
    assert invalid.status_code == 400, invalid.content
    assert invalid.data["custom_answers"]["purpose"].code == "invalid"
    registration.refresh_from_db()
    assert registration.custom_answers == expected and registration.version == initial_version + 1
    assert audits.count() == 1
    services.cancel_registration(registration, actor=manager)
    restored = api.post(url + "/restore/", {}, format="json")
    assert restored.status_code == 200, restored.content
    registration.refresh_from_db()
    assert registration.status == "registered" and registration.cancelled_at is None
    refused(api.post(url + "/restore/", {}, format="json"), 409, "not_cancelled")
    assert EventRegistration.objects.filter(event=event, member=organizer).count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="event.registration_restored",
                                   target_id=str(registration.pk)).count() == 1


def test_restore_refuses_exactly_at_the_five_minute_deadline(monkeypatch):
    w = world("cx5-restore-boundary")
    services.cancel_registration(w.registration, actor=w.staff)
    w.registration.refresh_from_db()
    deadline = w.registration.cancelled_at + timedelta(minutes=5)
    monkeypatch.setattr("apps.events.services_registration_tools.timezone.now", lambda: deadline)
    response = client_for(w.staff).post(f"{API}/event-registrations/{w.registration.pk}/restore/", {}, format="json")
    refused(response, 409, "window_expired")
    w.registration.refresh_from_db()
    assert w.registration.status == "cancelled"
    assert not AuditLog.objects.filter(makerspace=w.space, action="event.registration_restored").exists()


def test_series_collaborator_replace_and_pass_type_changes_are_audited_exactly():
    w = world("cx5-series")
    api = client_for(w.staff)
    url = f"{API}/event-series/{w.series.pk}"
    from tests.events.ticketing_helpers import event_space
    partner = event_space("cx5-series-partner")
    response = api.put(url + "/collaborators/", {"slugs": [partner.slug]}, format="json")
    assert response.status_code == 200, response.content
    assert w.series.collaborators.filter(makerspace=partner, status="invited").count() == 1
    assert AuditLog.objects.filter(makerspace=w.space, action="event.series_collaborators_changed",
                                   target_id=str(w.series.pk)).count() == 1
    created = api.post(url + "/pass-types/", {"name": "????? ??", "amount": "10.000"}, format="json")
    assert created.status_code == 201, created.content
    pk = created.json()["id"]
    patched = api.patch(f"{API}/event-pass-types/{pk}/", {"capacity": 1}, format="json")
    assert patched.status_code == 200 and patched.json()["capacity"] == 1
    assert AuditLog.objects.filter(makerspace=w.space, action="event.pass_type_saved", target_id=str(pk)).count() == 2


def test_report_switch_off_on_changes_effective_policy_keeps_data_and_noop_does_not_audit():
    w = world("cx5-report-switch")
    w.space.enabled_modules = sorted({*w.space.enabled_modules, "reports"})
    w.space.enabled_features = [key for key in w.space.enabled_features if key != "reports.event_pdf"]
    w.space.save(update_fields=["enabled_modules", "enabled_features"])
    api = client_for(w.staff)
    url = f"{API}/makerspaces/{w.space.pk}/events/report-switches/"
    for value in (True, False, True):
        result = api.patch(url, {"switches": {"reports.event_pdf": value}}, format="json")
        assert result.status_code == 200, result.content
        state = next(row for row in result.json()["switches"] if row["key"] == "reports.event_pdf")
        assert state["enabled"] is value and state["effective"] is value
        assert EventRegistration.objects.filter(pk=w.registration.pk).exists()
    audits = AuditLog.objects.filter(makerspace=w.space, action="settings.changed")
    assert audits.count() == 3
    again = api.patch(url, {"switches": {"reports.event_pdf": True}}, format="json")
    assert again.status_code == 200 and audits.count() == 3


def test_speaker_remove_refuses_signed_out_member_foreign_and_module_off_then_recovers():
    from rest_framework.test import APIClient
    from tests.events.test_staff_surface_conditions_mod2b import set_events_module
    w = world("cx5-speaker-remove-gates")
    api = client_for(w.staff)
    assigned = api.post(f"{API}/events/{w.event.pk}/speakers/", {"user_id": w.attendee.pk}, format="json")
    assert assigned.status_code == 201, assigned.content
    pk = assigned.json()["id"]
    url = f"{API}/event-speakers/{pk}/remove/"
    refused(APIClient().post(url, {}, format="json"), 401, "not_authenticated")
    refused(client_for(w.plain).post(url, {}, format="json"), 403, "permission_denied")
    refused(client_for(w.outsider).post(url, {}, format="json"), 404, "not_found")
    set_events_module(w.space, False)
    refused(api.post(url, {}, format="json"), 404, "module_disabled")
    assert EventSpeaker.objects.get(pk=pk).removed_at is None
    assert not AuditLog.objects.filter(makerspace=w.space, action="event.speaker_removed").exists()
    set_events_module(w.space, True)
    removed = api.post(url, {}, format="json")
    assert removed.status_code == 200 and removed.json()["status"] == "removed"
    assert AuditLog.objects.filter(makerspace=w.space, action="event.speaker_removed", target_id=str(pk)).count() == 1
