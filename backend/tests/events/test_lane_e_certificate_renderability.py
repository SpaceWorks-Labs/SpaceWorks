"""Reject impossible issuance before its immutable snapshot can strand a member."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.events.certificate_templates import DEFAULT_CERTIFICATE_TEMPLATE
from apps.events.models import EventAttendanceCertificate, EventCertificateArtwork, EventFeedbackResponse
from apps.events.services_certificate_templates import save_template
from apps.events.services_certificates import create_pending, render_certificate
from apps.events.services_feedback import configure_survey, open_survey
from tests.events.checkin_helpers import client_for, register, make_member
from tests.events.test_lane_e_designs import design, response_for
from tests.member_submission import active_member_client

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("box,name", [
    ({"height_mm": 1}, "Ada Lovelace"),
    ({"width_mm": 1, "height_mm": 20}, "W"),
    ({"width_mm": 10, "height_mm": 3}, "Long recipient name " * 10),
])
def test_impossible_recipient_refuses_before_save_and_corrected_design_can_issue(design, box, name, monkeypatch):
    space, manager, editor, event, grant = design
    response = response_for(event)
    response.registration.name = name
    response.registration.save(update_fields=["name"])
    parameters = deepcopy(DEFAULT_CERTIFICATE_TEMPLATE)
    parameters["name_box"].update(box)
    save_template(event, actor=editor, parameters=parameters)
    store = Mock(return_value=(123, "a" * 64))
    monkeypatch.setattr("apps.events.services_certificates.store_immutable_pdf", store)

    with pytest.raises(ValidationError, match="does not fit") as error:
        create_pending(response)
    assert error.value.status_code == 400 and "layout" in error.value.detail
    assert not EventAttendanceCertificate.objects.exists()
    assert not AuditLog.objects.filter(action="event.certificate_created").exists()
    store.assert_not_called()

    corrected = save_template(event, actor=editor, parameters={})
    certificate = create_pending(response)
    assert certificate.template_revision_id == corrected.pk and certificate.revision == 1
    assert render_certificate(certificate).status == "active"
    store.assert_called_once()


def test_issuance_preflight_never_reads_private_artwork_under_locks(design, monkeypatch):
    space, manager, editor, event, grant = design
    artwork = EventCertificateArtwork.objects.create(
        event=event, object_key=f"events/certificate-artwork/{space.pk}/preflight.png",
        promoted_at=timezone.now(), size_bytes=1, sha256="a" * 64,
    )
    revision = save_template(event, actor=editor, parameters={}, artwork_id=artwork.pk)
    read = Mock(side_effect=AssertionError("No object I/O in issuance transaction"))
    monkeypatch.setattr("apps.events.certificate_artwork_storage.read_artwork", read)
    certificate = create_pending(response_for(event))
    assert certificate.template_revision_id == revision.pk
    assert certificate.layout_snapshot["artwork_object_key"] == artwork.object_key
    read.assert_not_called()


def test_preflight_also_checks_default_design_event_text(design):
    space, manager, editor, event, grant = design
    event.title = "W" * 200
    event.save(update_fields=["title"])
    parameters = deepcopy(DEFAULT_CERTIFICATE_TEMPLATE)
    parameters.update(page_width_mm=100, page_height_mm=100)
    parameters["name_box"].update(x_mm=10, y_mm=40, width_mm=80, height_mm=10)
    save_template(event, actor=editor, parameters=parameters)
    with pytest.raises(ValidationError, match="does not fit"):
        create_pending(response_for(event))
    assert not EventAttendanceCertificate.objects.exists()


def test_feedback_overflow_rolls_back_response_and_succeeds_after_design_correction(design):
    space, manager, editor, event, grant = design
    event.starts_at = timezone.now() - timedelta(hours=2)
    event.ends_at = timezone.now() - timedelta(hours=1)
    event.save(update_fields=["starts_at", "ends_at"])
    question = {"id": "experience", "label": "How was it?", "type": "short_text",
                "required": False, "options": []}
    configure_survey(event, actor=manager, title="Feedback", questions=[question], certificate_enabled=True)
    open_survey(event, actor=manager)
    member = make_member(space, "overflow-feedback")
    client = client_for(member)
    register(event, member, status="attended")
    parameters = deepcopy(DEFAULT_CERTIFICATE_TEMPLATE)
    parameters["name_box"]["height_mm"] = 1
    save_template(event, actor=editor, parameters=parameters)
    url = reverse("public-event-feedback", kwargs={
        "makerspace_slug": space.slug, "public_token": event.public_token,
    })
    body = {"email": member.email, "answers": {}}
    refused = client.post(url, body, format="json")
    assert refused.status_code == 400
    assert not EventFeedbackResponse.objects.exists()
    assert not EventAttendanceCertificate.objects.exists()
    assert not AuditLog.objects.filter(action__in=["event.feedback_submitted", "event.certificate_created"]).exists()

    save_template(event, actor=editor, parameters={})
    assert client.post(url, body, format="json").status_code == 201
    assert EventFeedbackResponse.objects.count() == EventAttendanceCertificate.objects.count() == 1


def test_existing_unrenderable_snapshot_download_retains_typed_layout_error(design, monkeypatch):
    space, manager, editor, event, grant = design
    response = response_for(event)
    snapshot = deepcopy(DEFAULT_CERTIFICATE_TEMPLATE)
    snapshot["name_box"]["height_mm"] = 1
    # Simulate a snapshot frozen by the old issuance path, bypassing preflight.
    certificate = EventAttendanceCertificate(
        response=response, registration=response.registration, revision=1,
        layout_snapshot=snapshot, recipient_name="Ada Lovelace", event_title=event.title,
        event_starts_at=event.starts_at, event_ends_at=event.ends_at, issuer_name=space.name,
    )
    certificate.object_key = f"event-certificates/{space.pk}/{certificate.serial}.pdf"
    certificate.save()
    store = Mock()
    monkeypatch.setattr("apps.events.services_certificates.store_immutable_pdf", store)
    result = client_for(manager).get(reverse("admin-event-certificate-download", args=[certificate.pk]))
    assert result.status_code == 400 and "does not fit" in str(result.data)
    certificate.refresh_from_db()
    assert certificate.status == "failed" and certificate.layout_snapshot == snapshot
    store.assert_not_called()
