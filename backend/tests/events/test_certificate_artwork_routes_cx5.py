"""Certificate artwork HTTP authority, storage failure and write-once promotion."""
from unittest.mock import Mock

import pytest
from botocore.exceptions import EndpointConnectionError
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.events import certificate_artwork_storage as storage
from apps.events.models import EventCertificateArtwork
from tests.events.collab_helpers import client_for, make_member, make_staff
from tests.events.staff_grant_helpers import grant_fixture
from tests.events.test_lane_e_artwork import S3, png
from tests.events.ticketing_helpers import event_space
from tests.refusal_helpers_mod2b import field_error, refused

pytestmark = pytest.mark.django_db


@pytest.fixture
def artwork(monkeypatch):
    space, manager, editor, event, grant = grant_fixture(slug="cx5-artwork")
    space.enabled_features = sorted({*space.enabled_features, "events.certificate_designer"})
    space.save(update_fields=["enabled_features"])
    fake = S3()
    monkeypatch.setattr(storage, "_client", lambda endpoint: fake)
    # Version deletion is separately tested; keep promotion and byte validation real.
    monkeypatch.setattr(storage, "cleanup_staging", Mock())
    return space, manager, editor, event, grant, fake


def reserve_url(event):
    return f"/api/v1/admin/events/{event.pk}/certificate-artwork/"


def finalize_url(event, pk):
    return reserve_url(event) + f"{pk}/finalize/"


def reserve(artwork, actor=None):
    _space, manager, _editor, event, _grant, _fake = artwork
    response = client_for(actor or manager).post(reserve_url(event),
        {"content_type": "image/png", "content_length": len(png())}, format="json")
    assert response.status_code == 201, response.content
    return EventCertificateArtwork.objects.get(pk=response.json()["id"])


@pytest.mark.parametrize("role", ["space_manager", "manual_delegate", "organizer", "coorganizer"])
def test_presign_and_finalize_are_private_staged_and_audited_once(artwork, role):
    space, manager, editor, event, _grant, fake = artwork
    actor = manager if role == "space_manager" else editor
    if role in {"organizer", "coorganizer"}:
        from tests.events.test_scoped_organizer_routes_cx5 import organization_actor
        actor = organization_actor(event, role)
    row = reserve(artwork, actor)
    operation, values = fake.signed
    assert operation == "put_object"
    assert values["Params"]["Key"] == "staging/" + row.object_key
    assert values["Params"]["ContentLength"] == len(png())
    assert values["ExpiresIn"] == 600
    assert row.object_key not in fake.objects
    fake.objects["staging/" + row.object_key] = png("red")
    api = client_for(actor)
    result = api.post(finalize_url(event, row.pk), {}, format="json")
    assert result.status_code == 200, result.content
    assert result.json() == {"id": row.pk, "resource_id": str(row.resource_id)}
    assert result["Cache-Control"] == "private, no-store"
    row.refresh_from_db()
    metadata = (row.sha256, row.version_id, row.size_bytes, row.promoted_at)
    final_bytes = fake.objects[row.object_key]
    fake.objects["staging/" + row.object_key] = png("blue")
    replay = api.post(finalize_url(event, row.pk), {}, format="json")
    assert replay.status_code == 200 and replay.json() == result.json()
    row.refresh_from_db()
    assert (row.sha256, row.version_id, row.size_bytes, row.promoted_at) == metadata
    assert fake.objects[row.object_key] == final_bytes and len(fake.puts) == 1
    for action in ("event.certificate_artwork_presigned", "event.certificate_artwork_promoted"):
        assert AuditLog.objects.filter(makerspace=space, action=action, target_id=str(row.pk)).count() == 1


@pytest.mark.parametrize("operation", ["presign", "finalize"])
@pytest.mark.parametrize("role", ["signed_out", "member", "other_tenant"])
def test_artwork_refusals_do_not_reserve_promote_or_audit(artwork, operation, role):
    space, manager, _editor, event, _grant, fake = artwork
    row = reserve(artwork)
    actor = {"signed_out": None, "member": make_member(space, "plain"),
             "other_tenant": make_staff(event_space("cx5-artwork-other"))}[role]
    api = APIClient() if actor is None else client_for(actor)
    before = AuditLog.objects.filter(makerspace=space).count()
    url = reserve_url(event) if operation == "presign" else finalize_url(event, row.pk)
    body = {"content_type": "image/png", "content_length": 12} if operation == "presign" else {}
    status, code = (401, "not_authenticated") if actor is None else (
        (403, "permission_denied") if role == "member" else (404, "not_found"))
    refused(api.post(url, body, format="json"), status, code)
    assert EventCertificateArtwork.objects.filter(event=event).count() == 1
    assert AuditLog.objects.filter(makerspace=space).count() == before
    assert fake.puts == []


@pytest.mark.parametrize("operation", ["presign", "finalize"])
@pytest.mark.parametrize("switch", ["events", "events.certificate_designer"])
def test_artwork_switch_off_and_on_preserves_reservation(artwork, operation, switch):
    space, manager, _editor, event, _grant, fake = artwork
    row = reserve(artwork)
    fake.objects["staging/" + row.object_key] = png()
    field = "enabled_modules" if switch == "events" else "enabled_features"
    original = list(getattr(space, field))
    setattr(space, field, [key for key in original if key != switch])
    space.save(update_fields=[field])
    url = reserve_url(event) if operation == "presign" else finalize_url(event, row.pk)
    body = {"content_type": "image/png", "content_length": len(png())} if operation == "presign" else {}
    api = client_for(manager)
    refused(api.post(url, body, format="json"), 404,
            "module_disabled" if switch == "events" else "feature_disabled")
    row.refresh_from_db()
    assert row.promoted_at is None and fake.puts == []
    setattr(space, field, original)
    space.save(update_fields=[field])
    restored = api.post(url, body, format="json")
    assert restored.status_code == (201 if operation == "presign" else 200), restored.content
    assert EventCertificateArtwork.objects.filter(pk=row.pk).exists()


@pytest.mark.parametrize("body,field,code", [
    ({"content_type": "text/html", "content_length": 1}, "content_type", "invalid_choice"),
    ({"content_type": "image/png", "content_length": 0}, "content_length", "min_value"),
    ({"content_type": "image/png", "content_length": storage.MAX_BYTES + 1}, "content_length", "max_value"),
    ({"content_type": "image/png"}, "content_length", "required"),
])
def test_artwork_invalid_presigns_leave_no_reservation_or_audit(artwork, body, field, code):
    space, manager, _editor, event, _grant, fake = artwork
    response = client_for(manager).post(reserve_url(event), body, format="json")
    assert response.status_code == 400
    assert response.data[field][0].code == code
    assert not EventCertificateArtwork.objects.filter(event=event).exists()
    assert not AuditLog.objects.filter(makerspace=space, action="event.certificate_artwork_presigned").exists()
    assert fake.signed is None


def test_presign_storage_failure_rolls_back_row_quota_and_audit(artwork, monkeypatch):
    space, manager, _editor, event, _grant, fake = artwork
    space.refresh_from_db()
    before = space.storage_bytes_used
    fake.generate_presigned_url = Mock(side_effect=EndpointConnectionError(endpoint_url="https://private.test"))
    response = client_for(manager).post(reserve_url(event),
        {"content_type": "image/png", "content_length": 12}, format="json")
    refused(response, 503, "artwork_storage_unavailable")
    space.refresh_from_db()
    assert space.storage_bytes_used == before
    assert not EventCertificateArtwork.objects.filter(event=event).exists()
    assert not AuditLog.objects.filter(makerspace=space, action="event.certificate_artwork_presigned").exists()


def test_finalize_does_not_accept_a_foreign_artwork_id_or_client_object_key(artwork):
    space, manager, _editor, event, _grant, fake = artwork
    row = reserve(artwork)
    foreign = grant_fixture(slug="cx5-artwork-foreign", grantee="foreign-editor")[3]
    api = client_for(manager)
    refused(api.post(finalize_url(foreign, row.pk), {}, format="json"), 404, "not_found")
    response = api.post(finalize_url(event, row.pk), {"object_key": "other/final.png"}, format="json")
    field_error(response, "object_key", "invalid")
    row.refresh_from_db()
    assert row.promoted_at is None and fake.puts == []
    assert not AuditLog.objects.filter(makerspace=space, action="event.certificate_artwork_promoted").exists()
