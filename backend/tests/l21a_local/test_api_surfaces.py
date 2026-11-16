"""L21a HTTP surfaces: switches, applications:read on/off, reviewer workspace isolation, stage email switch."""
from types import SimpleNamespace

import pytest
from django.urls import reverse

from apps.events.hackathons import admission_stage_review
from apps.events.hackathons.admission_stage_models import AdmissionStage, AdmissionStageReviewer
from apps.events.models import EventParticipationSettings
from apps.events import notices_r2_l21a
from tests.events.collab_helpers import client_for, make_event, make_member, make_space, make_staff

pytestmark = pytest.mark.django_db


def test_participation_switches_need_the_full_manager_and_default_off():
    space = make_space("switches")
    event = make_event(space, is_public=True)
    staff, member = make_staff(space), make_member(space, "sw-m")
    url = reverse("events-programme-admin-participation-settings", kwargs={"pk": event.pk})
    body = client_for(staff).get(url).json()
    assert body == {"stage_advanced_email": False, "attendance_free_on_no": False, "crew_signup_open": False,
                    "crew_approval_required": True, "crew_public_section": False}
    response = client_for(staff).patch(url, {"attendance_free_on_no": True}, format="json")
    assert response.status_code == 200 and response.json()["attendance_free_on_no"] is True
    assert client_for(member).patch(url, {"crew_signup_open": True}, format="json").status_code in (403, 404)
    assert EventParticipationSettings.objects.get(event=event).crew_signup_open is False


def test_review_workspace_reads_404_for_a_person_not_on_the_panel(monkeypatch):
    space = make_space("panel-iso")
    space.enabled_features = ["events.applications", "events.application_stages"]
    space.save(update_fields=["enabled_features"])
    event = make_event(space, is_public=True)
    reviewer, outsider = make_member(space, "rev-in"), make_member(space, "rev-out")
    stage = AdmissionStage.objects.create(event=event, position=1, name="Screen", state="open")
    AdmissionStageReviewer.objects.create(stage=stage, reviewer=reviewer)
    url = reverse("events-programme-admin-application-stage-my-reviews", kwargs={"pk": event.pk, "stage_id": stage.pk})
    assert client_for(outsider).get(url).status_code == 404
    ok = client_for(reviewer).get(url)
    assert ok.status_code == 200 and ok.json()["assignments"] == []
    mine = client_for(reviewer).get(reverse("events-programme-admin-my-application-reviews"))
    assert [row["id"] for row in mine.json()] == [stage.pk]
    assert client_for(outsider).get(reverse("events-programme-admin-my-application-reviews")).json() == []
    stage.state = "closed"
    stage.save(update_fields=["state"])
    assert admission_stage_review.my_stages(reviewer) == []
    # The panel seat opens nothing else of the event.
    roster = reverse("admin-event-registration-list", kwargs={"pk": event.pk})
    assert client_for(reviewer).get(roster).status_code in (403, 404)


def test_stage_advanced_email_is_sent_only_with_the_per_event_switch(monkeypatch):
    space = make_space("stage-mail")
    event = make_event(space, is_public=True)
    member = make_member(space, "stage-mail-m")
    sent = []
    monkeypatch.setattr(notices_r2_l21a, "_send", lambda *args, **kwargs: sent.append(kwargs) or "env")
    application = SimpleNamespace(pk=5, member_id=member.pk, version=2)
    stage = SimpleNamespace(name="Interview")
    assert notices_r2_l21a.stage_advanced_notice(event, application, stage) is None and not sent
    EventParticipationSettings.objects.create(makerspace=space, event=event, stage_advanced_email=True)
    assert notices_r2_l21a.stage_advanced_notice(event, application, stage) == "env"
    # The notice now hands _send a lazy `copy` callable returning (subject, body) so the text is rendered per recipient locale.
    text = " ".join(sent[0]["copy"]())
    assert "Interview" in text and "score" not in text.lower()


def test_applications_read_is_off_without_the_switches(monkeypatch):
    from apps.events.views_integration_applications import counts
    space = make_space("apps-read")
    event = make_event(space, is_public=True)
    result = counts(event)
    assert result["total"] == 0 and result["stages"] == [] and set(result["by_status"]) >= {"submitted", "offered"}
    assert "member" not in str(result) and "answers" not in str(result)


def test_reaccept_route_needs_manage_registrations():
    space = make_space("reaccept-route")
    event = make_event(space, is_public=True)
    member = make_member(space, "ra-m")
    from apps.events.models import EventRegistration
    row = EventRegistration.objects.create(event=event, member=member, name="m", email=member.email, phone="1",
                                           status="rejected")
    url = reverse("events-programme-admin-registration-reaccept", kwargs={"pk": event.pk, "registration_id": row.pk})
    assert client_for(member).post(url, {}, format="json").status_code in (403, 404)
    response = client_for(make_staff(space)).post(url, {}, format="json")
    assert response.status_code == 200 and response.json()["status"] == "registered"
