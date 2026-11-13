from datetime import timedelta
from io import BytesIO
from uuid import uuid4
import logging
import pytest
from django.urls import reverse
from icalendar import Calendar
from PIL import Image
from apps.audit.models import AuditLog
from apps.bookings import services
from apps.bookings.models import BookingCheckInEvent
from apps.bookings.services_arrival import qr_value
from tests.bookings.staff_grant_helpers import client_for
from tests.bookings.arrival_helpers import world, clock, url, owner_url

pytestmark = pytest.mark.django_db


def test_owned_confirmation_contains_no_private_answers_or_contacts_and_is_no_store():
    w = world(); result = client_for(w.owner).get(owner_url(w))
    assert result.status_code == 200 and result.data["qr_value"] == w.credential
    assert result["Cache-Control"] == "private, no-store" and result["Referrer-Policy"] == "no-referrer"
    assert not {"note","email","phone","custom_answers","member"} & set(result.data)
    assert w.credential not in result.data["google_calendar_url"]
    assert w.owner.email not in result.data["google_calendar_url"]
    assert client_for(w.scanner).get(owner_url(w)).status_code == 404
    assert client_for(None).get(owner_url(w)).status_code in (401,403)


def test_account_only_installation_and_feature_off():
    from tests.return_helpers import make_user
    from apps.bookings.services_bookings import create_booking
    w = world(); owner = make_user("booking-account-confirmation", phone="123")
    w.tenant.enabled_modules = [key for key in w.tenant.enabled_modules if key not in ("events","membership","presence","payments")]
    w.tenant.save(update_fields=["enabled_modules"])
    w.booking = create_booking(w.resource, member=owner, actor=owner, starts_at=w.booking.starts_at + timedelta(days=1), ends_at=w.booking.ends_at + timedelta(days=1))
    assert client_for(owner).get(owner_url(w)).status_code == 200
    w.tenant.enabled_features = [key for key in w.tenant.enabled_features if key not in ("bookings.confirmations","bookings.checkin")]
    w.tenant.save(update_fields=["enabled_features"])
    assert client_for(owner).get(owner_url(w)).status_code == 404


@pytest.mark.parametrize("kind", ["garbage","unknown","booking_uuid","calendar_token","foreign"])
def test_uniform_404_credentials_and_no_resolve_writes(kind):
    w = world(); other = world("arrival-foreign")
    credential = {"garbage":"nope", "unknown":"spaceworks-booking:"+str(uuid4()),
                  "booking_uuid":str(w.booking.public_token),"calendar_token":"a"*43,"foreign":other.credential}[kind]
    count = AuditLog.objects.count()
    response = client_for(w.scanner).post(url(w,"resolve"), {"credential":credential}, format="json")
    assert response.status_code == 404 and str(response.data["detail"]) == "Not found."
    assert not BookingCheckInEvent.objects.exists() and AuditLog.objects.count() == count


@pytest.mark.parametrize("permission", ["edit_details","manage_reservations","publish_page"])
def test_scanner_permission_is_separate_from_other_grants(permission):
    w = world(); w.grant.permissions = [permission]; w.grant.save(update_fields=["permissions"])
    assert client_for(w.scanner).post(url(w,"resolve"), {"credential":w.credential}, format="json").status_code == 403


def test_scanner_projection_and_revocation_and_cross_tenant(monkeypatch):
    w = world(); clock(monkeypatch, w.booking.starts_at)
    scanner = client_for(w.scanner)
    result = scanner.post(url(w,"resolve"), {"credential":w.credential}, format="json")
    assert result.status_code == 200 and result.data["display_name"] == w.booking.name
    assert set(result.data) == {"booking_id","display_name","space_name","timezone","starts_at","ends_at","status","arrived_at","can_arrive","can_reverse","departed_at","can_depart","waiver_state","can_print_pass"}
    assert "no-store" in result["Cache-Control"]
    assert scanner.get(reverse("admin-space-booking-list", kwargs={"pk":w.resource.pk})).status_code == 403
    w.grant.revoked_at = w.booking.starts_at; w.grant.save(update_fields=["revoked_at"])
    # Revocation removes resource visibility as well as write authority.
    audits = AuditLog.objects.count()
    assert scanner.post(url(w,"confirm"), {"credential":w.credential}, format="json").status_code == 404
    w.booking.refresh_from_db()
    assert w.booking.arrived_at is None and not BookingCheckInEvent.objects.exists()
    assert AuditLog.objects.count() == audits
    other = world("arrival-wrong-tenant")
    assert client_for(other.scanner).post(url(w,"resolve"), {"credential":w.credential}, format="json").status_code in (403,404)


def test_rotation_and_cancel_invalidate_old_qr_and_keep_calendar_identity(monkeypatch):
    w = world(); owner = client_for(w.owner)
    initial = Calendar.from_ical(owner.get(owner_url(w,"calendar")).content).walk("VEVENT")[0]
    replacement = owner.post(owner_url(w,"rotate-checkin"), {}, format="json")
    assert replacement.status_code == 200 and replacement.data["qr_value"] != w.credential
    assert client_for(w.scanner).post(url(w,"resolve"), {"credential":w.credential}, format="json").status_code == 404
    w.booking.refresh_from_db(); old = qr_value(w.booking)
    services.cancel_booking(w.booking, actor=w.manager)
    assert client_for(w.scanner).post(url(w,"resolve"), {"credential":old}, format="json").status_code == 404
    changed = Calendar.from_ical(owner.get(owner_url(w,"calendar")).content).walk("VEVENT")[0]
    assert changed["UID"] == initial["UID"] and int(changed["SEQUENCE"]) == int(initial["SEQUENCE"]) + 1
    assert str(changed["STATUS"]) == "CANCELLED"
    assert str(w.booking.checkin_token) not in str(changed)
    assert all(w.credential not in str(meta) for meta in AuditLog.objects.values_list("meta",flat=True))


def test_png_is_valid_unicode_image_and_render_context_omits_private_data(monkeypatch):
    w = world(); w.resource.name = "\u0ba4\u0bae\u0bbf\u0bb4\u0bcd \u03b5\u03c1\u03b3\u03b1\u03c3\u03c4\u03ae\u03c1\u03b9\u03bf \u5de5\u623f"; w.resource.save(update_fields=["name"])
    import apps.bookings.confirmation_render as adapter
    w.booking.note = "Private note never printable"; w.booking.save(update_fields=["note"])
    actual = adapter.render_confirmation_png; seen = {}
    def render(**kwargs):
        seen.update(kwargs); return actual(**kwargs)
    monkeypatch.setattr(adapter,"render_confirmation_png",render)
    response = client_for(w.owner).get(owner_url(w,"confirmation-png"))
    assert response.status_code == 200 and response["Content-Type"] == "image/png"
    assert response["Referrer-Policy"] == "no-referrer" and "no-store" in response["Cache-Control"]
    image = Image.open(BytesIO(response.content)); image.verify()
    assert seen["qr_value"] == w.credential and seen["title"] == w.resource.name
    assert w.owner.email not in str(seen) and w.booking.note not in seen["lines"]
    assert AuditLog.objects.filter(action="booking.confirmation_downloaded").count() == 1


def test_qr_log_filter_redacts_the_whole_credential():
    from config.log_setup import RequestIdFilter
    credential = "spaceworks-booking:"+str(uuid4())
    record = logging.LogRecord("django.request",logging.WARNING,"",0,"invalid %s",(credential,),None)
    RequestIdFilter().filter(record)
    assert credential not in record.getMessage() and "[redacted]" in record.getMessage()


@pytest.mark.parametrize("blocked", ["feature","inactive_resource","inactive_scanner"])
def test_live_scanner_gates_cannot_be_bypassed(monkeypatch,blocked):
    w=world(); clock(monkeypatch,w.booking.starts_at)
    if blocked == "feature":
        w.tenant.enabled_features=[key for key in w.tenant.enabled_features if key != "bookings.checkin"]
        w.tenant.save(update_fields=["enabled_features"])
    elif blocked == "inactive_resource":
        w.resource.is_active=False; w.resource.save(update_fields=["is_active"])
    else:
        w.scanner.is_active=False; w.scanner.save(update_fields=["is_active"])
    response=client_for(w.scanner).post(url(w,"confirm"),{"credential":w.credential},format="json")
    assert response.status_code in (400,403,404,409)
    assert not BookingCheckInEvent.objects.exists()


def test_qr_pixels_encode_the_exact_isolated_credential():
    import segno
    from apps.bookings.confirmation_render import confirmation_png
    w=world()
    image=Image.open(BytesIO(confirmation_png(w.booking))).convert("RGB")
    matrix=tuple(segno.make(w.credential,micro=False).matrix_iter(scale=8,border=4))
    side=len(matrix); left=(image.width-side)//2; top=100+4*24
    # Check every QR module center, including the quiet zone. PNG compression and
    # Unicode labels cannot alter the exact machine-readable credential matrix.
    for y in range(4,side,8):
        for x in range(4,side,8):
            black=max(image.getpixel((left+x,top+y))) < 128
            assert black == bool(matrix[y][x])


@pytest.mark.parametrize("variant", ["hex","braced","uppercase"])
def test_noncanonical_uuid_forms_are_uniformly_refused_and_never_echoed(variant):
    w=world(); token=w.booking.checkin_token
    value={"hex":token.hex,"braced":"{"+str(token)+"}","uppercase":str(token).upper()}[variant]
    response=client_for(w.scanner).post(url(w,"resolve"),{"credential":"spaceworks-booking:"+value},format="json")
    assert response.status_code == 404 and value not in str(response.data)
