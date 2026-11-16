from copy import deepcopy
from unittest.mock import Mock

import pytest

from apps.events.certificate_templates import issuance_layout
from django.core.exceptions import ValidationError as ModelError
from django.db import DatabaseError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit.models import AuditLog
from apps.events.certificate_templates import DEFAULT_CERTIFICATE_TEMPLATE
from apps.events.models import (EventCertificateArtwork, EventCertificateTemplateRevision,
                               EventFeedbackResponse, EventFeedbackSurvey, EventRegistration)
from apps.events.services_certificate_templates import save_template, finalize_artwork
from apps.events.services_certificates import create_pending, render_certificate, reissue, revoke
from apps.events.certificate_storage import CertificateStorageUnavailable
from tests.events.checkin_helpers import client_for, make_event, register
from tests.events.staff_grant_helpers import grant_fixture
from tests.events.ticketing_helpers import account, event_space

pytestmark = pytest.mark.django_db


@pytest.fixture
def design():
    space, manager, editor, event, grant = grant_fixture()
    space.enabled_features += ["events.certificate_designer"]
    space.save(update_fields=["enabled_features"])
    return space, manager, editor, event, grant


def response_for(event):
    registration = register(event, account("certificate-recipient"), status="attended")
    survey = EventFeedbackSurvey.objects.create(event=event, title="Feedback", certificate_enabled=True,
                                                questions=[{"id": "rating", "label": "Rating", "type": "number", "options": [], "required": False}])
    return EventFeedbackResponse.objects.create(survey=survey, registration=registration,
                                               answers_snapshot='{"answers": []}', certificate_requested=True)


def test_every_save_appends_immutable_revision_and_audits(design):
    space, manager, editor, event, grant = design
    first = save_template(event, actor=editor, parameters={})
    changed = deepcopy(first.parameters)
    changed["name_box"]["colour"] = "#123456"
    second = save_template(event, actor=editor, parameters=changed)
    first.refresh_from_db()
    assert first.pk != second.pk
    assert first.parameters["name_box"]["colour"] != second.parameters["name_box"]["colour"]
    with pytest.raises(ModelError):
        first.save()
    with pytest.raises(DatabaseError), transaction.atomic():
        EventCertificateTemplateRevision.objects.filter(pk=first.pk).update(parameters={})
    assert AuditLog.objects.filter(action="event.certificate_template_saved").count() == 2


GEOMETRY = ("x_mm", "y_mm", "width_mm", "height_mm")


def name_geometry(snapshot):
    layer = next(layer for layer in snapshot["layers"] if layer.get("text") == "{{name}}")
    return {key: layer[key] for key in GEOMETRY}


def box_geometry(parameters):
    return {key: parameters["name_box"][key] for key in GEOMETRY}


def test_fractional_grid_survives_preview_revision_read_and_issuance(design, monkeypatch):
    space, manager, editor, event, grant = design
    parameters = deepcopy(DEFAULT_CERTIFICATE_TEMPLATE)
    parameters["grid_mm"] = 0.5
    parameters["name_box"].update(x_mm=25.5, y_mm=76.5, width_mm=246.5, height_mm=18.5)
    body = {"parameters": parameters}
    client = client_for(editor)
    url = f"/api/v1/admin/events/{event.pk}/certificate-template/"
    preview = Mock(return_value=b"%PDF-1.4 sample")
    monkeypatch.setattr("apps.events.views_certificate_templates.render_certificate_pdf", preview)
    assert client.post(url + "preview.pdf", body, format="json").status_code == 200
    snapshot = preview.call_args.args[0].layout_snapshot
    # Issuance upgrades a v1 design to the layered v2 document; the fractional
    # geometry must survive losslessly in the bound name layer.
    assert snapshot["version"] == 2 and name_geometry(snapshot) == box_geometry(parameters)
    saved = client.post(url, body, format="json")
    assert saved.status_code == 201 and saved.data["parameters"] == parameters
    # Reads project a stored v1 design as the layered v2 document (stored bytes unchanged).
    read = client.get(url).data["parameters"]
    assert read["version"] == 2 and name_geometry(read) == box_geometry(parameters)
    revision = EventCertificateTemplateRevision.objects.get(pk=saved.data["id"])
    assert revision.parameters == parameters
    certificate = create_pending(response_for(event))
    assert certificate.layout_snapshot["version"] == 2
    assert name_geometry(certificate.layout_snapshot) == box_geometry(parameters)


def test_templates_without_grid_keep_one_mm_default(design):
    parameters = deepcopy(DEFAULT_CERTIFICATE_TEMPLATE)
    parameters.pop("grid_mm")
    parameters["name_box"]["x_mm"] = 25.6
    revision = save_template(design[3], actor=design[2], parameters=parameters)
    assert revision.parameters["grid_mm"] == 1
    assert revision.parameters["name_box"]["x_mm"] == 26


def test_feature_grants_revocation_cross_event_and_tenant(design):
    space, manager, editor, event, grant = design
    url = f"/api/v1/admin/events/{event.pk}/certificate-template/"
    assert client_for(editor).get(url).status_code == 200
    foreign = make_event(event_space("foreign-design"))
    foreign_url = url.replace(f"/{event.pk}/", f"/{foreign.pk}/")
    assert client_for(editor).get(foreign_url).status_code == 404
    grant.revoked_at = timezone.now()
    grant.save(update_fields=["revoked_at"])
    with pytest.raises(PermissionDenied):
        save_template(event, actor=editor, parameters={})
    space.enabled_features.remove("events.certificate_designer")
    space.save(update_fields=["enabled_features"])
    # #183B: a capability that is off answers a typed 404.
    assert client_for(manager).get(url).status_code == 404
    assert not EventCertificateTemplateRevision.objects.exists()


def test_artwork_must_be_promoted_and_owned_by_same_event(design):
    space, manager, editor, event, grant = design
    artwork = EventCertificateArtwork.objects.create(event=event, object_key="private/pending.png")
    with pytest.raises(NotFound):
        save_template(event, actor=editor, parameters={}, artwork_id=artwork.pk)
    foreign = make_event(event_space("foreign-art"))
    other = EventCertificateArtwork.objects.create(event=foreign, object_key="private/other.png",
                                                   promoted_at=timezone.now(), size_bytes=1, sha256="a" * 64)
    with pytest.raises(NotFound):
        save_template(event, actor=editor, parameters={}, artwork_id=other.pk)
    with pytest.raises(NotFound):
        finalize_artwork(event, other.pk, actor=editor)


def test_pending_failed_retry_uses_issuance_revision_and_full_snapshot(design, monkeypatch):
    space, manager, editor, event, grant = design
    first = save_template(event, actor=editor, parameters={})
    certificate = create_pending(response_for(event))
    frozen = deepcopy(certificate.layout_snapshot)
    changed = deepcopy(first.parameters)
    changed["name_box"]["font_size_pt"] = 42
    second = save_template(event, actor=editor, parameters=changed)
    render = Mock(return_value=b"%PDF-1.4 test")
    store = Mock(side_effect=[CertificateStorageUnavailable(), (13, "a" * 64)])
    monkeypatch.setattr("apps.events.services_certificates.render_certificate_pdf", render)
    monkeypatch.setattr("apps.events.services_certificates.store_immutable_pdf", store)
    with pytest.raises(CertificateStorageUnavailable):
        render_certificate(certificate)
    certificate.refresh_from_db()
    assert certificate.status == "failed"
    rendered = render_certificate(certificate)
    assert rendered.status == "active"
    assert all(call.args[0].template_revision_id == first.pk for call in render.call_args_list)
    assert all(call.args[0].layout_snapshot == frozen for call in render.call_args_list)
    with pytest.raises(DatabaseError), transaction.atomic():
        type(certificate).objects.filter(pk=certificate.pk).update(layout_snapshot=second.parameters)
    revoke(rendered, actor=manager, reason="staff_revoked")
    new = reissue(certificate.registration, actor=manager)
    assert new.template_revision_id == second.pk
    # r2-idcards-best C1: issuance also freezes the kind/award/role/place labels beside the layout.
    assert {k: v for k, v in new.layout_snapshot.items() if k != "merge"} == issuance_layout(second)
    assert new.layout_snapshot["merge"]["kind"] == "Attendance"
    assert new.layout_snapshot["artwork_object_key"] == "" and new.layout_snapshot["artwork_sha256"] == ""
    assert next(layer for layer in new.layout_snapshot["layers"] if layer.get("text") == "{{name}}")["font_size_pt"] == 42


@pytest.mark.parametrize("parameters", [
    {"unknown": True}, {"page_width_mm": float("nan")}, {"version": 2},
    {"grid_mm": 0}, {"grid_mm": 0.25}, {"grid_mm": 11}, {"grid_mm": True},
    {"grid_mm": float("nan")}, {"grid_mm": float("inf")},
    {"name_box": {"field": "email", "x_mm": 0, "y_mm": 0, "width_mm": 100, "height_mm": 10}},
    {"name_box": {"field": "name", "x_mm": 290, "y_mm": 0, "width_mm": 100, "height_mm": 10}},
])
def test_layout_boundary_refuses_invalid_parameters(design, parameters):
    with pytest.raises(ValidationError):
        save_template(design[3], actor=design[2], parameters=parameters)
    assert not EventCertificateTemplateRevision.objects.exists()


def test_preview_is_sample_only_throttled_and_private(design, monkeypatch):
    space, manager, editor, event, grant = design
    render = Mock(return_value=b"%PDF-1.4 test")
    monkeypatch.setattr("apps.events.views_certificate_templates.render_certificate_pdf", render)
    url = f"/api/v1/admin/events/{event.pk}/certificate-template/preview.pdf"
    client = client_for(editor)
    assert client.post(url, {"parameters": {}, "name": "PRIVATE"}, format="json").status_code == 400
    result = client.post(url, {"parameters": {}}, format="json")
    assert result.status_code == 200
    assert result["Cache-Control"] == "private, no-store"
    assert render.call_args.args[0].recipient_name == "Sample attendee"
    for _ in range(29):
        client.post(url, {"parameters": {}}, format="json")
    assert client.post(url, {"parameters": {}}, format="json").status_code == 429


@pytest.mark.parametrize("permission,allowed", [("edit_details", True), ("check_in", False),
    ("manage_registrations", False), ("manage_invitations", False), ("publish_schedule", False)])
def test_designer_permission_vocabulary_does_not_confer_other_authority(permission, allowed):
    space, manager, user, event, grant = grant_fixture(permission)
    space.enabled_features += ["events.certificate_designer"]
    space.save()
    result = client_for(user).post(f"/api/v1/admin/events/{event.pk}/certificate-template/",
                                  {"parameters": {}}, format="json")
    assert result.status_code == (201 if allowed else 403)
    assert EventCertificateTemplateRevision.objects.count() == int(allowed)


def test_stale_editor_account_and_unservable_space_are_rechecked_under_locks(design):
    space, manager, editor, event, grant = design
    type(editor).objects.filter(pk=editor.pk).update(access_status="suspended")
    with pytest.raises(PermissionDenied):
        save_template(event, actor=editor, parameters={})
    type(editor).objects.filter(pk=editor.pk).update(access_status="active")
    space.archived_at = timezone.now()
    space.save(update_fields=["archived_at"])
    with pytest.raises(PermissionDenied):
        save_template(event, actor=editor, parameters={})
    assert not EventCertificateTemplateRevision.objects.exists()


def test_designer_capability_defaults_off_and_installer_events_area_picks_it_up():
    from apps.makerspaces.capabilities import FEATURES, default_enabled_features
    from apps.makerspaces.setup_areas import features_for
    key = "events.certificate_designer"
    assert FEATURES[key].parent_module == "events"
    assert set(FEATURES[key].requires_modules) == {"events"}
    assert key not in default_enabled_features()
    assert key in features_for(["events"])
    assert key not in features_for(["bookings"])
