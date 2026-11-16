"""C4: signatories, signature layers and the default-off approval gate."""
from copy import deepcopy

import pytest
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.events.certificates.layout import normalize_document
from apps.events.certificates.signatories import require_render_released, unapproved
from apps.events.certificates.signatory_commands import (approve, pending_for, remove_signatory,
                                                         save_signatory, set_approval_required)
from apps.events.credentials.errors import ProgrammeConflict
from apps.events.services_certificate_templates import save_template
from tests.events.checkin_helpers import make_member, make_staff, register
from tests.events.programme.certificates.test_layers import document

from .helpers import ended_event, issue

pytestmark = pytest.mark.django_db(transaction=True)
SIGNATURE = {"id": "0b9c1a3e-1b2c-4d5e-8f90-123456789abc", "type": "signature", "signature_slot": 1,
             "x_mm": 200, "y_mm": 150, "width_mm": 70, "height_mm": 40, "rotation": 0,
             "font_size_pt": 11, "font_weight": 600, "align": "center"}


def signed_document():
    value = deepcopy(document())
    value["layers"].append({**SIGNATURE, "order": len(value["layers"])})
    return value


def _world(slug):
    space, event = ended_event(slug)
    space.enabled_features = [*space.enabled_features, "events.certificate_designer"]
    space.save(update_fields=("enabled_features",))
    staff = make_staff(space)
    director = make_member(space, "director", display_name="Dr Director")
    return space, event, staff, director


def test_signature_layer_validation():
    normalize_document(signed_document())
    bad = signed_document()
    bad["layers"][-1]["signature_slot"] = 4
    with pytest.raises(ValidationError):
        normalize_document(bad)
    bad = signed_document()
    bad["layers"][-1]["text"] = "{{name}}"
    with pytest.raises(ValidationError):
        normalize_document(bad)
    with pytest.raises(ValidationError):
        normalize_document(signed_document(), badge=True)


def test_design_needs_the_signatory_and_issuance_freezes_it():
    space, event, staff, director = _world("c4-freeze")
    with pytest.raises(ValidationError):
        save_template(event, actor=staff, parameters=signed_document())
    save_signatory(event, actor=staff, slot=1, name="Dr Director", title="Director")
    revision = save_template(event, actor=staff, parameters=signed_document())
    attendee = make_member(space, "c4-attendee")
    row = issue(event, "registration", register(event, attendee, status="attended").pk, activate=False)
    signature = row.layout_snapshot["signatures"]["1"]
    assert (signature["name"], signature["title"], signature["version"]) == ("Dr Director", "Director", 1)
    assert row.template_revision_id == revision.pk
    from apps.events.certificate_rendering import render_certificate_pdf
    assert render_certificate_pdf(row).startswith(b"%PDF")
    with pytest.raises(ProgrammeConflict):
        remove_signatory(event, actor=staff, slot=1)


def test_approval_gate_holds_rendering_until_the_signatory_approves():
    space, event, staff, director = _world("c4-gate")
    save_signatory(event, actor=staff, slot=1, name="Dr Director", title="Director")
    with pytest.raises(ValidationError):
        set_approval_required(event, actor=staff, required=True)
    save_signatory(event, actor=staff, slot=1, name="Dr Director", title="Director", member_id=director.pk)
    set_approval_required(event, actor=staff, required=True)
    revision = save_template(event, actor=staff, parameters=signed_document())
    row = issue(event, "registration", register(event, make_member(space, "c4-a"), status="attended").pk,
                activate=False)
    with pytest.raises(ProgrammeConflict):
        require_render_released(row)
    waiting = pending_for(director, space.pk)
    assert [(item["template_revision_id"], item["approved"]) for item in waiting] == [(revision.pk, False)]
    other = make_member(space, "c4-other")
    from rest_framework.exceptions import NotFound
    with pytest.raises(NotFound):
        approve(event.pk, actor=other, signatory_id=waiting[0]["signatory_id"], template_revision_id=revision.pk)
    approve(event.pk, actor=director, signatory_id=waiting[0]["signatory_id"], template_revision_id=revision.pk)
    require_render_released(row)
    assert pending_for(director, space.pk)[0]["approved"] is True
    # A change to the signatory's details needs a fresh approval for new certificates.
    save_signatory(event, actor=staff, slot=1, name="Dr Director", title="Chair", member_id=director.pk)
    assert pending_for(director, space.pk)[0]["approved"] is False
    assert unapproved(event, revision.pk, row.layout_snapshot["signatures"]) == []


def test_routes_for_staff_and_signatory():
    space, event, staff, director = _world("c4-routes")
    client = APIClient()
    client.force_authenticate(staff)
    base = f"/api/v1/admin/events/{event.pk}/certificates/signatories/"
    response = client.post(base, {"slot": 1, "name": "Dr Director", "title": "Director",
                                  "member_id": director.pk}, format="json")
    assert response.status_code == 200, response.content
    assert response.data["signatories"][0]["member_name"] == "Dr Director"
    assert client.post(base + "approval-policy/", {"required": True}, format="json").data["approval_required"] is True
    assert [row["name"] for row in client.get(base + "candidates/", {"q": "Dire"}).data] == ["Dr Director"]
    revision = save_template(event, actor=staff, parameters=signed_document())
    member = APIClient()
    member.force_authenticate(director)
    listing = member.get(f"/api/v1/member/makerspaces/{space.pk}/certificate-approvals/")
    assert listing.status_code == 200 and listing.data[0]["template_revision_id"] == revision.pk
    signatory_id = listing.data[0]["signatory_id"]
    preview = member.get(f"/api/v1/member/makerspaces/{space.pk}/certificate-approvals/{signatory_id}/designs/{revision.pk}/preview.pdf")
    assert preview.status_code == 200 and preview["Content-Type"] == "application/pdf"
    done = member.post(f"/api/v1/member/makerspaces/{space.pk}/certificate-approvals/{signatory_id}/approve/",
                       {"template_revision_id": revision.pk}, format="json")
    assert done.status_code == 200, done.content
    assert client.get(base).data["designs"][0]["released"] is True
    assert client.delete(base + "1/").status_code == 409
