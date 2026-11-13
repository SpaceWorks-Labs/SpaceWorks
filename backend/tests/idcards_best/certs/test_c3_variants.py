"""C3: an event holds a design per certificate kind, falling back to the event default."""
from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from apps.events.certificates.template_commands import save_command
from apps.events.contributions.models_roles import EventRoleAssignment
from apps.events.services_certificate_templates import save_template
from tests.events.checkin_helpers import make_member, make_staff, register
from tests.events.programme.certificates.test_layers import document

from .helpers import ended_event, issue

pytestmark = pytest.mark.django_db(transaction=True)


def _designer_event(slug):
    space, event = ended_event(slug)
    space.enabled_features = [*space.enabled_features, "events.certificate_designer"]
    space.save(update_fields=("enabled_features",))
    return space, event, make_staff(space)


def _variant(size):
    value = document()
    value["layers"][0]["font_size_pt"] = size
    return value


def test_each_kind_snapshots_its_own_design_or_the_default():
    space, event, staff = _designer_event("c3-variants")
    default = save_template(event, actor=staff, parameters=_variant(20))
    organiser = save_template(event, actor=staff, parameters=_variant(30), certificate_kind="organiser_thanks")
    attendee = make_member(space, "c3-attendee")
    registration = register(event, attendee, status="attended")
    host = make_member(space, "c3-host")
    role = EventRoleAssignment.objects.create(event=event, makerspace=space, member=host,
                                              role="co_organizer", origin="staff", state="approved")
    attendance = issue(event, "registration", registration.pk)
    thanks = issue(event, "role_assignment", role.pk, kind="organiser_thanks")
    assert attendance.template_revision_id == default.pk and thanks.template_revision_id == organiser.pk
    assert [layer["font_size_pt"] for layer in thanks.layout_snapshot["layers"] if layer["type"] == "text"][0] == 30


def test_design_endpoint_reports_default_fallback_and_own_designs():
    space, event, staff = _designer_event("c3-endpoint")
    save_template(event, actor=staff, parameters=_variant(20))
    client = APIClient()
    client.force_authenticate(staff)
    url = f"/api/v1/admin/events/{event.pk}/certificate-template/"
    mentor = client.get(url, {"kind": "mentor_thanks"})
    assert mentor.status_code == 200 and mentor.data["uses_default"] is True and mentor.data["own_designs"] == []
    result = save_command(event.pk, actor=staff, operation_id=uuid4(), expected_version=event.version,
                          parameters=_variant(28), certificate_kind="mentor_thanks")
    assert result["certificate_kind"] == "mentor_thanks"
    mentor = client.get(url, {"kind": "mentor_thanks"})
    assert mentor.data["uses_default"] is False and mentor.data["own_designs"] == ["mentor_thanks"]
    assert client.get(url, {"kind": "nope"}).status_code == 400
    default = client.get(url)
    assert default.data["uses_default"] is False and default.data["id"] != mentor.data["id"]


def test_preview_uses_kind_sample_labels_and_sample_name():
    space, event, staff = _designer_event("c3-preview")
    client = APIClient()
    client.force_authenticate(staff)
    body = {"parameters": document(), "certificate_kind": "winner", "sample_name": "അനന്തകൃഷ്ണൻ നായർ"}
    response = client.post(f"/api/v1/admin/events/{event.pk}/certificate-template/preview.pdf", body, format="json")
    assert response.status_code == 200 and response["Content-Type"] == "application/pdf"
