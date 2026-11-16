"""Exercise real staff routes for each of the five independent permissions."""

from datetime import timedelta
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.events.event_permissions import PERMISSIONS
from apps.events.models import EventFeedbackResponse, EventFeedbackSurvey, EventInvite, EventRegistration
from apps.events.services import mark_attended
from apps.events.services_certificates import create_pending
from apps.events.services_checkin_roster import issue_roster
from tests.events.collab_helpers import client_for
from tests.events.staff_grant_helpers import grant_fixture
from tests.events.ticketing_helpers import account
from tests.events.test_image import mock_public_storage

pytestmark = pytest.mark.django_db

OPERATIONS = [
    ("edit_details", "patch", "admin-event-detail"),
    ("edit_details", "get", "admin-event-badge-template"),
    ("edit_details", "put", "admin-event-badge-template"),
    ("edit_details", "get", "admin-event-feedback-survey"),
    ("edit_details", "put", "admin-event-feedback-survey"),
    ("edit_details", "post", "admin-event-feedback-survey-open"),
    ("edit_details", "post", "admin-event-feedback-survey-close"),
    ("edit_details", "post", "admin-event-image"),
    ("edit_details", "put", "admin-event-image"),
    ("edit_details", "delete", "admin-event-image"),
    ("manage_registrations", "get", "admin-event-registration-list"),
    ("manage_registrations", "post", "admin-event-registration-list"),
    ("manage_registrations", "get", "admin-event-eligible-members"),
    ("manage_registrations", "post", "admin-event-registration-approve"),
    ("manage_registrations", "post", "admin-event-registration-reject"),
    ("manage_registrations", "post", "admin-event-registration-promote"),
    ("manage_registrations", "post", "admin-event-registration-cancel"),
    ("manage_registrations", "get", "admin-event-feedback-responses"),
    ("manage_registrations", "get", "admin-event-tickets"),
    ("manage_invitations", "get", "admin-event-invites"),
    ("manage_invitations", "post", "admin-event-invites"),
    ("manage_invitations", "post", "admin-event-invite-revoke"),
    ("check_in", "post", "admin-event-registration-mark-attended"),
    ("check_in", "post", "admin-event-registration-correct-attendance"),
    ("check_in", "post", "admin-event-check-in-resolve"),
    ("check_in", "get", "admin-event-check-in-offline-roster"),
    ("check_in", "post", "admin-event-check-in-offline-sync"),
    ("check_in", "post", "admin-event-badges-pdf"),
    ("publish_schedule", "post", "admin-event-publish"),
    ("publish_schedule", "post", "admin-event-cancel"),
    ("publish_schedule", "post", "admin-event-complete"),
]
QUESTIONS = [{"id": "experience", "label": "How was it?", "type": "short_text", "required": False, "options": []}]


@pytest.mark.parametrize("held", PERMISSIONS)
@pytest.mark.parametrize("required,method,route", OPERATIONS)
def test_each_permission_allows_its_operations_and_denies_every_other(held, required, method, route, monkeypatch):
    space, manager, user, event, _ = grant_fixture(held)
    attendee = account("matrix-attendee")
    registration = EventRegistration.objects.create(
        event=event, member=attendee, name="Attendee", email=attendee.email, phone=attendee.phone,
    )
    data = {}
    target = event.pk
    if route == "admin-event-detail":
        data = {"title": "Updated by event staff"}
    elif route.startswith("admin-event-registration-") and route != "admin-event-registration-list":
        target = registration.pk
        if route.endswith(("approve", "reject", "promote")):
            registration.status = "waitlisted" if route.endswith("promote") else "pending_approval"
            event.registration_requires_approval = True
            event.save(update_fields=["registration_requires_approval"])
        elif route.endswith("correct-attendance"):
            registration = mark_attended(registration, actor=manager)
        registration.save(update_fields=["status"])
    elif route == "admin-event-registration-list" and method == "post":
        other_attendee = account("matrix-new-attendee")
        data = {"member_id": other_attendee.pk}
    elif route == "admin-event-feedback-responses":
        EventFeedbackSurvey.objects.create(event=event, title="Feedback", questions=QUESTIONS)
    elif route.startswith("admin-event-feedback-survey"):
        if method == "put":
            data = {"title": "Survey", "questions": QUESTIONS}
        elif route.endswith(("open", "close")):
            event.starts_at = timezone.now() - timedelta(hours=2)
            event.ends_at = timezone.now() - timedelta(hours=1)
            event.save(update_fields=["starts_at", "ends_at"])
            EventFeedbackSurvey.objects.create(event=event, title="Survey", questions=QUESTIONS, is_open=route.endswith("close"))
    elif route == "admin-event-image":
        mock_public_storage(monkeypatch)
        data = {"content_type": "image/png", "filename": "poster.png"} if method == "post" else {}
        if method in ("put", "delete"):
            upload = client_for(manager).post(reverse(route, args=[event.pk]), {"content_type": "image/png", "filename": "poster.png"}, format="json")
            assert upload.status_code == 201
            data = {"object_key": upload.data["object_key"]} if method == "put" else {}
            if method == "delete":
                event.image_key = upload.data["object_key"]
                event.save(update_fields=["image_key"])
    elif route == "admin-event-invite-revoke":
        invitation = EventInvite.objects.create(makerspace=space, event=event)
        target = invitation.pk
    elif route == "admin-event-check-in-resolve":
        data = {"checkin_token": str(registration.checkin_token)}
    elif route in ("admin-event-check-in-offline-roster", "admin-event-check-in-offline-sync"):
        space.enabled_features = [*space.enabled_features, "events.offline_checkin"]
        space.save(update_fields=["enabled_features"])
        event.starts_at = timezone.now() - timedelta(hours=1)
        event.ends_at = timezone.now() + timedelta(hours=1)
        event.save(update_fields=["starts_at", "ends_at"])
        if method == "post":
            lease = issue_roster(event, actor=user, kind="staff")
            data = {"lease_token": lease["lease_token"], "operations": [{
                "operation_id": str(uuid4()), "checkin_token": str(registration.checkin_token),
                "reported_occurred_at": timezone.now().isoformat(),
            }]}
    elif route == "admin-event-badges-pdf":
        registration = mark_attended(registration, actor=manager)
        data = {"registration_ids": [registration.pk]}
    elif route == "admin-event-publish":
        event.status = "draft"
        event.save(update_fields=["status"])
    response = getattr(client_for(user), method)(reverse(route, args=[target]), data, format="json")
    if held == required:
        assert response.status_code < 300, (route, held, response.data)
    else:
        assert response.status_code == 403, (route, held, response.data)


@pytest.mark.parametrize("held", PERMISSIONS)
@pytest.mark.parametrize("route,method,data", [
    ("admin-event-staff-grants", "get", {}),
    ("admin-event-staff-invites", "post", {"permissions": ["check_in"]}),
    ("admin-event-collaborators", "get", {}),
    ("admin-event-check-in-station", "get", {}),
    ("admin-event-check-in-station-rotate", "post", {}),
    ("admin-event-tickets", "post", {"name": "Paid ticket", "amount": "5.00"}),
    ("admin-event-promos", "get", {}),
])
def test_full_manager_operations_stay_forbidden_for_all_grant_holders(held, route, method, data):
    _, _, user, event, _ = grant_fixture(held)
    response = getattr(client_for(user), method)(reverse(route, args=[event.pk]), data, format="json")
    if held == "manage_team" and route == "admin-event-staff-grants":
        # Decision 15: a manage_team co-organizer lists only the grants it issued (none here).
        assert response.status_code == 200 and response.data["results"] == [], response.data
        return
    assert response.status_code == 403


def test_detail_editor_cannot_change_payment_settings():
    _, _, user, event, _ = grant_fixture("edit_details")
    response = client_for(user).patch(reverse("admin-event-detail", args=[event.pk]), {"payment_amount": "25.00"}, format="json")
    assert response.status_code == 403
    event.refresh_from_db()
    assert event.payment_amount == 0


def test_check_in_response_has_no_roster_contacts_answers_or_payments():
    _, _, user, event, _ = grant_fixture("check_in")
    attendee = account("private-attendee")
    registration = EventRegistration.objects.create(
        event=event, member=attendee, name="Attendee", email=attendee.email,
        phone="private-phone", custom_answers={"version": 1, "answers": [{"id": "secret", "value": "private-answer"}]},
    )
    response = client_for(user).post(reverse("admin-event-registration-mark-attended", args=[registration.pk]), {}, format="json")
    assert response.status_code == 200
    assert set(response.data) == {"id", "event_id", "name", "status"}
    assert not any(value in str(response.data) for value in (attendee.email, "private-phone", "private-answer"))


def test_feedback_designer_cannot_enable_or_disable_certificate_issuance():
    _, _, user, event, _ = grant_fixture("edit_details")
    survey = EventFeedbackSurvey.objects.create(event=event, title="Original", questions=QUESTIONS, certificate_enabled=True)
    client = client_for(user)
    url = reverse("admin-event-feedback-survey", args=[event.pk])
    edited = client.put(url, {"title": "Design edited", "questions": QUESTIONS}, format="json")
    assert edited.status_code == 200
    survey.refresh_from_db()
    assert survey.certificate_enabled is True
    denied = client.put(url, {"title": "Disable certificates", "questions": QUESTIONS, "certificate_enabled": False}, format="json")
    assert denied.status_code == 403
    survey.refresh_from_db()
    assert survey.certificate_enabled is True


@pytest.mark.parametrize("held", PERMISSIONS)
@pytest.mark.parametrize("route", ["admin-event-certificate-download", "admin-event-certificate-revoke", "admin-event-certificate-reissue"])
def test_certificate_issue_revoke_and_artifact_reads_stay_manager_only(held, route):
    _, manager, user, event, _ = grant_fixture(held)
    attendee = account("certificate-attendee")
    registration = EventRegistration.objects.create(
        event=event, member=attendee, name="Attendee", email=attendee.email, phone=attendee.phone,
    )
    registration = mark_attended(registration, actor=manager)
    survey = EventFeedbackSurvey.objects.create(event=event, title="Survey", questions=QUESTIONS, certificate_enabled=True)
    response = EventFeedbackResponse.objects.create(
        survey=survey, registration=registration, answers_snapshot='{"version":1,"answers":[]}', certificate_requested=True,
    )
    certificate = create_pending(response)
    client = client_for(user)
    url = reverse(route, args=[certificate.pk])
    denied = client.get(url) if route.endswith("download") else client.post(url, {}, format="json")
    assert denied.status_code == 403
