"""O-F2: the applicant's own request carries what they need to edit it -- only while it was sent back.

`AdmissionRequestSerializer.edit_schema` is the form the application was made with (staff-only questions
removed, as on the join page) and `join_fields` the plan's photo/phone/state modes. Both are null in every
other state, so nothing new reaches the applicant outside the edit window.
"""
import pytest

from apps.makerspaces import membership_admission_changes as changes
from apps.makerspaces.models import MembershipRequest
from apps.makerspaces.serializers_admission import AdmissionRequestSerializer
from tests.makerspaces.l4_helpers import features_on
from tests.makerspaces.test_membership_admission_matrix import _application, _setup

pytestmark = pytest.mark.django_db(transaction=True)

SCHEMA = {"schema_version": 2, "form_id": "join", "revision": 1, "questions": [
    {"id": "name", "type": "short_text", "label": "Name", "required": True},
    {"id": "staff", "type": "short_text", "label": "Staff only", "required": False, "visibility": "server"},
], "sections": [{"id": "about", "before": "staff", "heading": "Internal"}]}


def _sent_back():
    space, actor, applicant, plan, _ = _setup("approval")
    features_on(space, "ask_changes")
    row = _application(space, applicant)
    MembershipRequest.objects.filter(pk=row.pk).update(application_schema=SCHEMA)
    row.refresh_from_db()
    return space, actor, applicant, plan, row


def test_edit_payload_is_null_outside_changes_requested():
    _, _, _, _, row = _sent_back()
    data = AdmissionRequestSerializer(row).data
    assert data["edit_schema"] is None and data["join_fields"] is None


def test_edit_payload_strips_staff_questions_and_reanchors_or_drops_their_headings():
    _, actor, _, _, row = _sent_back()
    sent = changes.request_changes(actor, row, "Tell us more.")
    data = AdmissionRequestSerializer(sent).data
    assert [question["id"] for question in data["edit_schema"]["questions"]] == ["name"]
    # The only heading sat above the staff-only question, with nothing visible below it: dropped.
    assert data["edit_schema"].get("sections", []) == []
    assert data["changes_note"] == "Tell us more."


def test_join_field_modes_follow_the_plan_and_the_space_switches():
    space, actor, _, plan, row = _sent_back()
    plan.join_photo, plan.join_phone, plan.join_state = "required", "optional", "hidden"
    plan.save(update_fields=["join_photo", "join_phone", "join_state"])
    MembershipRequest.objects.filter(pk=row.pk).update(selected_plan=plan)
    row.refresh_from_db()
    sent = changes.request_changes(actor, row, "Add a photo.")
    assert AdmissionRequestSerializer(sent).data["join_fields"] == {"photo": "off", "phone": "hidden", "state": "hidden"}
    features_on(space, "join_photo", "join_contact_fields")
    sent.refresh_from_db()
    assert AdmissionRequestSerializer(sent).data["join_fields"] == {"photo": "required", "phone": "optional", "state": "hidden"}
