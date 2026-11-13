"""Registration edits, feedback starter designs and count projections honor staff/public boundaries."""

import pytest

from apps.audit.models import AuditLog
from apps.events import services
from apps.events.feedback_templates import FEEDBACK_TEMPLATES
from apps.events.models import EventFeedbackResponse, EventFeedbackSurvey, EventRegistration
from apps.events.serializers_public import PublicEventSerializer
from apps.events.serializers_registration_admin import EventRegistrationAdminSerializer
from tests.events.collab_helpers import client_for, make_staff
from tests.events.staff_grant_helpers import grant_fixture, set_grant_permissions
from tests.events.ticketing_helpers import account, event_space, open_event, public_url

pytestmark = pytest.mark.django_db

QUESTION = {"id": "experience", "label": "Experience", "type": "single_choice", "options": ["New", "Experienced"], "required": True}


def editable_registration(permission="manage_registrations"):
    space, staff, grantee, event, grant = grant_fixture(permission)
    event.custom_form = [QUESTION]; event.save(update_fields=["custom_form"])
    row = services.register(event, member=account("edit-owner"), actor=staff,
                            staff_registration=True, custom_answers={"experience": "New"})
    return space, staff, grantee, event, grant, row


def test_granted_registration_manager_edits_answers_through_the_existing_snapshot_validator():
    _, _, grantee, event, _, row = editable_registration()
    response = client_for(grantee).patch(f"/api/v1/admin/event-registrations/{row.pk}/answers/",
        {"custom_answers": {"experience": "Experienced"}}, format="json")
    assert response.status_code == 200, response.data
    row.refresh_from_db()
    assert row.custom_answers["answers"] == [{"id": "experience", "label": "Experience", "type": "single_choice", "value": "Experienced"}]
    assert row.status == "registered" and row.event_id == event.pk
    audit = AuditLog.objects.get(action="event.registration_answers_edited")
    assert audit.actor == grantee and audit.target_id == str(row.pk)
    assert "Experienced" not in str(audit.meta) and "experience" not in str(audit.meta)


@pytest.mark.parametrize("answers", [{}, {"experience": "Invalid"}, {"unexpected": "data"}, ["Experienced"]])
def test_invalid_answer_edit_is_atomic_and_does_not_emit_audit(answers):
    _, _, grantee, _, _, row = editable_registration()
    original = row.custom_answers
    response = client_for(grantee).patch(f"/api/v1/admin/event-registrations/{row.pk}/answers/",
                                        {"custom_answers": answers}, format="json")
    assert response.status_code == 400
    row.refresh_from_db(); assert row.custom_answers == original
    assert row.status == "registered" and not AuditLog.objects.filter(action="event.registration_answers_edited").exists()


@pytest.mark.parametrize("permission", ["edit_details", "check_in", "manage_invitations", "publish_schedule"])
def test_answer_edit_does_not_accept_other_event_grants(permission):
    _, _, grantee, _, _, row = editable_registration(permission)
    response = client_for(grantee).patch(f"/api/v1/admin/event-registrations/{row.pk}/answers/",
                                        {"custom_answers": {"experience": "Experienced"}}, format="json")
    assert response.status_code in (403, 404)


def test_answer_edit_rejects_status_reassignment_and_registration_creation_fields():
    _, _, grantee, _, _, row = editable_registration()
    response = client_for(grantee).patch(f"/api/v1/admin/event-registrations/{row.pk}/answers/",
        {"custom_answers": {"experience": "Experienced"}, "status": "attended", "member_id": 1}, format="json")
    assert response.status_code == 400 and "status" in response.data and "member_id" in response.data
    row.refresh_from_db(); assert row.status == "registered"


@pytest.mark.parametrize("template", list(FEEDBACK_TEMPLATES))
def test_each_static_template_requires_edit_details_and_audits_the_template_key(template):
    _, _, grantee, event, _ = grant_fixture("edit_details")
    response = client_for(grantee).post(f"/api/v1/admin/events/{event.pk}/feedback-survey/templates/",
                                       {"template": template}, format="json")
    assert response.status_code == 200, response.data
    survey = EventFeedbackSurvey.objects.get(event=event)
    title, questions = FEEDBACK_TEMPLATES[template]
    assert survey.title == title and survey.questions == questions
    assert not survey.is_open and not survey.responses.exists()
    assert AuditLog.objects.get(action="event.feedback_template_applied").meta == {"template": template}


def test_template_refuses_any_response_even_if_no_question_ids_have_been_marked_answered():
    _, _, grantee, event, _ = grant_fixture("edit_details")
    survey = EventFeedbackSurvey.objects.create(event=event, title="Existing", questions=[QUESTION])
    EventFeedbackResponse.objects.create(survey=survey, answers_snapshot='{"version":1,"answers":[]}', certificate_requested=False)
    response = client_for(grantee).post(f"/api/v1/admin/events/{event.pk}/feedback-survey/templates/",
                                       {"template": "quick_pulse"}, format="json")
    assert response.status_code == 409
    survey.refresh_from_db(); assert survey.title == "Existing" and survey.questions == [QUESTION]
    assert not AuditLog.objects.filter(action="event.feedback_template_applied").exists()


def test_templates_refuse_invalid_key_and_registration_only_authority():
    _, _, grantee, event, grant = grant_fixture("manage_registrations")
    url = f"/api/v1/admin/events/{event.pk}/feedback-survey/templates/"
    assert client_for(grantee).post(url, {"template": "quick_pulse"}, format="json").status_code in (403, 404)
    set_grant_permissions(grant, ["edit_details"])
    assert client_for(grantee).post(url, {"template": "unknown"}, format="json").status_code == 400
    assert not EventFeedbackSurvey.objects.exists()


@pytest.mark.parametrize("show", [True, False])
def test_registration_count_is_consistent_in_public_list_detail_and_serializer(show):
    space = event_space("lane-b-count")
    staff = make_staff(space)
    event = open_event(space, show_registration_count=show)
    row = services.register(event, member=account("count-owner"), actor=staff, staff_registration=True)
    services.register(event, member=account("count-other"), actor=staff, staff_registration=True)
    row.status = "attended"; row.save(update_fields=["status"])
    EventRegistration.objects.create(event=event, member=account("count-waiter"), name="Waiter",
        email="count-waiter@example.test", phone="1", status="waitlisted", registration_audience="accounts")
    expected = 2 if show else None
    assert PublicEventSerializer(event).data["registration_count"] == expected
    for route in ("public-event-list", "public-event-detail"):
        url = public_url(event, route) if route == "public-event-detail" else f"/api/v1/public/{space.slug}/events/"
        response = client_for(row.member).get(url)
        assert response.status_code == 200, response.data
        payload = response.data if route == "public-event-detail" else response.data[0]
        assert payload["show_registration_count"] is show and payload["registration_count"] == expected
        assert "registration_counts" not in payload and "registrations" not in payload


def test_staff_count_toggle_is_authorized_and_does_not_hide_staff_operational_counts():
    _, _, grantee, event, _ = grant_fixture("edit_details")
    response = client_for(grantee).patch(f"/api/v1/admin/events/{event.pk}/", {"show_registration_count": False}, format="json")
    assert response.status_code == 200 and response.data["show_registration_count"] is False
    assert response.data["registration_counts"]["registered"] == 0


def test_paid_and_consumed_cancellations_never_advertise_undo_to_staff():
    from apps.events.models import EventInvite
    _, staff, _, _, _, row = editable_registration()
    cancelled = services.cancel_registration(row, actor=staff)
    assert EventRegistrationAdminSerializer(cancelled).data["restore_until"] is not None
    invite = EventInvite.objects.create(event=row.event, makerspace=row.event.makerspace, uses=1)
    cancelled.invite = invite; cancelled.save(update_fields=["invite"])
    assert EventRegistrationAdminSerializer(cancelled).data["restore_until"] is None
