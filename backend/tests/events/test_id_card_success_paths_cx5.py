"""Card scan, consented photo attachment and download: direct happy-path HTTP proofs."""
import pytest

from apps.audit.models import AuditLog
from apps.card_designs import photos, tokens
from apps.events.models import EventCheckInEvent
from tests.events.test_card_routes_conditions_mod2b import world
from tests.events.test_lane_e_artwork import png
from tests.l3_local.helpers import client
from tests.refusal_helpers_mod2b import field_error

pytestmark = pytest.mark.django_db
API = "/api/v1/admin"


def test_card_scan_identifies_before_checkin_and_replay_adds_no_attendance_or_audit():
    w = world("cx5-card-scan")
    token = tokens.live("event_card", w.card)
    assert token is not None
    api = client(w.sm)
    url = f"{API}/events/{w.event.pk}/check-in/card-scan"
    body = {"payload": tokens.url(token.token)}
    found = api.post(url, body, format="json")
    assert found.status_code == 200, found.content
    assert found.json()["checked_in"] is None
    assert [row["registration_id"] for row in found.json()["registrations"]] == [w.registration.pk]
    w.registration.refresh_from_db()
    assert w.registration.status == "registered"
    assert not EventCheckInEvent.objects.filter(registration=w.registration).exists()
    checked = api.post(url, {**body, "check_in": True}, format="json")
    assert checked.status_code == 200 and checked.json()["checked_in"] == w.registration.pk
    again = api.post(url, {**body, "check_in": True}, format="json")
    assert again.status_code == 200 and again.json()["checked_in"] is None
    assert EventCheckInEvent.objects.filter(registration=w.registration).count() == 1
    for action in ("event.registration_attended", "card.scanned_for_checkin"):
        assert AuditLog.objects.filter(makerspace=w.space, action=action, target_id=str(w.registration.pk)).count() == 1


def test_card_photo_requires_consent_then_attaches_to_a_new_server_owned_key(monkeypatch):
    w = world("cx5-card-photo")
    staged, final = {}, {}
    monkeypatch.setattr(photos, "presign_staging", lambda key, content_type, cap: {
        "url": "https://private.test/staging/" + key, "method": "PUT"})
    monkeypatch.setattr(photos, "take_staging", lambda key, cap: staged.pop(key, None))
    monkeypatch.setattr(photos, "put_bytes", lambda key, data, content_type: final.update({key: data}))
    api = client(w.sm)
    url = f"{API}/event-id-cards/{w.card.pk}/photo"
    first = api.post(url, {"content_type": "image/png"}, format="json")
    assert first.status_code == 201
    key = first.json()["object_key"]
    assert "/staging/" in first.json()["url"]
    staged[key] = png()
    refused = api.put(url, {"object_key": key, "holder_consented": False}, format="json")
    field_error(refused, "consent", "invalid")
    w.card.refresh_from_db()
    assert w.card.photo_object_key == "" and final == {}
    assert not AuditLog.objects.filter(makerspace=w.space, action="card.photo_set_by_staff").exists()
    retry = api.post(url, {"content_type": "image/png"}, format="json")
    assert retry.status_code == 201
    key = retry.json()["object_key"]
    staged[key] = png()
    result = api.put(url, {"object_key": key, "holder_consented": True}, format="json")
    assert result.status_code == 200 and result.json() == {"photo_set": True}
    w.card.refresh_from_db()
    assert w.card.photo_object_key != key
    assert w.card.photo_object_key in final and w.card.photo_content_type == "image/png"
    assert w.card.photo_consent_at is not None and staged == {}
    assert AuditLog.objects.filter(makerspace=w.space, action="event_card.photo_updated", target_id=str(w.card.pk)).count() == 1
    assert AuditLog.objects.filter(makerspace=w.space, action="card.photo_set_by_staff", target_id=str(w.card.pk)).count() == 1
    missing = api.put(url, {"object_key": key, "holder_consented": True}, format="json")
    field_error(missing, "object_key", "invalid")
    assert AuditLog.objects.filter(makerspace=w.space, action="card.photo_set_by_staff", target_id=str(w.card.pk)).count() == 1


def test_card_download_returns_a_pdf_and_throttles_duplicate_download_audits():
    w = world("cx5-card-download")
    api = client(w.sm)
    url = f"{API}/event-id-cards/{w.card.pk}/download"
    for _ in range(2):
        response = api.get(url)
        assert response.status_code == 200, response.content[:100]
        assert response["Content-Type"] == "application/pdf"
        assert response.content.startswith(b"%PDF-")
        assert response["Content-Disposition"].startswith("attachment;")
    assert AuditLog.objects.filter(makerspace=w.space, action="event_card.downloaded", target_id=str(w.card.pk)).count() == 1
