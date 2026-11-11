"""G36 anonymous feedback: per-form switch, certificates off only, no person link, switch on/off."""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.events.feedback_modes import feedback_mode, submit_member_feedback
from apps.events.models import EventFeedbackResponse, EventFeedbackSurvey, EventRegistration
from apps.events.services_feedback import configure_survey, submit_anonymous_feedback
from apps.events.services_registration import register
from tests.events.collab_helpers import make_staff
from tests.events.ticketing_helpers import account, event_space, open_event
from tests.l2_local.helpers import off, on

pytestmark = pytest.mark.django_db
QUESTIONS = [{"id": "q1", "label": "Rating", "type": "single_choice", "options": ["Good", "Bad"], "required": True}]


def finished(slug):
    space = event_space(slug)
    staff = make_staff(space)
    event = open_event(space)
    member = account(f"{slug}-member")
    row = register(event, member=member, actor=member)
    past = timezone.now() - timedelta(hours=3)
    type(event).objects.filter(pk=event.pk).update(starts_at=past, ends_at=past + timedelta(hours=1))
    EventRegistration.objects.filter(pk=row.pk).update(status="attended")
    event.refresh_from_db()
    return space, staff, member, event


def opened(survey):
    EventFeedbackSurvey.objects.filter(pk=survey.pk).update(is_open=True)
    survey.refresh_from_db()
    return survey


def test_anonymous_needs_the_switch_and_no_certificates():
    space, staff, _member, event = finished("anon-config")
    off(space, "events.anonymous_feedback")
    with pytest.raises(ValidationError):
        configure_survey(event, actor=staff, title="T", questions=QUESTIONS, anonymous=True)
    on(space, "events.anonymous_feedback")
    with pytest.raises(ValidationError):
        configure_survey(event, actor=staff, title="T", questions=QUESTIONS, certificate_enabled=True, anonymous=True)
    survey = configure_survey(event, actor=staff, title="T", questions=QUESTIONS, anonymous=True)
    assert survey.anonymous and AuditLog.objects.filter(action="event.feedback_anonymous_enabled").exists()


def test_anonymous_rows_have_no_person_and_the_audit_has_no_actor():
    space, staff, _member, event = finished("anon-submit")
    on(space, "events.anonymous_feedback")
    survey = opened(configure_survey(event, actor=staff, title="T", questions=QUESTIONS, anonymous=True))
    response, certificate = submit_anonymous_feedback(event, {"q1": "Good"})
    assert response.registration_id is None and certificate is None
    audit = AuditLog.objects.filter(action="event.feedback_submitted").latest("pk")
    assert audit.actor_id is None and audit.meta == {"mode": "anonymous"}
    assert not {field.name for field in EventFeedbackResponse._meta.fields} & {"ip", "ip_address", "user", "member"}
    assert feedback_mode(survey) == "anonymous"


def test_switch_off_closes_an_anonymous_form_instead_of_identifying_people():
    space, staff, _member, event = finished("anon-off")
    on(space, "events.anonymous_feedback")
    survey = opened(configure_survey(event, actor=staff, title="T", questions=QUESTIONS, anonymous=True))
    off(space, "events.anonymous_feedback")
    survey.refresh_from_db()
    assert feedback_mode(survey) == "unavailable"
    from django.urls import reverse
    url = reverse("public-event-feedback", kwargs={"makerspace_slug": space.slug, "public_token": event.public_token})
    assert APIClient().post(url, {"answers": {"q1": "Good"}}, format="json").status_code == 404


def test_identified_mode_links_the_registration_without_a_certificate():
    space, staff, member, event = finished("identified")
    off(space, "events.anonymous_feedback")
    survey = opened(configure_survey(event, actor=staff, title="T", questions=QUESTIONS, anonymous=False))
    assert feedback_mode(survey) == "identified"
    from tests.events.collab_helpers import make_member
    make_member(space, user=member)
    response, certificate = submit_member_feedback(event, actor=member, answers={"q1": "Bad"})
    assert response.registration.member_id == member.pk and not response.certificate_requested
    assert certificate is None
